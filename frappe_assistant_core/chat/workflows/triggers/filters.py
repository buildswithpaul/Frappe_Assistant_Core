# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Filter evaluation, changed-field detection, and payload construction.

All functions are pure (no frappe DB writes) to make them easy to unit-test.
"""

import datetime
import json
import uuid
from decimal import Decimal
from typing import Any

import frappe
from frappe.utils import get_datetime, get_timedelta, now

DEFAULT_PAYLOAD_BYTE_CAP = 256 * 1024
DEFAULT_SECRET_FIELDNAME_BLOCKLIST = (
    "api_key",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "client_secret",
)


def evaluate_filters(doc_dict: dict[str, Any], filter_rows: list[Any]) -> bool:
    """Return True if ALL filter rows pass against the doc dict.

    Each row exposes .fieldname, .operator, .value (Frappe child-table rows).
    Empty/None filter list → True (no constraints).
    """
    return first_failing_filter(doc_dict, filter_rows) is None


def first_failing_filter(doc_dict: dict[str, Any], filter_rows: list[Any]) -> Any | None:
    """Return the first row that does not pass, or None when all of them do.

    Filters are AND-only, so the first failure is the whole reason the trigger
    did not fire — which is what the dispatcher names in its log row.
    """
    if not filter_rows:
        return None

    for row in filter_rows:
        if not _row_passes(doc_dict, row):
            return row
    return None


def _row_passes(doc_dict: dict[str, Any], row: Any) -> bool:
    op = (row.operator or "").strip()
    fieldname = (row.fieldname or "").strip()
    raw_value = row.value if row.value is not None else ""

    if not fieldname or not op:
        return False

    actual = doc_dict.get(fieldname)

    if op == "is set":
        return actual not in (None, "", [])
    if op == "is not set":
        return actual in (None, "", [])

    if op in ("in", "not in"):
        try:
            expected_list = json.loads(raw_value) if raw_value else []
        except (ValueError, TypeError):
            # Fallback: comma-separated
            expected_list = [v.strip() for v in str(raw_value).split(",") if v.strip()]
        if not isinstance(expected_list, list):
            expected_list = [expected_list]
        # Compare as strings for robustness across types
        actual_str = str(actual) if actual is not None else ""
        expected_strs = [str(v) for v in expected_list]
        matches = actual_str in expected_strs
        return matches if op == "in" else not matches

    # Comparison operators
    if op in ("=", "!="):
        match = str(actual) == str(raw_value)
        return match if op == "=" else not match

    if op in (">", "<", ">=", "<="):
        return _ordered(actual, raw_value, op)

    return False


def _ordered(actual: Any, expected: Any, op: str) -> bool:
    """Evaluate an ordering operator with both sides coerced to one type.

    Coercing both sides with ``float()`` made every Date, Datetime, Time and
    Data comparison the filter UI actively invites fail and return False — and
    because filters are AND-only, one such row silently killed the trigger.
    """
    if actual in (None, "") or expected in (None, ""):
        # A missing value has no position in an ordering. Answering "absent
        # equals zero" is what made `amount < 100` match unset amounts.
        return False

    pair = _as_numbers(actual, expected) or _as_temporal(actual, expected)
    if pair is None:
        pair = (str(actual), str(expected))

    a, b = pair
    if op == ">":
        return a > b
    if op == "<":
        return a < b
    if op == ">=":
        return a >= b
    return a <= b


def _as_numbers(actual: Any, expected: Any) -> tuple[float, float] | None:
    """Both sides as floats, or None when either side is not numeric."""
    try:
        return (float(actual), float(expected))
    except (ValueError, TypeError):
        return None


def _as_temporal(actual: Any, expected: Any) -> tuple[Any, Any] | None:
    """Both sides as datetimes (or timedeltas), or None when not applicable.

    Driven off the *stored* value's type: MariaDB hands back real date /
    datetime / timedelta objects for those fieldtypes, while the filter row's
    value is always a string. Parsing an ordinary Data value as a date instead
    would let dateutil read "5" as the 5th of the current month.
    """
    if isinstance(actual, datetime.timedelta):
        parsed = _safe(get_timedelta, expected)
        return (actual, parsed) if isinstance(parsed, datetime.timedelta) else None

    if isinstance(actual, datetime.datetime | datetime.date):
        left = _safe(get_datetime, actual)
        right = _safe(get_datetime, expected)
        if isinstance(left, datetime.datetime) and isinstance(right, datetime.datetime):
            return (left, right)
        return None

    return None


def _safe(parser: Any, value: Any) -> Any:
    """Run a Frappe date parser, turning "cannot parse" into None."""
    try:
        return parser(value)
    except Exception:
        return None


def get_changed_fields(doc, watch_list: list[str]) -> dict[str, dict[str, Any]]:
    """Return {field: {old, new}} for watched fields that changed.

    Uses doc.get_doc_before_save() which is populated by Frappe on on_update.
    Returns empty dict on insert (no prior version).
    """
    if not watch_list:
        return {}

    before = None
    if hasattr(doc, "get_doc_before_save"):
        before = doc.get_doc_before_save()

    if before is None:
        # No prior version — treat all watched fields as unchanged
        return {}

    changed: dict[str, dict[str, Any]] = {}
    for field in watch_list:
        field = field.strip()
        if not field:
            continue
        old_value = before.get(field) if isinstance(before, dict) else getattr(before, field, None)
        new_value = doc.get(field) if hasattr(doc, "get") else getattr(doc, field, None)
        if old_value != new_value:
            changed[field] = {"old": old_value, "new": new_value}
    return changed


def parse_changed_fields_config(raw: str | None) -> list[str]:
    """Parse the Small Text field 'changed_fields' into a list of fieldnames."""
    if not raw:
        return []
    return [f.strip() for f in raw.split(",") if f.strip()]


def build_payload(
    trigger,
    doc,
    event: str,
    changed_fields: dict[str, dict[str, Any]],
    secret_blocklist: tuple = DEFAULT_SECRET_FIELDNAME_BLOCKLIST,
    byte_cap: int = DEFAULT_PAYLOAD_BYTE_CAP,
) -> dict[str, Any]:
    """Build the JSON-serializable payload sent to AR.

    Structure: {trigger, doc, changed_fields}. Strips Password fields (parent
    and child rows) and secret_blocklist fieldnames. Over ``byte_cap`` child
    tables are dropped largest-first, named in ``dropped_child_tables``; only
    a parent that is still too big on its own falls back to a minimal doc.
    """
    payload = {
        "trigger": {
            "source": "doc_event",
            "trigger_id": trigger.name,
            "event": event,
            "doctype": doc.doctype,
            "docname": doc.name,
            "user": frappe.session.user,
            "fired_at": now(),
            "site": frappe.local.site if hasattr(frappe.local, "site") else "",
        },
        "doc": _sanitize_doc(doc, secret_blocklist),
        "changed_fields": _coerce_changed_fields(changed_fields),
    }

    try:
        if _json_size(payload) <= byte_cap:
            return payload
    except (TypeError, ValueError):
        payload["doc"] = _minimal_doc(doc)
        payload["doc_truncated"] = True
        return payload

    payload["doc_truncated"] = True
    dropped = _drop_child_tables(payload, byte_cap)
    if dropped:
        payload["dropped_child_tables"] = dropped
    if _json_size(payload) > byte_cap:
        payload["doc"] = _minimal_doc(doc)
        payload.pop("dropped_child_tables", None)
    return payload


def _json_size(value: Any) -> int:
    """Serialized size in bytes. default=str only measures; it never ships."""
    return len(json.dumps(value, default=str).encode("utf-8"))


def _drop_child_tables(payload: dict[str, Any], byte_cap: int) -> list[str]:
    """Remove child tables, largest first, until the payload fits. Returns their fieldnames."""
    doc = payload["doc"]
    tables = sorted(
        (key for key, value in doc.items() if isinstance(value, list)),
        key=lambda key: _json_size(doc[key]),
        reverse=True,
    )
    dropped = []
    for key in tables:
        if _json_size(payload) <= byte_cap:
            break
        doc.pop(key)
        dropped.append(key)
    return dropped


def _coerce_changed_fields(changed_fields: dict[str, dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """{field: {old, new}} with JSON-native values (dates, Decimals and timedeltas included)."""
    return {
        field: {side: _coerce_json_native(value) for side, value in (change or {}).items()}
        for field, change in (changed_fields or {}).items()
    }


def _coerce_json_native(value: Any) -> Any:
    """Coerce non-JSON-native values into JSON-native equivalents.

    The trigger payload travels through SDK serialization and over HTTP, so
    any dict-leaf must round-trip cleanly through ``json.dumps`` without
    requiring a custom encoder on the receiving side.

    Frappe's ``as_dict()`` can return UUIDs (newer Frappe naming), Decimals
    (currency fields), datetimes/dates, and bytes. None of these survive
    default ``json.dumps``. We stringify them at the source so AR doesn't
    have to deal with type drift.
    """
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime.datetime | datetime.date | datetime.time):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        # MariaDB returns Time/Duration columns as timedelta (e.g. posting_time)
        return str(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    return value


def _sanitize_doc(doc, secret_blocklist: tuple) -> dict[str, Any]:
    """Return doc.as_dict() without Password fields (parent and child rows) or blocklisted keys."""
    try:
        raw = doc.as_dict()
    except Exception:
        return {"name": getattr(doc, "name", None)}

    password_cache: dict[str, set[str]] = {}
    password_fields = _password_fields(doc.doctype, password_cache)
    blocklist_lower = {b.lower() for b in secret_blocklist}

    sanitized: dict[str, Any] = {}
    for key, value in raw.items():
        if key in password_fields or key.lower() in blocklist_lower:
            continue
        if isinstance(value, list):
            sanitized[key] = [
                _sanitize_child(item, blocklist_lower, _password_fields(item.get("doctype"), password_cache))
                if isinstance(item, dict)
                else _coerce_json_native(item)
                for item in value
            ]
        else:
            sanitized[key] = _coerce_json_native(value)
    return sanitized


def _password_fields(doctype: str | None, cache: dict[str, set[str]]) -> set[str]:
    """Fieldnames of Password fields on ``doctype``; empty when the meta cannot be read."""
    if not doctype:
        return set()
    if doctype not in cache:
        try:
            meta = frappe.get_meta(doctype)
            cache[doctype] = {f.fieldname for f in meta.fields if f.fieldtype == "Password"}
        except Exception:
            cache[doctype] = set()
    return cache[doctype]


def _sanitize_child(item: dict[str, Any], blocklist_lower: set, password_fields: set[str]) -> dict[str, Any]:
    return {
        k: _coerce_json_native(v)
        for k, v in item.items()
        if k not in password_fields and k.lower() not in blocklist_lower
    }


def _minimal_doc(doc) -> dict[str, Any]:
    """Fallback for oversized docs: keep only identity + title."""
    try:
        meta = frappe.get_meta(doc.doctype)
        title_field = getattr(meta, "title_field", None)
    except Exception:
        title_field = None

    out: dict[str, Any] = {
        "name": getattr(doc, "name", None),
        "owner": getattr(doc, "owner", None),
        "creation": str(getattr(doc, "creation", "") or ""),
        "modified": str(getattr(doc, "modified", "") or ""),
        "modified_by": getattr(doc, "modified_by", None),
        "docstatus": getattr(doc, "docstatus", None),
    }
    if title_field:
        out[title_field] = getattr(doc, title_field, None)
    return out
