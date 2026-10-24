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

"""
Recent errors tool for the Core plugin.
Reads the Error Log and failed scheduled jobs so a builder can see what a script caused.
"""

from typing import Any, Dict, List

import frappe
from frappe.utils import add_to_date, now_datetime

from frappe_assistant_core.core.base_tool import BaseTool

DEFAULT_MINUTES = 60
MAX_MINUTES = 1440
DEFAULT_LIMIT = 10
MAX_LIMIT = 50
MAX_TEXT = 4000


def _like(text: str) -> str:
    """A LIKE pattern matching ``text`` literally anywhere."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _tail(text: str | None) -> str:
    """The last MAX_TEXT characters, where a traceback names its cause."""
    return (text or "")[-MAX_TEXT:]


class RecentErrors(BaseTool):
    """
    Tool for reading errors raised in the last few minutes.

    Read-only: it lists Error Log rows and failed Scheduled Job Log rows and
    never writes an Error Log row itself.
    """

    def __init__(self):
        super().__init__()
        self.name = "recent_errors"
        self.description = (
            "Read the errors this site logged recently: Error Log entries and failed scheduled "
            "jobs, newest first. Use this after running or saving a Server Script, hook or "
            "scheduled job you built, to see the traceback it caused. Pass contains, such as "
            "the script name, to narrow the list."
        )
        self.category = "Customization"
        self.requires_permission = None
        self.required_roles = ["System Manager"]

        self.inputSchema = {
            "type": "object",
            "properties": {
                "minutes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_MINUTES,
                    "default": DEFAULT_MINUTES,
                    "description": "How far back to look, up to 1440 (one day).",
                },
                "contains": {
                    "type": "string",
                    "description": "Only errors whose text contains this, for example a script name.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_LIMIT,
                    "default": DEFAULT_LIMIT,
                    "description": "Most rows to return from each list, up to 50.",
                },
            },
        }

    def _errors(self, since, contains: str, limit: int) -> List[Dict[str, Any]]:
        filters = [["creation", ">=", since]]
        if contains:
            filters.append(["error", "like", _like(contains)])
        rows = frappe.get_all(
            "Error Log",
            filters=filters,
            fields=["creation", "method", "error", "reference_doctype", "reference_name"],
            order_by="creation desc",
            limit_page_length=limit,
        )
        return [
            {
                "when": str(row.creation),
                "title": row.method,
                "reference": " ".join(part for part in (row.reference_doctype, row.reference_name) if part)
                or None,
                "error": _tail(row.error),
            }
            for row in rows
        ]

    def _failed_jobs(self, since, contains: str, limit: int) -> List[Dict[str, Any]]:
        filters = [["creation", ">=", since], ["status", "=", "Failed"]]
        or_filters = None
        if contains:
            pattern = _like(contains)
            or_filters = [["scheduled_job_type", "like", pattern], ["details", "like", pattern]]
        rows = frappe.get_all(
            "Scheduled Job Log",
            filters=filters,
            or_filters=or_filters,
            fields=["creation", "scheduled_job_type", "details"],
            order_by="creation desc",
            limit_page_length=limit,
        )
        return [
            {"when": str(row.creation), "job": row.scheduled_job_type, "details": _tail(row.details)}
            for row in rows
        ]

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Return recent Error Log rows and failed scheduled jobs."""
        minutes = max(1, min(int(arguments.get("minutes") or DEFAULT_MINUTES), MAX_MINUTES))
        limit = max(1, min(int(arguments.get("limit") or DEFAULT_LIMIT), MAX_LIMIT))
        contains = (arguments.get("contains") or "").strip()
        since = add_to_date(now_datetime(), minutes=-minutes)

        return {
            "success": True,
            "errors": self._errors(since, contains, limit),
            "failed_jobs": self._failed_jobs(since, contains, limit),
        }


recent_errors = RecentErrors
