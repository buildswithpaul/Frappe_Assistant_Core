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
Child-table input handling shared by create_document and update_document.

Frappe has two child-table fieldtypes, ``Table`` and ``Table MultiSelect``
(``frappe.model.table_fields``), and both are lists of child documents. Both
write tools used to recognise only ``Table``, so a Table MultiSelect value was
assigned raw and the save failed on ``.is_new()`` (issue #291). Deciding it here,
once, keeps the two tools from disagreeing about what a child table is.
"""

from typing import Any, Dict, Iterable, List, Optional, Set

import frappe


class ChildRowError(ValueError):
    """A child-table value the tools cannot turn into rows."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field

    def as_result(self) -> Dict[str, Any]:
        return {
            "success": False,
            "error": str(self),
            "error_type": "child_table_handling_error",
            "field": self.field,
        }


def child_table_fields(meta) -> Dict[str, Any]:
    """Every child-table field on ``meta`` by fieldname: Table and Table MultiSelect alike."""
    return {df.fieldname: df for df in meta.get_table_fields()}


def multiselect_link_field(child_doctype: str) -> Optional[str]:
    """The field a Table MultiSelect row keeps its value in.

    Desk uses the child doctype's first Link field (``get_link_field`` in
    table_multiselect.js), and DocType validation guarantees there is one. Using
    the same rule means a list of values here saves exactly what Desk would.
    """
    return next(
        (df.fieldname for df in frappe.get_meta(child_doctype).fields if df.fieldtype == "Link"),
        None,
    )


def normalize_child_rows(df, value: Any) -> List[Dict[str, Any]]:
    """Turn a tool's value for child-table field ``df`` into row dicts for ``doc.append``.

    Rows are copied, because ``doc.append`` writes ``doctype`` into the dict it is
    given and the caller's input should come back as it went in. A Table
    MultiSelect also accepts a bare value, as Desk sends one, and it fills the
    child's link field. A plain Table has no single field a bare value could
    mean, so it still requires dicts.
    """
    field = df.fieldname

    if not isinstance(value, list):
        raise ChildRowError(
            field, f"Child table '{field}' requires a list of rows, got: {type(value).__name__}"
        )

    link_field = multiselect_link_field(df.options) if df.fieldtype == "Table MultiSelect" else None

    rows = []
    for row in value:
        if isinstance(row, dict):
            rows.append(dict(row))
        elif link_field and isinstance(row, str):
            rows.append({link_field: row})
        elif link_field:
            raise ChildRowError(
                field,
                f"Table MultiSelect '{field}' rows must be {link_field} values or dictionaries, "
                f"got: {type(row).__name__}",
            )
        else:
            raise ChildRowError(
                field, f"Child table '{field}' rows must be dictionaries, got: {type(row).__name__}"
            )

    return rows


def restricted_row_keys(rows: Iterable[Dict[str, Any]], restricted: Set[str]) -> List[str]:
    """The restricted keys any of ``rows`` tries to set, sorted and without repeats."""
    return sorted({key for row in rows for key in row if key in restricted})
