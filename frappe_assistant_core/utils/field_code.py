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

"""Code a form field's definition carries: ``eval:`` display conditions and an HTML field's markup.

A field definition is a Custom Field, a Property Setter on a field, or a DocType's own field row.
``utils/customisation.py`` compares what these return before and after a write to decide whether
the write changes code that runs for other people.
"""

from typing import Any, Callable, Dict, Iterable, Optional

import frappe

from frappe_assistant_core.chat.api.current_code import DEPENDS_ON_KEYS

# Fieldtypes whose options the form renders as markup. ControlHTML (frappe/public/js/frappe/form/
# controls/html.js, get_content and _set_html) passes df.options through frappe.render, which
# compiles {% %} blocks into a JavaScript function (microtemplate.js, new Function), and puts the
# result on the form with jQuery's .html(), which runs any <script> in it; the standard print view
# renders it again as Jinja (templates/print_formats/standard_macros.html, render_field). Other
# fieldtypes' options are no markup: an HTML Editor's options is its editor language, set to
# "HTML" by html_editor.js, and its preview renders the field's value with scripts stripped; a
# Heading renders its label; a Button's options names a whitelisted method, already code on the
# server; a Link's or Select's options names a DocType or lists choices.
HTML_FIELDTYPES = frozenset({"HTML"})


def is_eval(value: Any) -> bool:
    """Whether a display condition is code: Frappe's form runs the text after ``eval:`` as JavaScript."""
    return isinstance(value, str) and value.lstrip().startswith("eval:")


def field_code(values: Callable[[str], Any]) -> tuple:
    """The code a field definition carries: each ``eval:`` condition, then an HTML field's options.

    A blank entry is no code. ``values`` reads one property of the definition.
    """
    conditions = tuple(values(key) if is_eval(values(key)) else "" for key in DEPENDS_ON_KEYS)
    html = (values("options") or "") if values("fieldtype") in HTML_FIELDTYPES else ""
    return (*conditions, html)


def _fieldtype(doctype: Any, fieldname: Any) -> Optional[str]:
    """The fieldtype a DocType's field has after its Custom Fields and Property Setters, or None."""
    if not (isinstance(doctype, str) and doctype and isinstance(fieldname, str) and fieldname):
        return None
    try:
        field = frappe.get_meta(doctype).get_field(fieldname)
    except frappe.DoesNotExistError:
        return None
    return field.fieldtype if field else None


def property_setter_code(values: Callable[[str], Any]) -> bool:
    """Whether a Property Setter's value is code.

    An ``eval:`` display condition is, and so are the options of an HTML field, since the form
    renders them (``HTML_FIELDTYPES``). A field that cannot be found counts as HTML, so any doubt
    shows the card. A Property Setter that turns a field into an HTML field counts as well: the
    field's options start to render.
    """
    prop, value = values("property"), values("value")
    if prop in DEPENDS_ON_KEYS:
        return is_eval(value)
    if prop == "fieldtype":
        return value in HTML_FIELDTYPES
    if prop == "options":
        fieldtype = _fieldtype(values("doc_type"), values("field_name"))
        return bool(value) and (fieldtype is None or fieldtype in HTML_FIELDTYPES)
    return False


def rows_field_code(rows: Iterable[Dict[str, Any]]) -> Optional[Dict[str, tuple]]:
    """``{fieldname: field_code}`` for the DocType field rows that carry code.

    None when a row that carries code has no plain fieldname, or shares it with another such row:
    its code cannot be told apart, so the caller counts it as a change.
    """
    out: Dict[str, tuple] = {}
    for row in rows:
        code = field_code(row.get)
        if not any(code):
            continue
        fieldname = row.get("fieldname")
        if not (isinstance(fieldname, str) and fieldname) or fieldname in out:
            return None
        out[fieldname] = code
    return out


