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

"""FAC Chat Session State — the single client-held session blob per session.

Zero-retention conversations: AR keeps nothing in its DB; the only copy of
conversation state lives in this row as an opaque, signed, gzipped blob. FAC
stores and round-trips it but NEVER parses it (``state_blob`` / ``state_sig``
are handled opaquely). The blob is deleted together with its messages — there
is no separate TTL — by ``archive_session``, ``archive_all_conversations`` and
the retention scheduler, so it can never outlive the conversation it belongs to.
"""

import frappe
from frappe.model.document import Document


class FACChatSessionState(Document):
    """One signed session blob per session. Last-writer-wins by ``turn_seq``."""

    @staticmethod
    def upsert(session_id, user, wire, has_pending_interrupt=False):
        """Persist the latest signed session blob for ``session_id``.

        ``wire`` is the opaque AR wire form ``{blob, sig, format_version}``.
        The signed envelope carries an inner ``turn_seq``, but FAC must not
        parse the blob to read it — so we only trust a top-level ``turn_seq``
        when AR surfaces one, and otherwise fall back to a FAC-side monotonic
        counter (relay writes for a session are serialized, so stored + 1 is a
        correct last-writer-wins ordering). A stale write (turn_seq <= stored)
        is dropped so an out-of-order relay cannot regress state.
        """
        if not wire or not wire.get("blob"):
            return

        name = frappe.db.exists("FAC Chat Session State", {"session_id": session_id})
        stored = (frappe.db.get_value("FAC Chat Session State", name, "turn_seq") or 0) if name else 0

        wire_turn_seq = wire.get("turn_seq")
        turn_seq = int(wire_turn_seq) if wire_turn_seq is not None else stored + 1

        if name and turn_seq <= stored:
            return  # stale, drop

        values = {
            "turn_seq": turn_seq,
            "state_blob": wire["blob"],
            "state_sig": wire.get("sig"),
            "format_version": wire.get("format_version", 1),
            "has_pending_interrupt": int(has_pending_interrupt),
            "updated_at": frappe.utils.now(),
        }

        if name:
            frappe.db.set_value("FAC Chat Session State", name, values)
        else:
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Session State",
                    "session_id": session_id,
                    "user": user,
                    **values,
                }
            ).insert(ignore_permissions=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — background relay thread, explicit commit required.

    @staticmethod
    def persist_safe(session_id, user, wire, has_pending_interrupt=False):
        """Best-effort blob persist for the relay's stream_complete path.

        Blob persistence is the *only* copy of conversation state, but it must
        never break the visible chat: a failed upsert (e.g. an oversized blob
        hitting max_allowed_packet, an InnoDB lock/timeout, a transient DB
        error) must not turn a fully generated, already-persisted assistant
        response into a stream_error. So we swallow and log. The log is
        content-free (session_id + traceback only) — this is a zero-retention
        feature; no blob/transcript/message text may ever be logged.
        """
        try:
            FACChatSessionState.upsert(session_id, user, wire, has_pending_interrupt=has_pending_interrupt)
        except Exception:
            frappe.log_error(
                title="FAC zero-retention blob persist failed",
                message=f"session_id={session_id}",
            )

    @staticmethod
    def load_wire(session_id):
        """Return the stored wire form for ``session_id`` or ``None``."""
        row = frappe.db.get_value(
            "FAC Chat Session State",
            {"session_id": session_id},
            ["state_blob", "state_sig", "format_version", "turn_seq"],
            as_dict=True,
        )
        if not row or not row.state_blob:
            return None
        return {
            "blob": row.state_blob,
            "sig": row.state_sig,
            "format_version": row.format_version,
            "turn_seq": row.turn_seq,
        }

    @staticmethod
    def delete_for_sessions(session_ids):
        """Delete state rows for one or many ``session_id`` values.

        Used by archive, bulk-archive, and the retention cleanup so the blob
        never outlives its messages (delete-with-messages, no separate TTL).
        """
        if not session_ids:
            return
        if isinstance(session_ids, str):
            session_ids = [session_ids]
        frappe.db.delete("FAC Chat Session State", {"session_id": ["in", session_ids]})


def get_permission_query_conditions(user: str | None = None) -> str:
    """Row-level scope: a user only sees their own session-state blobs in any
    list/report/desk query. System Manager is intentionally NOT exempted here —
    the blob is zero-retention conversation state and must not be browsable
    cross-user even by an admin via the desk UI."""
    user = user or frappe.session.user
    if user == "Administrator":
        return ""
    return f"`tabFAC Chat Session State`.`user` = {frappe.db.escape(user)}"


def has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
    """Document-level scope: only the owning user (or Administrator) may access a
    given session-state blob through permission-checked paths."""
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    return getattr(doc, "user", None) == user
