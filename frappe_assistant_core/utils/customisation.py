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

"""Shared helpers for customisation work: which doctypes count, and the Server Script safety guard."""

from typing import Any, Dict, Optional

import frappe
from frappe import _
from frappe.utils import get_url_to_form

CUSTOMISATION_DOCTYPES = frozenset(
    {
        "Server Script",
        "Client Script",
        "Custom Field",
        "Property Setter",
        "Workflow",
        "Workflow State",
        "Workflow Action Master",
        "Custom DocPerm",
        "DocType",
        "Role",
        "Report",
        "Print Format",
        "Notification",
    }
)


def server_scripts_enabled() -> bool:
    """Whether this site runs Server Scripts at all."""
    from frappe.utils.safe_exec import is_safe_exec_enabled

    return bool(is_safe_exec_enabled())


def server_script_guard(
    doctype: str, data: Dict[str, Any], current_disabled: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Refuse an active Server Script when server scripts are switched off on the site.

    Frappe then raises on every save of the script's document type, so an active script
    would stop that type from saving. Returns None when the write is allowed.
    """
    if doctype != "Server Script" or server_scripts_enabled():
        return None

    disabled = data.get("disabled", current_disabled if current_disabled is not None else 0)
    if disabled:
        return None

    reference_doctype = data.get("reference_doctype") or _("document")
    return {
        "success": False,
        "error": _(
            "Server scripts are switched off on this site, so this script would stop every "
            "{0} from saving. An administrator can switch them on (on Frappe Cloud this needs "
            "a private bench). I can save it switched off instead, or use a different approach."
        ).format(reference_doctype),
        "error_type": "server_scripts_disabled",
        "guidance": _(
            "Save the script with disabled set to 1, or achieve the same result with a "
            "Client Script, a Workflow or a Notification."
        ),
    }


def desk_url(doctype: str, name: str) -> str:
    """Link to a record's form in Desk."""
    return get_url_to_form(doctype, name)
