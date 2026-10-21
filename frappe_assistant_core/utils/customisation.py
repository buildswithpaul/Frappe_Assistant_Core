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

from typing import Any, Dict, Iterable, Optional

import frappe
from frappe import _
from frappe.utils import cint, get_url_to_form

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

APPLIES_TO_FIELDS = {
    "Custom Field": "dt",
    "Property Setter": "doc_type",
    "Client Script": "dt",
    "Server Script": "reference_doctype",
    "Print Format": "doc_type",
    "Notification": "document_type",
}


def server_scripts_enabled() -> bool:
    """Whether this site runs Server Scripts at all."""
    from frappe.utils.safe_exec import is_safe_exec_enabled

    return bool(is_safe_exec_enabled())


def script_report_warning(doctype: str, data: Dict[str, Any], current: Optional[Any] = None) -> Optional[str]:
    """Warn when a custom Script Report is saved while server scripts are off.

    The save is allowed: the report is harmless until someone runs it. `current` is the stored
    record on an update, used for whatever `data` leaves out.
    """
    if doctype != "Report" or server_scripts_enabled():
        return None

    def value(field: str) -> Any:
        if field in data:
            return data[field]
        return current.get(field) if current is not None else None

    if value("report_type") != "Script Report" or value("is_standard") != "No":
        return None

    return _(
        "Server scripts are switched off on this site, so this report will show an error when "
        "someone runs it until an administrator switches them on (on Frappe Cloud this needs a "
        "private bench)."
    )


def server_script_guard(
    doctype: str,
    data: Dict[str, Any],
    current_disabled: Optional[int] = None,
    current_reference_doctype: Optional[str] = None,
    current_script_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Refuse an active Server Script when server scripts are switched off on the site.

    A DocType Event script would stop its document type from saving; other script types
    would simply never run. Returns None when the write is allowed.
    """
    if doctype != "Server Script" or server_scripts_enabled():
        return None

    disabled = cint(data["disabled"]) if "disabled" in data else cint(current_disabled)
    if disabled:
        return None

    script_type = data.get("script_type") or current_script_type or "DocType Event"
    if script_type == "DocType Event":
        reference_doctype = data.get("reference_doctype") or current_reference_doctype or _("document")
        error = _(
            "Server scripts are switched off on this site, so this script would stop every "
            "{0} from saving. An administrator can switch them on (on Frappe Cloud this needs "
            "a private bench). I can save it switched off instead, or use a different approach."
        ).format(reference_doctype)
    else:
        error = _(
            "Server scripts are switched off on this site, so this script would not run. "
            "An administrator can switch them on (on Frappe Cloud this needs a private bench). "
            "I can save it switched off instead, or use a different approach."
        )

    return {
        "success": False,
        "error": error,
        "error_type": "server_scripts_disabled",
        "guidance": _(
            "Save the script with disabled set to 1, or achieve the same result with a "
            "Client Script, a Workflow or a Notification."
        ),
    }


def desk_url(doctype: str, name: str) -> str:
    """Link to a record's form in Desk."""
    return get_url_to_form(doctype, name)


def applies_to(doctype: str, values: Any) -> Optional[Dict[str, str]]:
    """The doctype a customisation changes, with a link to where to see it in Desk."""
    field = APPLIES_TO_FIELDS.get(doctype)
    target = values.get(field) if field else None
    if not target:
        return None
    return {"doctype": target, "url": get_url_to_form(target, "new")}


def locate_field(fields: Iterable[Any], fieldname: str) -> Optional[Dict[str, Any]]:
    """Where a field shows on its form, from the form's fields in layout (idx) order.

    Mirrors how Desk lays a form out: fields before the first Tab Break sit on a default
    "Details" tab when the form has tabs at all, and a field belongs to the nearest Section
    Break above it. `collapsed` is true when that section starts folded.
    """
    fields = list(fields)
    tabbed = any(f.fieldtype == "Tab Break" for f in fields)
    first_tab = True
    tab: Optional[str] = _("Details") if tabbed and fields and fields[0].fieldtype != "Tab Break" else None
    section: Optional[str] = None
    collapsed = False
    seen_tabs = 1 if tab else 0

    for field in fields:
        if field.fieldname == fieldname:
            return {"tab": tab, "section": section, "collapsed": collapsed, "first_tab": first_tab}
        if field.fieldtype == "Tab Break":
            seen_tabs += 1
            first_tab = seen_tabs == 1
            tab = field.label or None
            section, collapsed = None, False
        elif field.fieldtype == "Section Break":
            section = field.label or None
            collapsed = bool(cint(field.collapsible))
    return None


def custom_field_location(doc: Any) -> Optional[Dict[str, Any]]:
    """Where a saved Custom Field shows, read from the target form's meta after the save."""
    if not doc.get("dt") or not doc.get("fieldname"):
        return None
    return locate_field(frappe.get_meta(doc.dt, cached=False).fields, doc.fieldname)
