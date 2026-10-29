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
(``applies_to``), where a new Custom Field shows on its form (``location``),
``customisation_result`` which puts those into a create or update tool result, and
``check_plan_changes`` which checks a build plan against the site before it is shown.
"""

from itertools import zip_longest
from typing import Any, Callable, Dict, Iterable, Optional

import frappe
from frappe import _
from frappe.model import data_fieldtypes, table_fields
from frappe.model.meta import Meta
from frappe.utils import cint, get_url, get_url_to_form

from frappe_assistant_core.assistant_core.doctype.fac_page.fac_page import (
    PERSONAL,
    SHARED,
    is_system_manager,
)
from frappe_assistant_core.chat.api.current_code import (
    CODE_KEYS_BY_DOCTYPE,
    DEPENDS_ON_KEYS,
    GO_LIVE_KEYS_BY_DOCTYPE,
    ROW_CODE_COLUMNS_BY_DOCTYPE,
    TABLE_COLUMNS,
)
from frappe_assistant_core.utils.field_code import (
    code_on_doctype,
    field_code,
    property_setter_code,
    resulting_rows,
    rows_field_code,
)

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
        "FAC Page",
    }
)

# Roles that do not count as "other people" when judging whether a customisation can be felt.
SYSTEM_ROLES = frozenset({"System Manager", "Administrator"})

# Doctype -> the flag that switches it off, and the value that means "off".
_SWITCH_FIELDS = {
    "Server Script": ("disabled", 1),
    "Client Script": ("enabled", 0),
    "Notification": ("enabled", 0),
    "FAC Page": ("published", 0),
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


def _is_plain_name(value: Any) -> bool:
    """Whether a record or DocType name is a non-empty string.

    Anything else (a dict, a list) acts as a filter once it reaches the database, so it could
    read another record's facts.
    """
    return isinstance(value, str) and bool(value)


def _stored_record(doctype: str, name: Optional[str]) -> Optional[Dict[str, Any]]:
    """The stored record's fields, or None when it does not exist."""
    if not _is_plain_name(name):
        return None
    return frappe.db.get_value(doctype, name, "*", as_dict=True) or None


def _is_custom(name: str) -> int:
    return cint(frappe.db.get_value("DocType", name, "custom"))


# (doctype, fieldname) of each Frappe record that names a DocType it acts on, shows or reports on.
# An explicit list, not one read from the meta: a site has about 200 Link-to-DocType fields, many on
# large ledger tables with no index on that column, and probing them all took about 3 s on a dev site,
# inside the 5 s budget FAC Cloud gives the whole check. Every kind listed counts as in use, even when
# the record pointing at the DocType is itself dormant, so the check fails toward asking.
_DOCTYPE_REFERENCE_FIELDS = (
    ("Web Form", "doc_type"),
    ("Report", "ref_doctype"),
    ("Workspace Quick List", "document_type"),
    ("Dashboard Chart", "document_type"),
    ("Dashboard Chart", "parent_document_type"),
    ("Number Card", "document_type"),
    ("Number Card", "parent_document_type"),
    ("Notification", "document_type"),
    ("Kanban Board", "reference_doctype"),
    ("Calendar View", "reference_doctype"),
    ("Print Format", "doc_type"),
    ("Webhook", "webhook_doctype"),
    ("Server Script", "reference_doctype"),
    ("Client Script", "dt"),
    ("Workflow", "document_type"),
    ("Assignment Rule", "document_type"),
    ("Auto Repeat", "reference_doctype"),
    ("Document Naming Rule", "document_type"),
    ("DocType Layout", "document_type"),
    ("User Permission", "allow"),
    ("User Permission", "applicable_for"),
    ("Form Tour", "reference_doctype"),
    ("Onboarding Step", "reference_document"),
    ("Success Action", "ref_doctype"),
    ("Portal Menu Item", "reference_doctype"),
    ("Global Search DocType", "document_type"),
    ("List Filter", "reference_doctype"),
)


