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

"""Exact-match find/replace edits to long text and code fields, shared by the tools that patch them."""

from typing import Any, Dict, List, Optional

import frappe
from frappe import _

TEXT_FIELDTYPES = frozenset(
    {"Small Text", "Text", "Long Text", "Text Editor", "Markdown Editor", "HTML Editor", "Code", "JSON"}
)

_EDIT_KEYS = ("field", "find", "replace")


class EditError(ValueError):
    """An edit that cannot be applied; ``field`` names its field and ``count`` how often it matched."""

    def __init__(self, message: str, field: str, count: int = 0):
        super().__init__(message)
        self.field = field
        self.count = count


def _to_crlf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def apply_edits(current: Dict[str, Any], edits: List[Dict[str, str]]) -> Dict[str, str]:
    """Apply ``edits`` in order and return ``{field: new_value}`` for each field they touch.

    Each ``find`` is literal text and must match its field exactly once. A field stored with
    ``\\r\\n`` line endings keeps them: a bare ``\\n`` in ``find`` and ``replace`` is read as ``\\r\\n``.
    """
    values: Dict[str, str] = {}
    for edit in edits:
        field, find, replace = edit["field"], edit["find"], edit["replace"]
        value = values[field] if field in values else current.get(field)
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise EditError(_("'{0}' is not a text field").format(field), field)
        if not find:
            raise EditError(_("'{0}' is empty").format(field), field)
        if "\r\n" in value:
            find, replace = _to_crlf(find), _to_crlf(replace)
        count = value.count(find)
        if count != 1:
            raise EditError(
                _("'{0}' matched {1} times in {2}; it must match exactly once.").format(find, count, field),
                field,
                count,
            )
        values[field] = value.replace(find, replace, 1)
    return values


def edit_target_problem(doctype: str, edits: Any, data: Dict[str, Any]) -> Optional[str]:
    """Why ``edits`` cannot be applied to ``doctype`` alongside ``data``, or None."""
    if not (
        isinstance(edits, list)
        and edits
        and all(
            isinstance(edit, dict) and all(isinstance(edit.get(key), str) for key in _EDIT_KEYS)
            for edit in edits
        )
    ):
        return _("'edits' must be a list of {'field', 'find', 'replace'} objects with text values.")

    meta = frappe.get_meta(doctype)
    for field in dict.fromkeys(edit["field"] for edit in edits):
        if field in data:
            return _("'{0}' is in both 'edits' and 'data'; use one.").format(field)
        df = meta.get_field(field)
        if not df or df.fieldtype not in TEXT_FIELDTYPES:
            return _("'{0}' is not a long text or code field of {1}; edits only work on those.").format(
                field, doctype
            )
    return None


def effective_data(
    current: Dict[str, Any], data: Dict[str, Any], edits: List[Dict[str, str]]
) -> Dict[str, Any]:
    """``data`` with each edited field set to its edited value."""
    return {**data, **apply_edits(current, edits)}
