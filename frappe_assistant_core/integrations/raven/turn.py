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

"""The Raven job: one FACO turn for one addressed message, run as the asker and waited on.

Frappe's RQ worker forks a process per job, and a relay thread started here would die when the
job returned; so the job waits for the relay to finish (queue "long", timeout 1200s).
"""

import base64
import time

import frappe
from frappe import _, _lt

from frappe_assistant_core.chat.api.chat import turn_observers
from frappe_assistant_core.integrations.raven import bot, formatting, sessions
from frappe_assistant_core.integrations.raven.sink import RavenReplyWriter, ReplySink

REPLIES_KEY = "fac_raven_replies"
TURN_TIMEOUT = 1100
LOCK_WAIT = 300
IMAGE_LIMIT = 5 * 1024 * 1024
DM_LINE = _lt("You are answering as FAC Bot in a private Raven conversation. Raven cannot draw charts.")
CHANNEL_LINE = _lt(
    "You are answering as FAC Bot in a shared Raven channel; everyone in it can read your answer. "
    "Avoid sensitive figures unless the user asks for them explicitly. Raven cannot draw charts."
)


def run(message_id: str, kind: str) -> None:
    msg = frappe.get_doc("Raven Message", message_id)
    if not _is_person(msg.owner):
        return
    frappe.set_user(msg.owner)  # nosemgrep: frappe-setuser — the turn runs as, and bills, the asker
    raven_bot = frappe.get_doc("Raven Bot", bot.BOT_NAME)
    if bot.state() != "on":
        raven_bot.send_message(_reply_channel(msg, kind), str(formatting.SWITCHED_OFF))
        return
    in_thread = _is_thread(msg.channel_id)
    if kind == "mention" and not in_thread and not raven_bot.is_member(msg.channel_id):
        raven_bot.send_message(_reply_channel(msg, kind), str(formatting.NOT_A_MEMBER))
        return
    reply_channel = _reply_channel(msg, kind)
    from frappe_assistant_core.chat.api.settings import can_use_faco

    access = can_use_faco()
    if not access.get("can_use"):
        raven_bot.send_message(reply_channel, formatting.refusal_text(access))
        return
    session_id = sessions.session_id_for(reply_channel, msg.owner)
    with _session_lock(session_id):
        _run_turn(msg, kind, raven_bot, reply_channel, session_id)


def _is_person(user: str) -> bool:
    """Only a person's own words start a turn. Server code (document notifications, imports) inserts
    messages as Administrator; running those as their owner would let text nobody typed act with
    Administrator's rights."""
    if user in ("Administrator", "Guest"):
        return False
    return bool(frappe.db.exists("Raven User", {"user": user, "type": "User", "enabled": 1}))


def _is_thread(channel_id: str) -> bool:
    return bool(frappe.get_cached_doc("Raven Channel", channel_id).is_thread)


def _reply_channel(msg, kind: str) -> str:
    """A DM or a thread is answered where it is; a channel message gets a thread of its own."""
    if kind == "dm" or _is_thread(msg.channel_id):
        return msg.channel_id
    if not msg.is_thread:
        from raven.api.threads import create_thread

        create_thread(msg.name)  # as the asker; the thread's channel id is the message name
    return msg.name


def _batch(msg) -> list:
    """The message plus the files sent with it (files and their caption share a batch id)."""
    if not msg.message_batch_id:
        return [msg]
    return frappe.get_all(
        "Raven Message",
        # Only the asker's own messages: the batch id is client-chosen, so another member could
        # reuse it to slip their text or files into this person's turn.
        filters={"channel_id": msg.channel_id, "message_batch_id": msg.message_batch_id, "owner": msg.owner},
        fields=["name", "message_type", "content", "file"],
        order_by="creation asc",
    )


def _files(batch) -> tuple[list[str], list[dict], list[str]]:
    """Readable files split into documents and images; names of the ones the asker cannot read."""
    file_urls, images, dropped = [], [], []
    for row in batch:
        if row.message_type not in ("File", "Image") or not row.file:
            continue
        name = frappe.db.get_value("File", {"file_url": row.file}, "name")
        if not name or not frappe.has_permission("File", "read", doc=name):
            dropped.append(row.file.rsplit("/", 1)[-1])
            continue
        file_doc = frappe.get_doc("File", name)
        if row.message_type == "Image" and (file_doc.file_size or 0) <= IMAGE_LIMIT:
            images.append(
                {
                    "type": "image",
                    "format": (file_doc.file_name.rsplit(".", 1)[-1] or "png").lower(),
                    "name": file_doc.file_name,
                    "file_url": row.file,
                    "data": base64.b64encode(file_doc.get_content()).decode(),
                }
            )
        else:
            file_urls.append(row.file)
    return file_urls, images, dropped


def _track(reply: str, session_id: str) -> None:
    frappe.cache.hset(REPLIES_KEY, reply, {"session_id": session_id, "updated": time.time()})


def _run_turn(msg, kind: str, raven_bot, reply_channel: str, session_id: str) -> None:
    from frappe_assistant_core.chat.api.chat.messages import start_turn

    batch = _batch(msg)
    text = next((row.content for row in batch if row.message_type == "Text" and row.content), "")
    file_urls, images, dropped = _files(batch)
    addendum = str(CHANNEL_LINE if kind == "mention" else DM_LINE)
    if dropped:
        addendum += " " + _(
            "These files were not shared with the user, so they are not attached: {0}."
        ).format(", ".join(dropped))
    reply = raven_bot.send_message(reply_channel, "<p>…</p>")
    sink = ReplySink(
        RavenReplyWriter(reply, reply_channel, raven_bot.raven_user), sessions.session_url(session_id)
    )
    _track(reply, session_id)
    frappe.db.commit()  # nosemgrep: frappe-manual-commit — background job; the reply must exist before the relay edits it.

    def observe(event: dict) -> None:
        sink(event)
        if sink.done:
            frappe.cache.hdel(REPLIES_KEY, reply)
            turn_observers.unregister(session_id)
        else:
            _track(reply, session_id)

    turn_observers.register(session_id, observe)
    try:
        future = start_turn(
            session_id,
            text or _("(sent files)"),
            file_urls=file_urls,
            attachments=images,
            system_prompt_addendum=addendum,
            client_type="raven",
        )
        future.result(timeout=TURN_TIMEOUT)
    except Exception:
        frappe.log_error(title="FAC Bot turn failed", message=frappe.get_traceback())
        if not sink.done:
            sink({"event": "stream_error"})
    finally:
        turn_observers.unregister(session_id)
        frappe.cache.hdel(REPLIES_KEY, reply)


class _session_lock:
    """One turn at a time per session: a second message waits (up to LOCK_WAIT) instead of racing."""

    def __init__(self, session_id: str):
        self.key = frappe.cache.make_key(f"fac_raven_lock:{session_id}")

    def __enter__(self):
        deadline = time.monotonic() + LOCK_WAIT
        # nosemgrep: frappe-cache-breaks-multitenancy — the key is site-prefixed (make_key); set_value has no NX
        while not frappe.cache.set(self.key, 1, nx=True, ex=TURN_TIMEOUT + 60):
            if time.monotonic() > deadline:
                break
            time.sleep(0.2)
        return self

    def __exit__(self, *exc):
        frappe.cache.delete(self.key)
