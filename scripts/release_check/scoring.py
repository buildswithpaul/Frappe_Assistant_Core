"""Pure scoring and comparison for the release check. No Frappe, no network."""

import json
import re

TOTAL_TOLERANCE = 0.005

MULTIPLIERS = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "mn": 1e6,
    "million": 1e6,
    "lakh": 1e5,
    "lakhs": 1e5,
    "lac": 1e5,
    "lacs": 1e5,
    "cr": 1e7,
    "crore": 1e7,
    "crores": 1e7,
    "b": 1e9,
    "bn": 1e9,
    "billion": 1e9,
}

# digits with optional comma groups (western 1,234,567 or Indian 1,23,456) and decimals,
# then an optional magnitude word; a trailing "." is sentence punctuation, not a decimal point
NUMBER = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:\s?(" + "|".join(MULTIPLIERS) + r")\b)?",
    re.IGNORECASE,
)


def extract_numbers(text: str) -> list:
    """Every number in the text as a float.

    Supports comma grouping (western and Indian), decimals, currency signs (ignored) and the
    magnitudes K, thousand, M/million, B/billion, lakh and crore ("1.2M", "12 lakh").
    """
    values = []
    for match in NUMBER.finditer(text or ""):
        value = float(match.group(1).replace(",", ""))
        if match.group(2):
            value *= MULTIPLIERS[match.group(2).lower()]
        values.append(value)
    return values


def score_total(answer: str, expected: float) -> bool:
    """True when any number in the answer is within 0.5% of the expected total."""
    allowed = abs(expected) * TOTAL_TOLERANCE
    return any(abs(value - expected) <= allowed for value in extract_numbers(answer))


NUMERIC_TERM = re.compile(r"[\d,]+(?:\.\d+)?")


def _contains(answer: str, term) -> bool:
    """Whole-token, case-insensitive match: "ABC" is not in "ABCD", "...00001" is not in "...000012"."""
    if not isinstance(term, str) or not term:
        return False
    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return re.search(pattern, answer or "", re.IGNORECASE) is not None


def _matches(answer: str, term) -> bool:
    """A numeric term (an amount in some formatting) must equal a number in the answer exactly;
    anything else is matched as a whole token."""
    if isinstance(term, str) and NUMERIC_TERM.fullmatch(term):
        wanted = float(term.replace(",", ""))
        return any(abs(value - wanted) < 1e-9 for value in extract_numbers(answer))
    return _contains(answer, term)


def score_top_n(answer: str, expected_names: list) -> bool:
    """True when every expected name appears as a whole token in the answer (case-insensitive)."""
    return bool(expected_names) and all(_contains(answer, name) for name in expected_names)


def score_mentions(answer: str, terms: list) -> bool:
    """True when every term appears; a term that is a list is satisfied by any one alternative.

    Numeric alternatives are compared as numbers, exactly, so "1,000.00" never matches inside
    "11,000.00" and "500" never inside "1500".
    """
    if not terms:
        return False
    return all(
        any(_matches(answer, option) for option in (term if isinstance(term, list) else [term]))
        for term in terms
    )


def is_cited(text: str, cite: list) -> bool:
    """True when any acceptable report or doctype name appears (whole words) in the text."""
    return any(_contains(text, name) for name in cite)


def citation_text(answer: str, tool_calls) -> str:
    """The answer plus each tool call's NAME and INPUT. Never the result: a report list that merely
    mentions "Sales Register" must not count as using it."""
    if isinstance(tool_calls, str):
        try:
            tool_calls = json.loads(tool_calls)
        except ValueError:
            tool_calls = None
    parts = [answer or ""]
    for call in tool_calls if isinstance(tool_calls, list) else []:
        if isinstance(call, dict):
            parts.append(str(call.get("name") or ""))
            parts.append(json.dumps(call.get("input") or "", default=str))
    return " ".join(parts)


def is_non_answer(reply) -> bool:
    """No reply, an empty one, or a turn that errored or was aborted: never scored correct."""
    return (
        not reply
        or bool(reply.get("errored") or reply.get("aborted"))
        or not (reply.get("content") or "").strip()
    )


def regressions(old: list, new: list) -> list:
    """Ids that were correct in the old results and are not correct in the new ones.

    A question absent from the new results counts: a check that silently stops asking must not pass.
    """
    now = {row["id"]: row for row in new}
    return [row["id"] for row in old if row["correct"] and not now.get(row["id"], {}).get("correct")]
