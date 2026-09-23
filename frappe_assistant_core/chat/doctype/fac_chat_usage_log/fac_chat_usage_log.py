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
from frappe.model.document import Document


class FACChatUsageLog(Document):
    """FAC Chat Usage Log - Tracks all LLM API calls for billing and analytics"""

    def before_insert(self):
        """Set defaults before inserting"""
        if not self.timestamp:
            self.timestamp = frappe.utils.now()

        if not self.user:
            self.user = frappe.session.user

    @staticmethod
    def log_usage(
        session_id,
        model,
        tokens_prompt,
        tokens_completion,
        context=None,
        llm_mode=None,
        credits_used=0,
        success=True,
        error_message=None,
    ):
        """
        Log LLM usage

        Args:
            session_id: Session ID
            model: Model used (e.g., "gpt-4", "claude-3-sonnet")
            tokens_prompt: Input tokens
            tokens_completion: Output tokens
            context: Dict with context info (type, doctype, name)
            llm_mode: "byo_key" or "proxy"
            credits_used: Credits used (for proxy mode)
            success: Whether the call was successful
            error_message: Error message if failed
        """
        try:
            log = frappe.get_doc(
                {
                    "doctype": "FAC Chat Usage Log",
                    "user": frappe.session.user,
                    "session_id": session_id,
                    "timestamp": frappe.utils.now(),
                    "model": model,
                    "tokens_prompt": tokens_prompt,
                    "tokens_completion": tokens_completion,
                    "tokens_total": tokens_prompt + tokens_completion,
                    "llm_mode": llm_mode,
                    "credits_used": credits_used,
                    "success": success,
                    "error_message": error_message,
                }
            )

            # Add context if provided
            if context:
                log.context_type = context.get("type")
                log.context_doctype = context.get("doctype")
                log.context_name = context.get("name")

            log.insert(ignore_permissions=True)
            frappe.db.commit()

            return log

        except Exception as e:
            frappe.log_error(title="FAC Chat Usage Log Error", message=f"Failed to log usage: {e!s}")
