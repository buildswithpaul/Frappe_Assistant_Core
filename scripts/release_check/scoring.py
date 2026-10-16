"""Pure scoring and comparison for the release check. No Frappe, no network."""

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


def _contains(answer: str, term: str) -> bool:
    return term.lower() in (answer or "").lower()


def score_top_n(answer: str, expected_names: list) -> bool:
    """True when every expected name appears in the answer (case-insensitive)."""
    return bool(expected_names) and all(_contains(answer, name) for name in expected_names)


def score_mentions(answer: str, terms: list) -> bool:
    """True when every term appears; a term that is a list is satisfied by any one alternative."""
    if not terms:
        return False
    return all(
        any(_contains(answer, option) for option in (term if isinstance(term, list) else [term]))
        for term in terms
    )


def is_cited(text: str, cite: list) -> bool:
    """True when any acceptable report or doctype name appears in the text."""
    return any(_contains(text, name) for name in cite)


def regressions(old: list, new: list) -> list:
    """Ids that were correct in the old results and are not correct in the new ones.

    A question absent from the new results counts: a check that silently stops asking must not pass.
    """
    now = {row["id"]: row for row in new}
    return [row["id"] for row in old if row["correct"] and not now.get(row["id"], {}).get("correct")]
