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

# Roles that do not count as "other people" when judging whether a customisation can be felt.
SYSTEM_ROLES = frozenset({"System Manager", "Administrator"})

# Doctype -> the flag that switches it off, and the value that means "off".
_SWITCH_FIELDS = {
    "Server Script": ("disabled", 1),
    "Client Script": ("enabled", 0),
    "Notification": ("enabled", 0),
}

_WRITE_TOOLS = frozenset({"create_document", "update_document", "delete_document"})

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


def _stored_record(doctype: str, name: Optional[str]) -> Optional[Dict[str, Any]]:
    """The stored record's fields, or None when it does not exist."""
    if not name:
        return None
    return frappe.db.get_value(doctype, name, "*", as_dict=True) or None


def _is_custom(name: str) -> int:
    return cint(frappe.db.get_value("DocType", name, "custom"))


# Field types through which another form links to or embeds a DocType.
_REFERENCE_FIELDTYPES = ("Link", "Table", "Table MultiSelect")


def _referenced_elsewhere(name: str) -> bool:
    """Whether a field on another DocType links to or embeds this one."""
    filters = {"fieldtype": ["in", _REFERENCE_FIELDTYPES], "options": name}
    return bool(
        frappe.get_all("DocField", filters={**filters, "parent": ["!=", name]}, pluck="name", limit=1)
        or frappe.get_all("Custom Field", filters={**filters, "dt": ["!=", name]}, pluck="name", limit=1)
    )


def _stored_doctype(name: str) -> Optional[Dict[str, Any]]:
    """What decides whether a stored DocType is dormant, or None when it does not exist.

    A Single or virtual DocType has no table to count, so it is never reported custom (never
    dormant). `custom_roles` are the Custom DocPerm roles, which override the standard ones.
    `in_use` is true for a child table (it has no DocPerm rows and no records until a parent
    saves, yet shows inside its parent's form) and for a DocType another form links to or embeds:
    deleting it reaches those forms.
    """
    kind = (
        frappe.db.get_value("DocType", name, ["issingle", "is_virtual", "istable"], as_dict=True)
        if name
        else None
    )
    if not kind:
        return None
    facts: Dict[str, Any] = {"custom": 0, "roles": [], "custom_roles": [], "records": 0, "in_use": False}
    if cint(kind.issingle) or cint(kind.is_virtual):
        return facts
    facts["custom"] = _is_custom(name)
    if facts["custom"]:
        facts["in_use"] = bool(cint(kind.istable)) or _referenced_elsewhere(name)
        facts["custom_roles"] = frappe.get_all("Custom DocPerm", filters={"parent": name}, pluck="role")
        standard_roles = frappe.get_all("DocPerm", filters={"parent": name}, pluck="role")
        facts["roles"] = standard_roles + facts["custom_roles"]
        facts["records"] = frappe.db.count(name)
    return facts


def _doctype_is_dormant(custom: int, roles: Iterable[Optional[str]], records: int) -> bool:
    """A custom DocType nobody outside the system roles can reach, with no records yet."""
    return bool(custom) and not records and all(role in SYSTEM_ROLES for role in roles)


def _stored_facts_are_dormant(facts: Optional[Dict[str, Any]]) -> bool:
    """Whether a stored DocType is dormant: no other form uses it and nobody else can reach it."""
    return (
        bool(facts)
        and not facts["in_use"]
        and _doctype_is_dormant(facts["custom"], facts["roles"], facts["records"])
    )


def _stored_doctype_is_dormant(name: Optional[str]) -> bool:
    return _stored_facts_are_dormant(_stored_doctype(name) if name else None)