def _references_to(name: str) -> tuple:
    """(doctype, filters) for each kind of record that can point at the DocType ``name``.

    Fields: any field whose options name it, whatever its type, because a Property Setter can turn
    the field into a Link or Table, and a Property Setter that points a field's options at it.
    Connections links and Workspace links and shortcuts from elsewhere, and every record kind in
    ``_DOCTYPE_REFERENCE_FIELDS``. Only the DocType's own fields, Property Setters and Connections
    links to itself are left out.
    """
    return (
        ("DocField", {"options": name, "parent": ["!=", name]}),
        ("Custom Field", {"options": name, "dt": ["!=", name]}),
        ("Property Setter", {"property": "options", "value": name, "doc_type": ["!=", name]}),
        ("DocType Link", {"link_doctype": name, "parent": ["!=", name]}),
        ("Workspace Link", {"link_type": "DocType", "link_to": name}),
        ("Workspace Shortcut", {"type": "DocType", "link_to": name}),
        *((doctype, {fieldname: name}) for doctype, fieldname in _DOCTYPE_REFERENCE_FIELDS),
    )


def _referenced_elsewhere(name: str) -> bool:
    """Whether another form or a record other people open links to, embeds or reports on this DocType."""
    return any(
        frappe.get_all(doctype, filters=filters, pluck="name", limit=1)
        for doctype, filters in _references_to(name)
    )


# DocType properties that decide what kind of DocType it is. A DocType-level Property Setter can set
# them, and Frappe's meta applies it over the DocType row.
_KIND_PROPERTIES = frozenset({"istable", "issingle", "is_virtual"})


def _kind_is_overridden(name: str) -> bool:
    """Whether a Property Setter changes whether the DocType is a child table, Single or virtual."""
    return bool(
        frappe.get_all(
            "Property Setter",
            filters={"doc_type": name, "property": ["in", tuple(_KIND_PROPERTIES)]},
            pluck="name",
            limit=1,
        )
    )


def _stored_doctype(name: str) -> Optional[Dict[str, Any]]:
    """What decides whether a stored DocType is dormant, or None when it does not exist.

    A Single or virtual DocType has no table to count, so it is never reported custom (never
    dormant). `custom_roles` are the Custom DocPerm roles, which override the standard ones.
    `in_use` is true for a child table (it has no DocPerm rows and no records until a parent
    saves, yet shows inside its parent's form) and for a DocType that another form, or a record
    other people open, points at (see ``_references_to``): deleting it reaches them. The kind is
    read from the DocType row, so a Property Setter that changes it (``_KIND_PROPERTIES``) makes
    the DocType count as in use, whatever it sets: any doubt counts as live.
    """
    kind = (
        frappe.db.get_value("DocType", name, ["issingle", "is_virtual", "istable"], as_dict=True)
        if _is_plain_name(name)
        else None
    )
    if not kind:
        return None
    facts: Dict[str, Any] = {"custom": 0, "roles": [], "custom_roles": [], "records": 0, "in_use": False}
    if _kind_is_overridden(name):
        return {**facts, "in_use": True}
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
    return _stored_facts_are_dormant(_stored_doctype(name) if _is_plain_name(name) else None)


def _doctype_write_is_dormant(creating: bool, data: Dict[str, Any], stored: Optional[Dict[str, Any]]) -> bool:
    """Whether a DocType write is dormant before and after it (an error or a doubt is not).

    custom and the record count come from the stored DocType only, so data cannot turn a standard
    DocType custom. Supplied permissions replace the standard rows, but stored Custom DocPerm
    rows still apply. A write that makes it a child table is live, as a stored child table is
    (``_stored_doctype``): any form can then embed it, and its fields render there.
    """
    if cint(data.get("istable")):
        return False
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


_NOT_PLAIN_DOCTYPE = "The target DocType is not a plain name"


def _targets_are_plain(creating: bool, before: Any, after: Any, field: str) -> bool:
    """Whether the target DocType, stored and after the write, is a plain name."""
    return _is_plain_name(after(field)) and (creating or _is_plain_name(before(field)))


_LIVE_PAGE = {"dormant": False, "reason": "FAC Page opens for other people"}


