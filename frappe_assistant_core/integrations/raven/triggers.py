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
TURN_JOB = "frappe_assistant_core.integrations.raven.turn.run"


def addressed(doc) -> Literal["dm", "mention"] | None:
    """How FAC Bot was addressed by this message, if at all. A switched-off bot is still
    addressed, so it can say it is off; a site that never created it skips everything."""
    flags = frappe.flags
    if flags.in_install or flags.in_migrate or flags.in_patch or flags.in_import:
        return None
    if doc.is_bot_message or doc.message_type not in ANSWERED_TYPES:
        return None
    if bot.state() == "absent":
        return None
    if any(row.user == bot.BOT_NAME for row in doc.mentions or []):
        return "mention"
    channel = frappe.get_cached_doc("Raven Channel", doc.channel_id)
    if channel.is_direct_message and bot.BOT_NAME in (channel.dm_user_1, channel.dm_user_2):
        return "dm"
    return None


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
        )
    except RedisConnectionError:
        frappe.logger("fac_raven").warning(f"Redis is down; FAC Bot skipped message {doc.name}")


def on_insert(doc, method=None) -> None:
    kind = addressed(doc)
    if kind:
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
