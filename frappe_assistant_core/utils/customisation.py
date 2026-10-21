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

"""Shared helpers for customisation work: records that change how a site behaves.

Covers which doctypes count (``CUSTOMISATION_DOCTYPES``, the canonical list, mirrored by the
Chat SPA and by AR), the Server Script safety guard, the warning for a Script Report saved
while server scripts are off, links to a record and to the form a customisation changes
(``applies_to``), where a new Custom Field shows on its form (``location``), and
``customisation_result`` which puts those into a create or update tool result.
"""

from typing import Any, Dict, Iterable, Optional

import frappe
from frappe import _
from frappe.model.meta import Meta
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


def customisation_result(doctype: str, doc: Any, warning: Optional[str] = None) -> Dict[str, Any]:
    """The customisation details a create or update result adds.

    applies_to, location and warning, plus placement_warning when a Custom Field landed
    collapsed or off the first tab.
    """
    details: Dict[str, Any] = {}
    customised = applies_to(doctype, doc)
    if customised:
        details["applies_to"] = customised
    if doctype == "Custom Field":
        location = custom_field_location(doc)
        if location:
            details["location"] = location
            sentence = placement_warning(location)
            if sentence:
                details["placement_warning"] = sentence
    if warning:
        details["warning"] = warning
    return details


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


PROBE_FIELDNAME = "fac_placement_probe"


class _ProbeMeta(Meta):
    """A doctype's meta with one extra Custom Field, ordered by Frappe's own sort_fields."""

    def __init__(self, doctype: str, probe: Dict[str, Any]):
        self._probe = probe
        super().__init__(doctype)

    def add_custom_fields(self):
        super().add_custom_fields()
        self.extend("fields", [self._probe])
        # Custom fields are read in idx order, so the probe goes where its idx puts it.
        probe = self.fields.pop()
        position = next(
            (
                i
                for i, f in enumerate(self.fields)
                if getattr(f, "is_custom_field", False) and cint(f.idx) >= cint(probe.idx)
            ),
            len(self.fields),
        )
        self.fields.insert(position, probe)


def _new_field_idx(dt: str, insert_after: Optional[str]) -> Optional[int]:
    """The idx Frappe gives a new Custom Field: just after insert_after in the form's order."""
    fieldnames = [f.fieldname for f in frappe.get_meta(dt, cached=False).fields]
    return fieldnames.index(insert_after) + 1 if insert_after in fieldnames else None


def placement_is_ambiguous(dt: str, insert_after: Optional[str]) -> bool:
    """Whether another Custom Field after the same field already holds the idx a new one would get.

    Frappe orders custom fields by idx alone, so on a tie the database decides which comes first
    and the layout, hence the prediction, cannot be known in advance. A tie matters only between
    fields with the same insert_after. On v16 Tab and Section Breaks are moved to the end of their
    tab, so the flag can still be cautious there.
    """
    idx = _new_field_idx(dt, insert_after)
    return bool(
        idx and frappe.db.exists("Custom Field", {"dt": dt, "idx": idx, "insert_after": insert_after})
    )


def predict_field_location(
    dt: str, insert_after: Optional[str], fieldtype: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Where a Custom Field would show if saved now, before it exists.

    The field gets the idx Frappe gives a new Custom Field (just after `insert_after`), is added
    to a fresh meta of `dt` and is laid out by Frappe's own ordering, so the prediction follows
    the running version's rules (an unknown insert_after puts it at the end of the form). Same
    shape as ``location``. Nothing is written.

    Frappe reads custom fields ORDER BY idx with no tie-break, so when another custom field
    already sits at the new field's idx (a second field added after the same one) the database
    decides their order and the prediction can differ: see placement_is_ambiguous. The probe
    goes first on a tie.
    """
    probe = {
        "doctype": "Custom Field",
        "dt": dt,
        "fieldname": PROBE_FIELDNAME,
        "fieldtype": fieldtype or "Data",
        "label": PROBE_FIELDNAME,
        "insert_after": insert_after or None,
        "is_custom_field": 1,
    }
    idx = _new_field_idx(dt, insert_after)
    if idx:
        probe["idx"] = idx
    return locate_field(_ProbeMeta(dt, probe).fields, PROBE_FIELDNAME)


def is_hidden(location: Dict[str, Any]) -> bool:
    """Whether a field is easy to miss: in a collapsed section, or not on the first tab."""
    return bool(location.get("collapsed")) or not location.get("first_tab", True)


def placement_sentence(location: Dict[str, Any]) -> str:
    """Plain-language description of where a field shows, labels translated as Desk does."""
    tab = _(location["tab"]) if location.get("tab") else None
    section = _(location["section"]) if location.get("section") else None
    if tab and section:
        sentence = _("Will appear on the {0} tab, in the {1} section").format(tab, section)
    elif tab:
        sentence = _("Will appear on the {0} tab").format(tab)
    elif section:
        sentence = _("Will appear in the {0} section").format(section)
    else:
        sentence = _("Will appear on the form")
    if location.get("collapsed"):
        sentence += " " + _("(collapsed, hidden until someone opens it)")
    return sentence


def placement_warning(location: Dict[str, Any]) -> Optional[str]:
    """A sentence to show when the field is hidden away: collapsed, or not on the first tab."""
    if not is_hidden(location):
        return None
    collapsed = bool(location.get("collapsed"))
    if collapsed and not location.get("first_tab", True):
        reason = _("People may not notice it: the section is collapsed and the tab is not the first one.")
    elif collapsed:
        reason = _("People may not notice it: the section is collapsed.")
    else:
        reason = _("People may not notice it: it is not on the first tab.")
    return f"{placement_sentence(location)}. {reason}"