def _personal_page_impact(
    creating: bool, data: Dict[str, Any], before: Callable[[str], Any], after: Callable[[str], Any]
) -> Optional[Dict[str, Any]]:
    """The impact of a write that touches a personal FAC Page, or None for a shared one throughout.

    A personal page opens, published or not, for its owner only. So a write is dormant when the
    page is personal before and after it and belongs to the session user, and live otherwise:
    someone else's page changes for them, and sharing a page opens it to other people.

    A personal page never ``switches_on`` and never ``changes_live_code``: it reaches its owner
    alone, and its script runs in a frame that reads only what they may and asks them before any
    change. Sharing a page
    switches it on when it is published after the write, since that opens it to its roles.
    """
    # PERSONAL is the schema default; reading it from the meta raises on a site not yet migrated.
    visibility = (data.get("visibility") or PERSONAL) if creating else after("visibility")
    was_personal = not creating and before("visibility") != SHARED
    user = frappe.session.user
    if visibility == SHARED and not was_personal:
        # Frappe refuses anyone else's shared-page write, so it cannot be dormant.
        return None if is_system_manager(user) else dict(_LIVE_PAGE)
    # A new page's owner is always the session user; Frappe overwrites any supplied owner.
    owned = creating or (before("owner") == user and after("owner") == user)
    if owned and visibility == PERSONAL and (creating or before("visibility") == PERSONAL):
        return {"dormant": True, "reason": _("only you can open this page")}
    return {**_LIVE_PAGE, "switches_on": visibility == SHARED and bool(cint(after("published")))}


def customisation_impact(tool_name: str, tool_input: Any) -> Dict[str, Any]:
    """Whether a customisation write changes nothing anyone but its builder can feel yet.

    Dormant: a switched-off script or notification, an unpublished shared FAC Page, a personal FAC
    Page its owner changes and keeps personal, or anything that only touches a custom DocType that
    nobody outside the system roles can reach, that holds no records and that is not a child table
    or used by another form. A write is dormant only when
    the stored state and the state after the write both are, so switching a script on, publishing
    a page or moving a field onto a live DocType is live, and any doubt counts as live.
    ``switches_on`` is true when the write turns a ``_SWITCH_FIELDS`` record from off to on,
    including a create saved switched on, and when it shares a personal FAC Page that is published
    after the write (``_personal_page_impact``). ``changes_live_code`` is true when an update changes a
    live field (``_live_fields``: code, templates and audience, such as a Report's roles, compared
    as a set; and code in child rows, ``ROW_CODE_COLUMNS_BY_DOCTYPE``, compared row by row) of a
    record that is live before and after the write, and when a create of a doctype without a switch
    (a Report, a Print Format, a Workflow) sets any live field. For a Custom Field or Property Setter
    on a live DocType it is true when the write changes an ``eval:`` display condition or an HTML
    field's options, which the form renders (``_changes_condition_code``), and for a DocType that is
    not dormant when the write leaves its own field rows with such code that did not run before
    (``_doctype_changes_field_code``). A write that opens a dormant DocType to other people, a
    DocType update or a Custom DocPerm write, sets it when any code lives on it, in its own fields,
    its Custom Fields or its Property Setters (``code_on_doctype``), as does making it a child
    table. FAC Cloud shows its card for either even when an approved build plan lists the write,
    so the user sees the final code.
    Never writes. The reason is plain words for logs and never repeats stored values.
    """
    result = _dormancy(tool_name, tool_input)
    result.setdefault("switches_on", False)
    result.setdefault("changes_live_code", False)
    return result


def _row_values(rows: Any, column: str) -> Optional[frozenset]:
    """The set of ``column`` values in sent child rows (dicts or bare values); None if not a list."""
    if not isinstance(rows, list):
        return None
    return frozenset(row.get(column) if isinstance(row, dict) else row for row in rows)


def _live_fields(doctype: str) -> tuple:
    """The fields of ``doctype`` whose value runs or reaches people: code, templates and audience."""
    return CODE_KEYS_BY_DOCTYPE.get(doctype, ()) + GO_LIVE_KEYS_BY_DOCTYPE.get(doctype, ())


def _non_empty(value: Any) -> bool:
    """Whether a sent value says something: text that is not blank, a child table with a row."""
    return bool(value.strip()) if isinstance(value, str) else bool(value)