def resulting_rows(sent: Any, stored_rows: list) -> Optional[list]:
    """The child rows a table holds once update_document applies ``sent`` to ``stored_rows``.

    As ``_apply_child_table_update`` in plugins/core/tools/update_document.py: with no named row
    (replace mode) the sent rows replace the table; with any (patch mode) a named row updates the
    stored row of that name, or is removed when it carries ``_delete``, a row without a name is
    appended, and rows not sent stay. None when the rows cannot be read or name a row that is not
    stored (update_document refuses those), so the caller counts it as a change.
    """
    if not isinstance(sent, list) or not all(isinstance(row, dict) for row in sent):
        return None
    if not any(row.get("name") for row in sent):
        return sent
    by_name: Dict[str, Optional[Dict[str, Any]]] = {row["name"]: dict(row) for row in stored_rows}
    appended = []
    for row in sent:
        name = row.get("name")
        if not name:
            appended.append(row)
        elif name not in by_name or by_name[name] is None:
            return None
        elif row.get("_delete"):
            by_name[name] = None
        else:
            by_name[name].update({key: value for key, value in row.items() if key not in ("name", "_delete")})
    return [row for row in by_name.values() if row is not None] + appended


# The field properties that can carry code, and the columns read to judge them.
_CODE_PROPERTIES = (*DEPENDS_ON_KEYS, "options")
_FIELD_COLUMNS = ("name", "fieldname", "fieldtype", "options", *DEPENDS_ON_KEYS)


def code_on_doctype(name: str) -> list:
    """Every piece of code on a DocType's form, as its form would run it, one entry per value.

    The DocType's own field rows, its Custom Fields, and its Property Setters on a field's
    conditions, options or fieldtype, applied over the field they change as Frappe's meta applies
    them. Each entry is ``{"source", "name", "field", "key", "code"}``: the record that sets the
    value (``DocType``, ``Custom Field`` or ``Property Setter``), that record's name, the field and
    property, and the code (``field_code``: an ``eval:`` condition or an HTML field's options).
    """
    fields: Dict[str, Dict[str, Any]] = {}
    for source, rows in (
        ("DocType", _rows("DocField", {"parent": name, "parenttype": "DocType", "parentfield": "fields"})),
        ("Custom Field", _rows("Custom Field", {"dt": name})),
    ):
        for row in rows:
            values = {key: row.get(key) for key in _FIELD_COLUMNS}
            origin = {key: (source, row.name) for key in (*_CODE_PROPERTIES, "fieldtype")}
            fields[row.fieldname or row.name] = {"values": values, "origin": origin}
    setters = frappe.get_all(
        "Property Setter",
        filters={
            "doc_type": name,
            "doctype_or_field": "DocField",
            "property": ["in", (*_CODE_PROPERTIES, "fieldtype")],
        },
        fields=["name", "field_name", "property", "value"],
        order_by="creation asc",
    )
    for setter in setters:
        # A field found nowhere else counts as an HTML field, as in property_setter_code: any doubt
        # shows the code.
        field = fields.setdefault(
            setter.field_name,
            {"values": {"fieldname": setter.field_name, "fieldtype": "HTML"}, "origin": {}},
        )
        field["values"][setter.property] = setter.value
        field["origin"][setter.property] = ("Property Setter", setter.name)
    entries = []
    for fieldname, field in fields.items():
        code = field_code(field["values"].get)
        for key, value in zip(_CODE_PROPERTIES, code):
            if not value:
                continue
            origin = field["origin"].get(key, ("Property Setter", ""))
            # Options a Property Setter turned into an HTML field's markup is code because of it.
            if key == "options" and field["origin"].get("fieldtype", ("",))[0] == "Property Setter":
                origin = field["origin"]["fieldtype"]
            entries.append(
                {"source": origin[0], "name": origin[1], "field": fieldname, "key": key, "code": value}
            )
    return entries


def _rows(doctype: str, filters: Dict[str, Any]) -> list:
    return frappe.get_all(doctype, filters=filters, fields=list(_FIELD_COLUMNS), order_by="idx asc")
