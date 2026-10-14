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
from frappe_assistant_core.chat.api.chat.conversation_files import files_addendum
from frappe_assistant_core.integrations.raven import bot, formatting, sessions
from frappe_assistant_core.integrations.raven.sink import RavenReplyWriter, ReplySink

REPLIES_KEY = "fac_raven_replies"
TURN_TIMEOUT = 1100
IMAGE_LIMIT = 5 * 1024 * 1024
DM_LINE = _lt("You are answering as FAC Bot in a private Raven conversation. Raven cannot draw charts.")
CHANNEL_LINE = _lt(
    "You are answering as FAC Bot in a shared Raven channel; everyone in it can read your answer. "
    "Avoid sensitive figures unless the user asks for them explicitly. Raven cannot draw charts."
)


def run(message_id: str, kind: str, typed_by_person: bool = False) -> None:
    msg = frappe.get_doc("Raven Message", message_id)
    if not _is_person(msg.owner, typed_by_person) or not _claim_batch(msg):
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
    lock = _session_lock(session_id)
    if not lock.acquire():
        raven_bot.send_message(reply_channel, str(formatting.STILL_WORKING))
        return
    try:
        _run_turn(msg, kind, raven_bot, reply_channel, session_id)
    finally:
        lock.release()


def _is_person(user: str, typed_by_person: bool = False) -> bool:
    """Only a person's own words start a turn. Server code (jobs, the scheduler) inserts messages as
    Administrator; running those as their owner would let text nobody typed act with Administrator's
    rights. Administrator's own messages count when the trigger saw them typed in a request."""
    if user == "Guest" or (user == "Administrator" and not typed_by_person):
        return False
    return bool(frappe.db.exists("Raven User", {"user": user, "type": "User", "enabled": 1}))


def _claim_batch(msg) -> bool:
    """One answer per send. Files and their caption arrive as separate messages of one batch, and
    each reaches the trigger; job de-duplication does not hold for enqueues deferred to commit."""
    if not msg.message_batch_id:
        return True
    key = frappe.cache.make_key(f"fac_raven_batch:{msg.channel_id}:{msg.message_batch_id}")
    # nosemgrep: frappe-cache-breaks-multitenancy — the key is site-prefixed (make_key); set_value has no NX
    return bool(frappe.cache.set(key, 1, nx=True, ex=3600))


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


def _files(batch) -> tuple[list, list[dict], list[str]]:
    """Readable files split into documents (File rows) and images; names the asker cannot read."""
    documents, images, dropped = [], [], []
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
            documents.append(
                frappe._dict(
                    name=file_doc.name,
                    file_name=file_doc.file_name,
                    file_url=file_doc.file_url,
                    file_size=file_doc.file_size,
                )
            )
    return documents, images, dropped


def _track(reply: str, session_id: str) -> None:
    frappe.cache.hset(REPLIES_KEY, reply, {"session_id": session_id, "updated": time.time()})


def _run_turn(msg, kind: str, raven_bot, reply_channel: str, session_id: str) -> None:
    from frappe_assistant_core.chat.api.chat.messages import start_turn

    batch = _batch(msg)
    text = next((row.content for row in batch if row.message_type == "Text" and row.content), "")
    documents, images, dropped = _files(batch)
    addendum = str(CHANNEL_LINE if kind == "mention" else DM_LINE)
    # Raven's files stay attached to their Raven message; their text goes into this turn's prompt.
    addendum += files_addendum(documents)
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
            turn_observers.unregister(session_id)
        else:
            _track(reply, session_id)

    turn_observers.register(session_id, observe)
    try:
        future = start_turn(
            session_id,
            text or _("(sent files)"),
            attachments=images,
            system_prompt_addendum=addendum,
            client_type="raven",
        )
        future.result(timeout=TURN_TIMEOUT)
        # A stream can end with no final event (FAC Cloud's worker died); never leave "…".
        sink.interrupted()
    except Exception:
        frappe.log_error(title="FAC Bot turn failed", message=frappe.get_traceback())
        if not sink.done:
            sink({"event": "stream_error"})
    finally:
        turn_observers.unregister(session_id)
        # Still tracked if unfinished (the job was killed), so the sweep can finish it.
        if sink.done:
            frappe.cache.hdel(REPLIES_KEY, reply)


class _session_lock:
    """One turn at a time per session. A second message is told to wait rather than queued: each
    turn holds a worker, and two turns on one session would race on its saved state."""

    def __init__(self, session_id: str):
        self.key = frappe.cache.make_key(f"fac_raven_lock:{session_id}")
        self.token = frappe.generate_hash(length=16)

    def acquire(self) -> bool:
        # nosemgrep: frappe-cache-breaks-multitenancy — the key is site-prefixed (make_key); set_value has no NX
        return bool(frappe.cache.set(self.key, self.token, nx=True, ex=TURN_TIMEOUT + 60))

    def release(self) -> None:
        # Only our own lock: if ours expired and another turn took the key, leave theirs alone.
        # nosemgrep: frappe-cache-breaks-multitenancy — the key is site-prefixed (make_key)
        if frappe.cache.get(self.key) == self.token.encode():
            frappe.cache.delete(self.key)