def _row_code(row: Dict[str, Any], columns: tuple) -> tuple:
    return tuple(row.get(column) or "" for column in columns)


def _row_has_code(row: Dict[str, Any], columns: tuple) -> bool:
    return any(_non_empty(value) for value in _row_code(row, columns))


def _rows_carry_code(rows: Any, columns: tuple) -> bool:
    """Whether sent child rows set any code column; anything but a list of rows counts if it says anything."""
    if not isinstance(rows, list):
        return _non_empty(rows)
    return any(not isinstance(row, dict) or _row_has_code(row, columns) for row in rows)


def _carries_live_fields(doctype: str, data: Dict[str, Any]) -> bool:
    """Whether a create sets any live field of ``doctype``, or code in any of its child rows."""
    return any(_non_empty(data.get(field)) for field in _live_fields(doctype)) or any(
        _rows_carry_code(data.get(field), columns)
        for field, columns in ROW_CODE_COLUMNS_BY_DOCTYPE.get(doctype, {}).items()
        if field in data
    )


def _row_context(child_doctype: str, columns: tuple) -> tuple:
    """The child doctype's other value columns, which say where its code applies.

    A Workflow Transition's state, action, next_state and allowed role decide which move its condition
    gates, and a Notification Recipient's receiver decides whose email its cc rides on.
    """
    return tuple(
        df.fieldname
        for df in frappe.get_meta(child_doctype).fields
        if df.fieldtype in data_fieldtypes
        and df.fieldtype not in table_fields
        and df.fieldname not in columns
    )


def _stored_rows(child_doctype: str, doctype: str, parent: Any, field: str, columns: tuple) -> list:
    """The stored rows of a child table, in the order the form shows them."""
    return frappe.get_all(
        child_doctype,
        filters={"parent": parent, "parenttype": doctype, "parentfield": field},
        fields=["name", *columns],
        order_by="idx asc",
    )


def _code_row_changed(
    row: Dict[str, Any], stored_row: Dict[str, Any], columns: tuple, context: tuple
) -> bool:
    """Whether a sent named row changes a row that holds code, before or after: its code or where it applies."""
    if not (_row_has_code(row, columns) or _row_has_code(stored_row, columns)):
        return False
    return any(key in row and (row[key] or "") != (stored_row.get(key) or "") for key in (*columns, *context))


def _rows_change_code(rows: Any, stored_rows: list, columns: tuple, context: tuple) -> bool:
    """Whether sent child rows, applied as update_document applies them, change code or where it applies.

    A row that holds code before or after the write counts when its code or any of its ``context``
    columns changes, so moving an unchanged condition to another transition counts. With any named
    row (patch mode) a named row is compared with the stored row of that name, a row without one is
    appended and counts when it carries code, and a deleted row runs nothing. With none (replace
    mode) the table is refilled, so the rows are compared in order with the stored ones, and a row
    left out of the sent values counts as cleared. Rows that cannot be read count.
    """
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return True
    every = (*columns, *context)
    if not any(row.get("name") for row in rows):
        for row, stored_row in zip_longest(rows, stored_rows):
            sent, kept = row or {}, stored_row or {}
            if (_row_has_code(sent, columns) or _row_has_code(kept, columns)) and _row_code(
                sent, every
            ) != _row_code(kept, every):
                return True
        return False
    by_name = {row.name: row for row in stored_rows}
    for row in rows:
        if row.get("_delete"):
            continue
        stored_row = by_name.get(row.get("name"))
        if stored_row is None:
            if _row_has_code(row, columns):
                return True
        elif _code_row_changed(row, stored_row, columns, context):
            return True
    return False


