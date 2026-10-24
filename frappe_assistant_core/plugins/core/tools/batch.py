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
Many records in one create_document, update_document or delete_document call.

Each record goes through the tool's own single-record path, so a batch is checked exactly
as the same records sent one at a time would be. Each record runs inside its own savepoint,
so a record that fails partway leaves nothing behind; the whole batch runs inside another,
so ``all_or_nothing`` can undo the records that were already saved.
"""

from typing import Any, Callable, Dict, List, Optional

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import exception_message
from frappe_assistant_core.utils.customisation import CUSTOMISATION_DOCTYPES
from frappe_assistant_core.utils.savepoint import open_savepoint, release_savepoint, rollback_to_savepoint

MAX_BATCH_SIZE = 100
ALL_OR_NOTHING = "all_or_nothing"
CONTINUE = "continue"

_BATCH_SAVEPOINT = "fac_batch"
_RECORD_SAVEPOINT = "fac_batch_record"

# What a single-record result says about that record; its advice to the model is per call.
_RECORD_KEYS = (
    "name",
    "url",
    "docstatus",
    "submitted",
    "submit_error",
    "error",
    "error_type",
    "missing_fields",
    "field",
    "warnings",
)

MODE_SCHEMA = {
    "type": "string",
    "enum": [ALL_OR_NOTHING, CONTINUE],
    "default": ALL_OR_NOTHING,
    "description": (
        "For a batch: all_or_nothing saves nothing if any record fails; continue saves the "
        "records that pass and reports each failure."
    ),
}


def batch_refusal(doctype: str, items: Any, field: str, mode: Any) -> Optional[Dict[str, Any]]:
    """The error for a batch this tool will not run, or None."""
    error = None
    if not isinstance(items, list) or not items:
        error = _("'{0}' must be a non-empty list.").format(field)
    elif len(items) > MAX_BATCH_SIZE:
        error = _(
            "A batch can hold at most {0} records; this one has {1}. Split it into smaller batches."
        ).format(MAX_BATCH_SIZE, len(items))
    elif mode not in (ALL_OR_NOTHING, CONTINUE):
        error = _("mode must be '{0}' or '{1}'.").format(ALL_OR_NOTHING, CONTINUE)
    elif doctype in CUSTOMISATION_DOCTYPES:
        # Each customisation write gets its own preview and approval, which a batch would skip.
        error = _("{0} records change how the site works, so they are written one at a time.").format(doctype)
    if error is None:
        return None
    return {"success": False, "error": error, "error_type": "invalid_batch", "doctype": doctype}


def _record_entry(index: int, label: str, result: Dict[str, Any]) -> Dict[str, Any]:
    entry = {"index": index, "record": label, "success": bool(result.get("success"))}
    entry.update({key: result[key] for key in _RECORD_KEYS if result.get(key) is not None})
    return entry


def _run_one(run_one: Callable[[Any], Dict[str, Any]], item: Any) -> Dict[str, Any]:
    try:
        return run_one(item)
    except Exception as e:
        return {"success": False, "error": exception_message(e)}


def run_batch(
    doctype: str,
    items: List[Any],
    run_one: Callable[[Any], Dict[str, Any]],
    label: Callable[[int, Any], str],
    mode: str,
) -> Dict[str, Any]:
    """Run ``run_one`` on every item and report each record's outcome."""
    results: List[Dict[str, Any]] = []
    batch_marks = open_savepoint(_BATCH_SAVEPOINT)

    for index, item in enumerate(items):
        marks = open_savepoint(_RECORD_SAVEPOINT)
        entry = _record_entry(index, label(index, item), _run_one(run_one, item))
        if entry["success"]:
            release_savepoint(_RECORD_SAVEPOINT)
            results.append(entry)
            continue

        rollback_to_savepoint(_RECORD_SAVEPOINT, marks, doctype, entry.get("name"))
        if mode == ALL_OR_NOTHING:
            undone = rollback_to_savepoint(_BATCH_SAVEPOINT, batch_marks, doctype, None)
            return _batch_failure(doctype, items, entry, results, undone)
        results.append(entry)

    release_savepoint(_BATCH_SAVEPOINT)
    return _batch_summary(doctype, mode, results)


def run_validation(
    doctype: str,
    items: List[Any],
    run_one: Callable[[Any], Dict[str, Any]],
    label: Callable[[int, Any], str],
) -> Dict[str, Any]:
    """Dry-run every item, each of which undoes its own writes, and report every error."""
    results = [
        _record_entry(index, label(index, item), _run_one(run_one, item)) for index, item in enumerate(items)
    ]
    failed = [entry for entry in results if not entry["success"]]
    return {
        "success": not failed,
        "validation_passed": not failed,
        "doctype": doctype,
        "total": len(results),
        "failed": len(failed),
        "results": results,
        "message": (
            _("All {0} records passed validation. Nothing was saved.").format(len(results))
            if not failed
            else _("{0} of {1} records failed validation. Nothing was saved.").format(
                len(failed), len(results)
            )
        ),
    }


def _batch_failure(
    doctype: str,
    items: List[Any],
    failed: Dict[str, Any],
    saved_before: List[Dict[str, Any]],
    undone: bool,
) -> Dict[str, Any]:
    if undone:
        outcome = _("Nothing was saved.")
    else:
        # Only a commit inside a record removes the batch savepoint, and that commit kept what came before it.
        outcome = _("Some earlier records may already be saved; check them before retrying: {0}").format(
            ", ".join(entry["record"] for entry in saved_before) or _("none")
        )
    return {
        "success": False,
        "doctype": doctype,
        "mode": ALL_OR_NOTHING,
        "error": f"{failed['record']}: {failed.get('error', _('failed'))} {outcome}",
        "error_type": failed.get("error_type", "batch_record_failed"),
        "failed_record": failed,
        "total": len(items),
        "all_undone": undone,
        "suggestion": _(
            "Fix that record and send the batch again, or pass mode='continue' to save the records that pass."
        ),
    }


def _batch_summary(doctype: str, mode: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    failed = [entry for entry in results if not entry["success"]]
    succeeded = len(results) - len(failed)
    if not failed:
        message = _("All {0} records succeeded.").format(len(results))
    else:
        message = _("{0} of {1} records succeeded; {2} failed and were not saved.").format(
            succeeded, len(results), len(failed)
        )
    return {
        "success": succeeded > 0,
        "doctype": doctype,
        "mode": mode,
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(failed),
        "results": results,
        "message": message,
    }
