# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Raven Message hooks: decide whether FAC Bot was addressed, then hand off to a job.

Every Raven message on the site passes here (Raven has no hook for external bots), so the checks
run cheapest first and an ordinary channel message costs no database query.
"""

from typing import Literal

import frappe
from redis.exceptions import ConnectionError as RedisConnectionError

from frappe_assistant_core.integrations.raven import bot

ANSWERED_TYPES = ("Text", "File", "Image")
# Each turn holds a worker while it runs; the HTTP send endpoint allows 30 a minute.
TURNS_PER_MINUTE = 10
TURN_JOB = "frappe_assistant_core.integrations.raven.turn.run"


def addressed(doc) -> Literal["dm", "mention"] | None:
    """How FAC Bot was addressed by this message, if at all. A switched-off bot is still
    addressed, so it can say it is off; a site that never created it skips everything."""
    flags = frappe.flags
    if flags.in_install or flags.in_migrate or flags.in_patch or flags.in_import:
        return None
    if doc.is_bot_message or doc.message_type not in ANSWERED_TYPES:
        return None
    if doc.owner == "Guest" or (doc.owner == "Administrator" and not _typed_by_administrator()):
        return None
    if bot.state() == "absent":
        return None
    if any(row.user == bot.BOT_NAME for row in doc.mentions or []):
        return "mention"
    channel = frappe.get_cached_doc("Raven Channel", doc.channel_id)
    if channel.is_direct_message and bot.BOT_NAME in (channel.dm_user_1, channel.dm_user_2):
        return "dm"
    return None


# Raven's composer sends through these; nothing else counts as Administrator typing.
RAVEN_SEND_METHODS = (
    "raven.api.raven_message.send_message",
    "raven.api.raven_message.send_message_with_attachments",
    "raven.api.upload_file.upload_file_with_message",
)


def _typed_by_administrator() -> bool:
    """Administrator typing in Raven, as opposed to server code that inserts as Administrator.

    Jobs and the scheduler insert with no request behind them, and any other endpoint running as
    Administrator may insert words nobody typed; running those as Administrator would let that text
    act with Administrator's rights. So only Raven's own send methods count, called from a logged-in
    session (browser cookie or the mobile app's OAuth token) rather than with an API key.
    """
    request = getattr(frappe.local, "request", None)
    if request is None or frappe.session.user != "Administrator":
        return False
    # An OAuth Bearer token is a person's own login (Raven's mobile app sends with one); an API
    # key ("token key:secret") or Basic auth is a script.
    authorization = (getattr(request, "headers", None) or {}).get("Authorization") or ""
    if authorization and not authorization.lower().startswith("bearer "):
        return False
    return (frappe.local.form_dict or {}).get("cmd") in RAVEN_SEND_METHODS


def _enqueue(doc, kind: str) -> None:
    # One job per send: files and their caption share a batch id, so they make one turn.
    try:
        frappe.enqueue(
            TURN_JOB,
            queue="long",
            timeout=1200,
            job_id=f"fac-raven:{doc.message_batch_id or doc.name}",
            deduplicate=True,
            enqueue_after_commit=True,
            message_id=doc.name,
            kind=kind,
            # Decided here, in the request that inserted the message; the job cannot tell.
            typed_by_person=True,
        )
    except RedisConnectionError:
        frappe.logger("fac_raven").warning(f"Redis is down; FAC Bot skipped message {doc.name}")


def _within_rate(owner: str) -> bool:
    key = frappe.cache.make_key(f"fac_raven_rate:{owner}")
    try:
        count = frappe.cache.incr(key)
        if count == 1:
            frappe.cache.expire(key, 60)
    except RedisConnectionError:
        return True  # the enqueue fails next and logs; do not count against the person
    return count <= TURNS_PER_MINUTE


def on_insert(doc, method=None) -> None:
    kind = addressed(doc)
    if not kind:
        return
    # One batch is one turn: only its first message counts against the person.
    if doc.message_batch_id and frappe.flags.get(f"fac_raven_batch:{doc.message_batch_id}"):
        return
    if doc.message_batch_id:
        frappe.flags[f"fac_raven_batch:{doc.message_batch_id}"] = True
    if not _within_rate(doc.owner):
        frappe.logger("fac_raven").info(f"FAC Bot rate limit: skipped message {doc.name} from {doc.owner}")
        return
    _enqueue(doc, kind)


def on_update(doc, method=None) -> None:
    # Older upload paths set `file` after insert: a file arriving is a new message, an edit is not.
    # Frappe also runs on_update inside insert; after_insert has handled that one.
    if doc.flags.in_insert or doc.is_new():
        return
    if doc.message_type not in ("File", "Image") or not doc.has_value_changed("file"):
        return
    on_insert(doc)


def on_trash(doc, method=None) -> None:
    """Raven has no Stop button: deleting FAC Bot's reply while it streams stops the turn."""
    if not doc.is_bot_message or doc.bot != bot.BOT_NAME:
        return
    from frappe_assistant_core.chat.api.chat.cancel import mark_cancelled
    from frappe_assistant_core.integrations.raven.turn import REPLIES_KEY

    entry = frappe.cache.hget(REPLIES_KEY, doc.name)
    if entry:
        mark_cancelled(entry["session_id"])
