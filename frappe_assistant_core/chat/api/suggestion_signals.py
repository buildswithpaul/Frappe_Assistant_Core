"""Local usage-signal gathering for curated welcome suggestions.

All reads are FAC-local (under ZDR the chat history lives here, not on AR).
Only summarized signals leave this module — never raw transcripts.
"""

import re
from collections import Counter

import frappe
from frappe.utils import add_days, now_datetime

LOOKBACK_DAYS = 30
MAX_DOCTYPES = 5
MAX_STEMS = 5
MAX_SAMPLES = 5
SAMPLE_MAX_LEN = 120
MESSAGE_LIMIT = 200
ROUTE_LIMIT = 500
STEM_WORDS = 5
NOISE_ROLES = {"All", "Guest", "Desk User", "System Manager", "Administrator"}
ROUTE_KINDS = {"form", "list", "tree", "report"}


def _doctypes_from_routes(routes) -> Counter:
    counts: Counter = Counter()
    for route in routes or []:
        if not route or not isinstance(route, str):
            continue
        parts = route.split("/")
        if len(parts) >= 2 and parts[0].lower() in ROUTE_KINDS and parts[1]:
            counts[parts[1]] += 1
    return counts


def _normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _repeated_stems(contents) -> list:
    counts: Counter = Counter()
    for content in contents or []:
        words = _normalize(content).split()
        if len(words) >= 3:
            counts[" ".join(words[:STEM_WORDS])] += 1
    return [stem for stem, n in counts.most_common(MAX_STEMS) if n >= 2]


def gather_suggestion_signals(user: str) -> dict:
    cutoff = add_days(now_datetime(), -LOOKBACK_DAYS)

    messages = frappe.get_all(
        "FAC Chat Message",
        filters={"user": user, "timestamp": [">", cutoff]},
        fields=["content", "role", "context_doctype"],
        order_by="timestamp desc",
        limit_page_length=MESSAGE_LIMIT,
    )
    routes = frappe.get_all(
        "Route History",
        filters={"user": user, "modified": [">", cutoff]},
        fields=["route"],
        order_by="modified desc",
        limit_page_length=ROUTE_LIMIT,
    )

    merged: Counter = Counter()
    for m in messages:
        if m.get("context_doctype"):
            merged[m["context_doctype"]] += 2  # explicit chat context outweighs navigation
    merged.update(_doctypes_from_routes([r.get("route") for r in routes]))

    user_contents = [m["content"] for m in messages if m.get("role") == "user" and m.get("content")]
    samples, seen = [], set()
    for content in user_contents:
        key = _normalize(content)
        if not key or key in seen:
            continue
        seen.add(key)
        samples.append(content[:SAMPLE_MAX_LEN])
        if len(samples) >= MAX_SAMPLES:
            break

    roles = [r for r in frappe.get_roles(user) if r not in NOISE_ROLES]

    return {
        "top_doctypes": [dt for dt, _n in merged.most_common(MAX_DOCTYPES)],
        "repeated_prompts": _repeated_stems(user_contents),
        "sample_prompts": samples,
        "roles": roles[:6],
        "locale": getattr(frappe.local, "lang", None) or "en",
    }
