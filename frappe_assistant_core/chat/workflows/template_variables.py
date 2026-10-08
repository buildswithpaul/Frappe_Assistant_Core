# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Validate a template import's variables against the template's typed schema.

This runs on the tenant's own site because only this site can say whether a
Link value exists — FAC Cloud has no access to the tenant's database.
"""

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import validate_email_address

# Spellings that templates exported before typed variables still carry.
TYPE_ALIASES = {"string": "text", "data": "text", "integer": "int", "number": "float", "boolean": "check"}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class _InvalidValue(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def parse_schema(raw: str | dict | None) -> dict[str, dict]:
    """The template's variables_schema as {name: spec}; anything unreadable is empty."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except ValueError:
            return {}
    if not isinstance(raw, dict):
        return {}
    return {key: spec for key, spec in raw.items() if isinstance(spec, dict)}


def parse_variables(raw: str | dict | None) -> dict:
    """The import form's values as a dict. A non-object is a user error."""
    if raw in (None, ""):
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    if not isinstance(raw, dict):
        frappe.throw(_("Template settings must be sent as a JSON object."), frappe.ValidationError)
    return raw


def validate_template_variables(schema: dict[str, dict], values: dict[str, Any]) -> dict[str, Any]:
    """Return ``values`` coerced to their declared types, or throw naming every bad field."""
    errors: list[str] = []
    cleaned = dict(values)

    for key, spec in schema.items():
        label = spec.get("label") or key
        value = values.get(key)
        if _is_blank(value):
            cleaned.pop(key, None)
            if spec.get("required"):
                errors.append(_("{0} is required.").format(label))
            continue
        try:
            cleaned[key] = _coerce(spec, value)
        except _InvalidValue as e:
            errors.append(_("{0}: {1}").format(label, e.message))

    if errors:
        frappe.throw(errors, frappe.ValidationError, title=_("Check the template's settings"), as_list=True)
    return cleaned


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _kind(spec: dict) -> str:
    kind = str(spec.get("type") or "text").strip().lower()
    return TYPE_ALIASES.get(kind, kind)


def _coerce(spec: dict, value: Any) -> Any:
    kind = _kind(spec)
    text = str(value).strip()

    if kind == "int":
        if isinstance(value, bool) or not text.lstrip("-").isdigit():
            raise _InvalidValue(_("must be a whole number"))
        return int(text)

    if kind == "float":
        if isinstance(value, bool):
            raise _InvalidValue(_("must be a number"))
        try:
            return float(text)
        except ValueError:
            raise _InvalidValue(_("must be a number")) from None

    if kind == "check":
        if isinstance(value, bool):
            return int(value)
        if text.lower() in TRUE_VALUES:
            return 1
        if text.lower() in FALSE_VALUES:
            return 0
        raise _InvalidValue(_("must be checked or unchecked"))

    if kind == "email":
        if not validate_email_address(text):
            raise _InvalidValue(_("must be a valid email address"))
        return text

    if kind == "select":
        options = spec.get("options") or []
        if isinstance(options, str):
            options = [o for o in options.split("\n") if o.strip()]
        options = [str(o) for o in options]
        if text not in options:
            raise _InvalidValue(_("must be one of: {0}").format(", ".join(options)))
        return text

    if kind == "link":
        doctype = spec.get("options")
        if not doctype:
            return text
        if not frappe.db.exists("DocType", doctype):
            raise _InvalidValue(_("needs a {0}, which this site does not have").format(doctype))
        if not frappe.db.exists(doctype, text):
            raise _InvalidValue(_("{0} '{1}' does not exist on this site").format(_(doctype), text))
        return text

    return text
