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

"""Find the reports that answer a question, instead of listing every report."""

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import frappe
from frappe import _

from frappe_assistant_core.plugins.core.tools.report_access import can_run_report, report_origin
from frappe_assistant_core.utils.search_tokens import tokens

DEFAULT_LIMIT = 10
MAX_LIMIT = 25
CUSTOM_BOOST = 1
PURPOSES_FILE = Path(__file__).resolve().parents[3] / "data" / "standard_report_purposes.json"


@lru_cache(maxsize=1)
def _standard_purposes() -> Dict[str, str]:
    return json.loads(PURPOSES_FILE.read_text(encoding="utf-8"))


def standard_report_purpose(report_name: str) -> Optional[str]:
    """One-line purpose of a standard report, or None when none is recorded."""
    return _standard_purposes().get(report_name)


def _score(query_tokens: set, report: Dict[str, Any], purpose: Optional[str]) -> int:
    """A word in the report's name counts double: the name is what the report is about."""
    name_hits = query_tokens & tokens(report.name)
    context = " ".join(part for part in (report.module, report.ref_doctype, purpose) if part)
    other_hits = query_tokens & tokens(context)
    return 2 * len(name_hits) + len(other_hits)


def _mandatory_filters(report_name: str) -> List[str]:
    from frappe_assistant_core.plugins.core.tools.report_requirements import discover_filter_definitions

    try:
        definitions = discover_filter_definitions(frappe.get_doc("Report", report_name))
    except Exception:
        return []
    return [fieldname for fieldname, definition in definitions.items() if definition.get("required")]


def _clamp_limit(limit: Any) -> int:
    try:
        return max(1, min(int(limit), MAX_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def _candidate_reports(module: Optional[str]) -> List[Dict[str, Any]]:
    # get_list applies the user's read permission on Report before the per-report run check.
    return frappe.get_list(
        "Report",
        filters={"module": module} if module else {},
        fields=["name", "report_type", "module", "is_standard", "ref_doctype", "prepared_report"],
        limit_page_length=0,
    )


def search_reports(query: str, module: Optional[str] = None, limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    """Reports the user can run, best match for ``query`` first; custom beats standard on a tie."""
    query_tokens = tokens(query)
    ranked = []
    for report in _candidate_reports(module):
        purpose = standard_report_purpose(report.name)
        score = _score(query_tokens, report, purpose)
        if not score:
            continue
        # Only a report built in the UI is boosted: a generic report shipped by an extra app
        # (a country pack, say) is "custom" by origin but not tailored to this business.
        if report.is_standard == "No":
            score += CUSTOM_BOOST
        origin = report_origin(report.name, report.module, report.is_standard)
        # Among equals, a report with a recorded purpose is one we know how to recommend.
        ranked.append(((-score, purpose is None, report.name), report, origin, purpose))
    ranked.sort(key=lambda row: row[0])

    results = []
    for _key, report, origin, purpose in ranked:
        if len(results) >= _clamp_limit(limit):
            break
        if not can_run_report(report.name):
            continue
        results.append(
            {
                "name": report.name,
                "report_type": report.report_type,
                "module": report.module,
                "origin": origin,
                "ref_doctype": report.ref_doctype,
                "prepared": bool(report.prepared_report),
                "mandatory_filters": _mandatory_filters(report.name),
                "purpose": purpose,
            }
        )

    hint = None
    if not results:
        hint = _(
            "No report matches. Try other words or a module (report_list with module set). Otherwise "
            "use get_doctype_info to find the DocType that holds this data, then answer with "
            "list_documents using grouping."
        )
    return {"success": True, "count": len(results), "reports": results, "hint": hint}


def module_summary() -> Dict[str, Any]:
    """Runnable report count per module: the answer to "what is there?" without every name."""
    counts = Counter(r.module for r in _candidate_reports(None) if can_run_report(r.name))
    return {
        "success": True,
        "modules": dict(sorted(counts.items())),
        "hint": _(
            "Call report_list with query set to what the user asked, or with module to list one module."
        ),
    }
