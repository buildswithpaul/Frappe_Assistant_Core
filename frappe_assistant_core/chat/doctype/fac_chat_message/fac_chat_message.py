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

import frappe
from frappe import _
from frappe.model.document import Document


class FACChatMessage(Document):
    """FAC Chat Message - Stores individual messages in a session"""

    def before_insert(self):
        """Set timestamp and validate session"""
        if not self.timestamp:
            self.timestamp = frappe.utils.now()

        # Set user from session if not provided
        if not self.user:
            self.user = frappe.session.user

    def validate(self):
        """Validate message data"""
        self.validate_role()
        self.validate_context()

    def validate_role(self):
        """Ensure role is either 'user' or 'assistant'"""
        if self.role not in ["user", "assistant"]:
            frappe.throw(_("Role must be either 'user' or 'assistant'"))

    def validate_context(self):
        """Validate context fields if context_type is set.

        Context fields (doctype/name/url) are all optional even for
        Form/List/Report context types — messages may originate from
        contexts where those details are not yet available.
        """
        # No-op: context details are optional for all context_types.
        return

    @staticmethod
    def get_session_messages(session_id, limit=30, offset=0, user=None):
        """Get messages for a session with pagination, ordered by timestamp, with attachments.

        Returns the most recent messages (applies offset from the end).
        Returns dict with 'messages' and 'has_more' for pagination.

        Args:
                session_id: Conversation session ID.
                limit: Max messages to return.
                offset: Number of messages to skip from the end.
                user: When provided, restrict the query to messages owned by this user
                        (prevents cross-user IDOR). Pass ``None`` for admin/trusted callers
                        that explicitly need unfiltered access.
        """
        # Build filter dict — scope to user when provided
        base_filters: dict = {"session_id": session_id}
        if user:
            base_filters["user"] = user

        # Count total messages for this session (respecting user scope if set)
        total = frappe.db.count("FAC Chat Message", base_filters)

        if total == 0:
            return None  # Signal to caller to try AR fallback

        # Calculate pagination — load from the end (most recent first)
        start = max(0, total - limit - offset)
        page_limit = min(limit, total - offset)

        if page_limit <= 0:
            return {"messages": [], "has_more": False}

        messages = frappe.get_all(
            "FAC Chat Message",
            filters=base_filters,
            fields=[
                "name",
                "role",
                "content",
                "timestamp",
                "tool_calls",
                "blocks",
                "idx",
                "message_id",
                "aborted",
                "errored",
                # Without these the per-message cost chip only ever exists on
                # the live turn and vanishes on reload.
                "credits_used",
                "model",
                "model_breakdown",
            ],
            order_by="idx asc, timestamp asc",
            limit_start=start,
            limit_page_length=page_limit,
        )

        # Get attachments for each message
        for msg in messages:
            msg["attachments"] = frappe.get_all(
                "File",
                filters={"attached_to_doctype": "FAC Chat Message", "attached_to_name": msg.name},
                fields=["name", "file_name", "file_url", "file_size"],
            )

        return {
            "messages": messages,
            "has_more": start > 0,
        }

    @staticmethod
    def create_message(session_id, role, content, context=None, llm_metadata=None):
        """Helper method to create a new message.

        ``content`` is allowed to be empty: streaming creates an assistant
        shell row up front (so a resume can find it by message_id) and the
        real text is backfilled when ``stream_complete`` fires. The shell
        insert therefore skips the mandatory-field check on ``content``;
        every other field is still validated normally.
        """
        # Get the next idx for this session
        last_msg = frappe.get_all(
            "FAC Chat Message",
            filters={"session_id": session_id},
            fields=["idx"],
            order_by="idx desc",
            limit=1,
        )
        next_idx = (last_msg[0].idx + 1) if last_msg else 1

        doc = frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": session_id,
                "role": role,
                "content": content,
                "user": frappe.session.user,
                "timestamp": frappe.utils.now(),
                "idx": next_idx,
            }
        )

        # Add context if provided
        if context:
            doc.context_type = context.get("type")
            doc.context_doctype = context.get("doctype")
            doc.context_name = context.get("name")
            doc.context_url = context.get("url")

        # Add LLM metadata if provided (for assistant messages). FAC surfaces
        # credits only — token counts are recorded by AR (AR Message), not here.
        if llm_metadata:
            doc.model = llm_metadata.get("model")
            doc.credits_used = llm_metadata.get("credits_used")
            doc.tool_calls = llm_metadata.get("tool_calls")

        # ignore_mandatory: assistant streaming shells start with empty content,
        # backfilled on stream_complete. Without this the reqd content field
        # raises MandatoryError and the shell — which the resume relies on — is
        # never created, cascading into a failed resume.
        doc.insert(ignore_permissions=True, ignore_mandatory=not content)
        return doc