def _doctype_write_is_dormant(creating: bool, data: Dict[str, Any], stored: Optional[Dict[str, Any]]) -> bool:
    """Whether a DocType write is dormant before and after it (an error or a doubt is not).

    custom and the record count come from the stored DocType only, so data cannot turn a standard
    DocType custom. Supplied permissions replace the standard rows, but stored Custom DocPerm
    rows still apply.
    """
    if creating:
        roles = [row.get("role") for row in data.get("permissions") or [] if isinstance(row, dict)]
        return _doctype_is_dormant(cint(data.get("custom")), roles, 0)
    if not _stored_facts_are_dormant(stored):
        return False
    if "permissions" not in data:
        return True
    supplied = [row.get("role") for row in data["permissions"] or [] if isinstance(row, dict)]
    return _doctype_is_dormant(stored["custom"], supplied + stored["custom_roles"], stored["records"])


def _schema_default(doctype: str, field: str) -> int:
    """The default a field takes when a new record leaves it out."""
    meta_field = frappe.get_meta(doctype).get_field(field)
    return cint(meta_field.default) if meta_field else 0


def customisation_impact(tool_name: str, tool_input: Any) -> Dict[str, Any]:
    """Whether a customisation write changes nothing anyone but its builder can feel yet.

    Dormant: a switched-off script or notification, or anything that only touches a custom
    DocType that nobody outside the system roles can reach, that holds no records and that is
    not a child table or used by another form. A write
    is dormant only when the stored state and the state after the write both are, so switching
    a script on or moving a field onto a live DocType is live, and any doubt counts as live.
    Never writes. The reason is plain words for logs and never repeats stored values.
    """
    if tool_name not in _WRITE_TOOLS or not isinstance(tool_input, dict):
        return {"dormant": False, "reason": "Not a customisation write"}
    doctype = tool_input.get("doctype")
    if doctype not in CUSTOMISATION_DOCTYPES:
        return {"dormant": False, "reason": "Not a customisation doctype"}

    data = tool_input.get("data")
    data = data if isinstance(data, dict) else {}
    name = tool_input.get("name")
    creating = tool_name == "create_document"
    if tool_name == "delete_document":
        data = {}

    stored = None if creating else _stored_record(doctype, name)
    if not creating and stored is None:
        return {"dormant": False, "reason": "The record does not exist"}
    stored = stored or {}

    def before(field: str) -> Any:
        return stored.get(field)

    def after(field: str) -> Any:
        return data[field] if field in data else stored.get(field)

    if doctype in _SWITCH_FIELDS:
        field, off = _SWITCH_FIELDS[doctype]
        value = _schema_default(doctype, field) if creating and data.get(field) is None else after(field)
        stored_off = creating or cint(before(field)) == off
        if stored_off and cint(value) == off:
            return {"dormant": True, "reason": f"{doctype} is switched off"}
        return {"dormant": False, "reason": f"{doctype} is switched on"}

    if doctype == "DocType":
        stored_facts = None if creating else _stored_doctype(name)
        if _doctype_write_is_dormant(creating, data, stored_facts):
            return {"dormant": True, "reason": "DocType is not reachable by anyone else yet"}
        return {"dormant": False, "reason": "DocType may be reachable by other people"}

    if doctype in ("Custom Field", "Property Setter"):
        target_field = "dt" if doctype == "Custom Field" else "doc_type"
        stored_ok = creating or _stored_doctype_is_dormant(before(target_field))
        if stored_ok and _stored_doctype_is_dormant(after(target_field)):
            return {"dormant": True, "reason": f"{doctype} changes a DocType nobody else can reach yet"}
        return {"dormant": False, "reason": f"{doctype} changes a DocType other people can reach"}

    if doctype == "Custom DocPerm":
        stored_ok = creating or (
            before("role") in SYSTEM_ROLES and _stored_doctype_is_dormant(before("parent"))
        )
        if stored_ok and after("role") in SYSTEM_ROLES and _stored_doctype_is_dormant(after("parent")):
            return {"dormant": True, "reason": "Permission only covers system roles on a dormant DocType"}
        return {"dormant": False, "reason": "Permission may open a DocType to other people"}

    return {"dormant": False, "reason": f"{doctype} changes always count"}


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