def _changes_live_fields(doctype: str, data: Dict[str, Any], stored: Dict[str, Any]) -> bool:
    """Whether ``data`` gives a code or go-live field of ``doctype`` a value other than the stored one.

    An audience table (``TABLE_COLUMNS``) is compared as the set of its rows' values, so reordering
    rows is no change and rows that cannot be read count as one. A table whose rows hold code
    (``ROW_CODE_COLUMNS_BY_DOCTYPE``) is compared row by row (``_rows_change_code``), so an edited
    condition on one Workflow transition, or an unchanged one moved to another, counts.
    """
    for field, columns in ROW_CODE_COLUMNS_BY_DOCTYPE.get(doctype, {}).items():
        if field not in data:
            continue
        child_doctype = frappe.get_meta(doctype).get_field(field).options
        context = _row_context(child_doctype, columns)
        stored_rows = _stored_rows(child_doctype, doctype, stored.get("name"), field, (*columns, *context))
        if _rows_change_code(data[field], stored_rows, columns, context):
            return True
    for field in _live_fields(doctype):
        if field not in data:
            continue
        if field in TABLE_COLUMNS:
            column = TABLE_COLUMNS[field]
            current = frappe.get_all(
                frappe.get_meta(doctype).get_field(field).options,
                filters={"parent": stored.get("name"), "parenttype": doctype, "parentfield": field},
                pluck=column,
            )
            if _row_values(data[field], column) != frozenset(current):
                return True
        elif (data[field] or "") != (stored.get(field) or ""):
            return True
    return False


def _condition_code(doctype: str, values: Callable[[str], Any]) -> tuple:
    """The code a Custom Field or Property Setter sets, with the field it runs on; empty when none.

    A Custom Field's ``eval:`` conditions and, for an HTML field, its options (``field_code``); a
    Property Setter's value when it is code (``property_setter_code``).
    """
    if doctype == "Custom Field":
        code = field_code(values)
        return (values("dt"), values("fieldname"), code) if any(code) else ()
    if property_setter_code(values):
        return (values("doc_type"), values("field_name"), values("property"), values("value"))
    return ()


def _changes_condition_code(
    doctype: str, creating: bool, before: Callable[[str], Any], after: Callable[[str], Any]
) -> bool:
    """Whether a Custom Field or Property Setter write adds, edits, moves or removes code in a field.

    That is an ``eval:`` condition or an HTML field's options (``field_code``). An HTML field's
    options is markup the form renders and runs (``HTML_FIELDTYPES`` cites the Frappe source), so
    any change to it counts, and so does turning a field with options into an HTML field. For a
    condition, only an ``eval:`` value is code. Frappe's form (``evaluate_depends_on_value`` in
    layout.js) runs the text after ``eval:`` as JavaScript for every user who opens the form, while a bare
    fieldname only reads that field's value and ``fn:`` calls a method the form's own scripts
    already define, so neither runs anything the write wrote. Changing one fieldname to another is
    therefore no code change, while any change on a side that holds an ``eval:`` expression is,
    as a cleared script is for the other code fields. Leading whitespace counts as ``eval:`` too:
    any doubt shows the card.
    """
    stored_code = () if creating else _condition_code(doctype, before)
    return _condition_code(doctype, after) != stored_code


# A DocType's field rows, with every column field_code reads.
_FIELD_ROW_COLUMNS = ("fieldname", "fieldtype", "options", *DEPENDS_ON_KEYS)


def _doctype_changes_field_code(
    creating: bool, data: Dict[str, Any], name: Any, stored_facts: Optional[Dict[str, Any]]
) -> bool:
    """Whether a DocType write that is not dormant leaves its fields with code nobody has seen live.

    Code is what ``field_code`` reads: ``eval:`` conditions and an HTML field's options, the same as
    on a Custom Field. Rows are compared by fieldname as the table stands once update_document has
    applied ``fields`` (``resulting_rows``: whole replacement or named rows), so code that is added,
    edited, removed or moved to another field counts, and reordering rows does not. A create, or an
    update that makes a dormant DocType reachable, counts any code its fields carry, since none of
    it ran for anyone before; an update that opens it counts the code its Custom Fields and Property
    Setters carry as well (``code_on_doctype``). Rows that cannot be read count.
    """
    stored_rows = [] if creating else _stored_rows("DocField", "DocType", name, "fields", _FIELD_ROW_COLUMNS)
    was_live = not creating and not _stored_facts_are_dormant(stored_facts)
    if was_live and "fields" not in data:
        return False
    after_rows = resulting_rows(data["fields"], stored_rows) if "fields" in data else stored_rows
    after = rows_field_code(after_rows) if after_rows is not None else None
    before = rows_field_code(stored_rows) if was_live else {}
    if after is None or before is None or after != before:
        return True
    return not creating and not was_live and bool(code_on_doctype(name))


