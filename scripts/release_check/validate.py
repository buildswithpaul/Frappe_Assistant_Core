"""Check questions.json against the release-check schema and expected.py.

Pure Python (no Frappe): expected.py is parsed with `ast`, never imported, so
this runs anywhere, including CI.

    python scripts/release_check/validate.py
"""

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITES = {"realistic", "large"}
KINDS = {"total", "top_n", "mentions"}
REQUIRED_IDS = {
    "sales_last_month",
    "top_customers_quarter",
    "receivables_ageing",
    "vendor_payment_history",
    "stock_position",
    "sales_by_region_custom_report",
    "bookings_this_month_custom_doctype",
    "ledger_heavy_report",
}


def function_names(source: str) -> set:
    """Top-level function names defined in a Python source string."""
    return {node.name for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}


def validate_questions(questions, available_functions: set) -> list:
    """Return a list of problems; empty means valid."""
    if not isinstance(questions, list) or not questions:
        return ["questions must be a non-empty list"]
    problems, seen = [], set()
    for index, item in enumerate(questions):
        where = f"question #{index}"
        if not isinstance(item, dict):
            problems.append(f"{where}: must be an object")
            continue
        qid = item.get("id")
        where = f"question '{qid}'"
        if not isinstance(qid, str) or not qid:
            problems.append(f"{where}: id must be a non-empty string")
        elif qid in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(qid)
        if item.get("site") not in SITES:
            problems.append(f"{where}: site must be one of {sorted(SITES)}")
        if not isinstance(item.get("question"), str) or not item.get("question", "").strip():
            problems.append(f"{where}: question must be a non-empty string")
        expect = item.get("expect")
        if not isinstance(expect, dict):
            problems.append(f"{where}: expect must be an object")
        else:
            if expect.get("kind") not in KINDS:
                problems.append(f"{where}: expect.kind must be one of {sorted(KINDS)}")
            if expect.get("source") not in available_functions:
                problems.append(
                    f"{where}: expect.source '{expect.get('source')}' is not a function in expected.py"
                )
        cite = item.get("cite")
        if not (isinstance(cite, list) and cite and all(isinstance(name, str) and name for name in cite)):
            problems.append(f"{where}: cite must be a non-empty list of names")
    for missing in sorted(REQUIRED_IDS - seen):
        problems.append(f"required question id '{missing}' is missing")
    return problems


def main() -> int:
    questions = json.loads((HERE / "questions.json").read_text())
    functions = function_names((HERE / "expected.py").read_text())
    problems = validate_questions(questions, functions)
    for problem in problems:
        print(f"INVALID: {problem}")
    if not problems:
        print(f"OK: {len(questions)} questions, all sources found in expected.py")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