def code_going_live(doctype: Any) -> list:
    """The code on a DocType that is dormant now, which a write opening it would put live.

    ``code_on_doctype``: its own fields', its Custom Fields' and its Property Setters' ``eval:``
    conditions and HTML markup, which ran for nobody while it was dormant. [] for a DocType that is
    already reachable, which showed its code when it went live.
    """
    return code_on_doctype(doctype) if _stored_doctype_is_dormant(doctype) else []


def _permission_opens_code(doctype: Any, role: Any) -> bool:
    """Whether a Custom DocPerm write opens a dormant DocType that carries code to another role."""
    return role not in SYSTEM_ROLES and bool(code_going_live(doctype))


def _dormancy(tool_name: str, tool_input: Any) -> Dict[str, Any]:
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

    if not creating and not _is_plain_name(name):
        return {"dormant": False, "reason": "The record name is not a plain name"}

    stored = None if creating else _stored_record(doctype, name)
    if not creating and stored is None:
        return {"dormant": False, "reason": "The record does not exist"}
    stored = stored or {}

    def before(field: str) -> Any:
        return stored.get(field)

    def after(field: str) -> Any:
        return data[field] if field in data else stored.get(field)

    if doctype == "FAC Page":
        personal = _personal_page_impact(creating, data, before, after)
        if personal:
            return personal

    if doctype in _SWITCH_FIELDS:
        field, off = _SWITCH_FIELDS[doctype]
        value = _schema_default(doctype, field) if creating and data.get(field) is None else after(field)
        stored_off = creating or cint(before(field)) == off
        if stored_off and cint(value) == off:
            return {"dormant": True, "reason": f"{doctype} is switched off"}
        stays_on = not stored_off and cint(value) != off
        return {
            "dormant": False,
            "reason": f"{doctype} is switched on",
            "switches_on": stored_off,
            "changes_live_code": stays_on and _changes_live_fields(doctype, data, stored),
        }

    if doctype == "DocType":
        stored_facts = None if creating else _stored_doctype(name)
        if _doctype_write_is_dormant(creating, data, stored_facts):
            return {"dormant": True, "reason": "DocType is not reachable by anyone else yet"}
        return {
            "dormant": False,
            "reason": "DocType may be reachable by other people",
            "changes_live_code": _doctype_changes_field_code(creating, data, name, stored_facts),
        }

    if doctype in ("Custom Field", "Property Setter"):
        target_field = "dt" if doctype == "Custom Field" else "doc_type"
        code = _changes_condition_code(doctype, creating, before, after)
        if not _targets_are_plain(creating, before, after, target_field):
            return {"dormant": False, "reason": _NOT_PLAIN_DOCTYPE, "changes_live_code": code}
        if doctype == "Property Setter" and _KIND_PROPERTIES & {before("property"), after("property")}:
            # A child table can be embedded in any form; a Single or virtual DocType has no records
            # to count. Either way it may reach people now, with all the code on it.
            return {
                "dormant": False,
                "reason": "Property Setter changes what kind of DocType it is",
                "changes_live_code": code or bool(code_going_live(after(target_field))),
            }
        stored_ok = creating or _stored_doctype_is_dormant(before(target_field))
        if stored_ok and _stored_doctype_is_dormant(after(target_field)):
            return {"dormant": True, "reason": f"{doctype} changes a DocType nobody else can reach yet"}
        return {
            "dormant": False,
            "reason": f"{doctype} changes a DocType other people can reach",
            "changes_live_code": code,
        }

    if doctype == "Custom DocPerm":
        if not _targets_are_plain(creating, before, after, "parent"):
            return {"dormant": False, "reason": _NOT_PLAIN_DOCTYPE}
        stored_ok = creating or (
            before("role") in SYSTEM_ROLES and _stored_doctype_is_dormant(before("parent"))
        )
        if stored_ok and after("role") in SYSTEM_ROLES and _stored_doctype_is_dormant(after("parent")):
            return {"dormant": True, "reason": "Permission only covers system roles on a dormant DocType"}
        return {
            "dormant": False,
            "reason": "Permission may open a DocType to other people",
            "changes_live_code": _permission_opens_code(after("parent"), after("role")),
        }

    return {
        "dormant": False,
        "reason": f"{doctype} changes always count",
        "changes_live_code": (
            _carries_live_fields(doctype, data) if creating else _changes_live_fields(doctype, data, stored)
        ),
    }


_PLAN_ACTION_TOOLS = {"update": "update_document", "delete": "delete_document"}


def _plan_change_problem(doctype: Any, planned_doctypes: set) -> Optional[str]:
    """Why a plan entry cannot be written as listed: an unknown doctype or a child table."""
    if _is_plain_name(doctype) and doctype in planned_doctypes:
        return None
    kind = frappe.db.get_value("DocType", doctype, "istable") if _is_plain_name(doctype) else None
    if kind is None:
        return _(
            '{0} is not a doctype on this site. To create a new doctype, list it with doctype "DocType" and name "{0}".'
        ).format(doctype)
    if not cint(kind):
        return None
    problem = _(
        "{0} is a child table and is saved through its parent record; list the parent record instead."
    ).format(doctype)
    if doctype == "Has Role":
        problem += " " + _("For a role assignment, list an update of each User by name.")
    return problem


def _plan_entry_shares(change: Dict[str, Any]) -> bool:
    """Whether a plan entry says it sets the page to Shared, on the entry or in its data."""
    data = change.get("data") if isinstance(change.get("data"), dict) else {}
    return SHARED in (change.get("visibility"), data.get("visibility"))


def _plan_change_goes_live(change: Dict[str, Any]) -> bool:
    """Whether a plan entry goes live, correcting a dormant claim the stored state contradicts.

    A customisation doctype without a switch can never be dormant. An update or delete of a stored
    switchable record goes live unless that record is switched off now, and a FAC Page update that
    shares the page goes live. Anything else keeps the flag as sent, and a true flag is never turned
    false.
    """
    goes_live = bool(change.get("goes_live"))
    doctype = change.get("doctype")
    if goes_live or not _is_plain_name(doctype) or doctype not in CUSTOMISATION_DOCTYPES:
        return goes_live
    if doctype == "FAC Page" and change.get("action") == "update" and _plan_entry_shares(change):
        return True
    if doctype not in _SWITCH_FIELDS:
        return True
    action = change.get("action")
    tool_name = _PLAN_ACTION_TOOLS.get(action) if isinstance(action, str) else None
    name = change.get("name")
    if tool_name and _is_plain_name(name) and frappe.db.exists(doctype, name):
        return not customisation_impact(tool_name, {"doctype": doctype, "name": name, "data": {}})["dormant"]
    return goes_live


def check_plan_changes(changes: list[dict]) -> list[dict]:
    """Check each entry of a build plan against the site before the plan is shown.

    One result per change, numbered from 1 as FAC Cloud numbers them: ``problem`` is why the entry
    cannot be written as listed (None when it can) and ``goes_live`` is the entry's flag, corrected when the site shows a
    dormant claim cannot hold. Never writes.
    """
    planned_doctypes = {
        change.get("name")
        for change in changes
        if change.get("doctype") == "DocType"
        and change.get("action") == "create"
        and _is_plain_name(change.get("name"))
    }
    return [
        {
            "index": index,
            "problem": _plan_change_problem(change.get("doctype"), planned_doctypes),
            "goes_live": _plan_change_goes_live(change),
        }
        for index, change in enumerate(changes, start=1)
    ]


def desk_url(doctype: str, name: str) -> str:
    """Link to a record's form in Desk."""
    return get_url_to_form(doctype, name)


def fac_page_url(name: str) -> str:
    """Where a FAC Page opens in Desk, by record name (a personal page's name is not its slug)."""
    return get_url(f"/app/fac-pages/{name}")


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
    collapsed or off the first tab, and page_url for a FAC Page (``url`` stays its form).
    """
    details: Dict[str, Any] = {}
    customised = applies_to(doctype, doc)
    if customised:
        details["applies_to"] = customised
    if doctype == "FAC Page":
        details["page_url"] = fac_page_url(doc.name)
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
