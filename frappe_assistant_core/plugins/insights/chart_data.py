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

"""Pure helpers for reading Frappe Insights v3 charts: filters, freshness, shaping, caps.

They mirror what Insights 3.14's dashboard page does in the browser (dashboard.ts
getAdhocFilters, filter_utils.ts isFilterValid), so FACO sees the numbers a user sees
with the dashboard's default filters. Nothing here imports Insights, so CI runs it.
"""

import json
import re
from html import unescape

MAX_CHARTS = 12
MAX_DASHBOARD_ROWS = 600
MAX_CELL = 200
MAX_NOTE = 500

VALUELESS_OPERATORS = ("is_set", "is_not_set")
FILTER_LINK = re.compile(r"`(?P<query>[^`]+)`\.`(?P<column>[^`]+)`")
TAG = re.compile(r"<[^>]*>")


def parse_items(items) -> list[dict]:
    if isinstance(items, str):
        items = json.loads(items or "[]")
    return [item for item in (items or []) if isinstance(item, dict)]


def dashboard_filters(items) -> list[dict]:
    """Each filter item of a dashboard, with its default only when Insights would apply it."""
    filters = []
    for item in parse_items(items):
        if item.get("type") != "filter" or not item.get("filter_name"):
            continue
        operator, value = item.get("default_operator"), item.get("default_value")
        filters.append(
            {
                "name": item["filter_name"],
                "type": item.get("filter_type") or "String",
                "links": item.get("links") or {},
                "default": (operator, value) if operator and value else None,
            }
        )
    return filters


def _is_number(value) -> bool:
    try:
        float(value)
        return not isinstance(value, bool)
    except (TypeError, ValueError):
        return False


def _is_valid(operator, value, filter_type) -> bool:
    if not operator:
        return False
    if operator in VALUELESS_OPERATORS:
        return True
    if value is None or value == "" or value is False:
        return False
    if filter_type == "Number":
        if operator == "between":
            return isinstance(value, list) and len(value) == 2 and all(_is_number(v) for v in value)
        return _is_number(value)
    return True


def resolve_filters(filters: list[dict], overrides) -> list[dict]:
    """The operator and value each filter applies: an override by name, else its default."""
    by_name = {o.get("filter"): o for o in (overrides or []) if isinstance(o, dict)}
    resolved = []
    for f in filters:
        override = by_name.get(f["name"])
        if override is not None:
            operator, value, source = override.get("operator"), override.get("value"), "override"
        elif f["default"]:
            (operator, value), source = f["default"], "default"
        else:
            operator, value, source = None, None, "none"
        if not _is_valid(operator, value, f["type"]):
            operator, value, source = None, None, "none"
        resolved.append({**f, "operator": operator, "value": value, "source": source})
    return resolved


def unknown_overrides(filters: list[dict], overrides) -> list[str]:
    names = {f["name"] for f in filters}
    return [
        o.get("filter") for o in (overrides or []) if isinstance(o, dict) and o.get("filter") not in names
    ]


def adhoc_filters_for(chart_name: str, resolved: list[dict]) -> dict:
    """Insights' adhoc_filters for one chart: applied filters linked to it, grouped by base query."""
    groups: dict = {}
    for f in resolved:
        if f["source"] == "none":
            continue
        link = FILTER_LINK.fullmatch(f["links"].get(chart_name) or "")
        if not link:
            continue
        group = groups.setdefault(
            link["query"], {"type": "filter_group", "logical_operator": "And", "filters": []}
        )
        group["filters"].append(
            {
                "column": {"type": "column", "column_name": link["column"]},
                "operator": f["operator"],
                "value": f["value"],
            }
        )
    return groups


def chart_names(items) -> list[str]:
    charts = [i for i in parse_items(items) if i.get("type") == "chart" and i.get("chart")]
    charts.sort(key=lambda i: ((i.get("layout") or {}).get("y", 0), (i.get("layout") or {}).get("x", 0)))
    names: list[str] = []
    for item in charts:
        if item["chart"] not in names:
            names.append(item["chart"])
    return names


def notes(items) -> list[str]:
    out = []
    for item in parse_items(items):
        if item.get("type") != "text":
            continue
        text = " ".join(unescape(TAG.sub(" ", item.get("text") or "")).split())
        if text:
            out.append(text[:MAX_NOTE] + ("…" if len(text) > MAX_NOTE else ""))
    return out


def is_fresh(data_query_modified, chart_modified, operations) -> bool:
    """Whether the chart's stored data_query reflects its current config."""
    ops = json.loads(operations or "[]") if isinstance(operations, str) else operations
    return (
        bool(ops)
        and data_query_modified is not None
        and chart_modified is not None
        and data_query_modified >= chart_modified
    )


def config_summary(chart_type: str, config) -> dict:
    cfg = json.loads(config or "{}") if isinstance(config, str) else (config or {})
    dimensions: list[dict] = []
    measures: list[dict] = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("aggregation") and node.get("column_name"):
                entry = {
                    "column": node["column_name"],
                    "aggregation": node["aggregation"],
                    "label": node.get("measure_name"),
                }
                if entry not in measures:
                    measures.append(entry)
            elif node.get("dimension_name") and node.get("column_name"):
                entry = {
                    "column": node["column_name"],
                    "label": node["dimension_name"],
                    "granularity": node.get("granularity"),
                }
                if entry not in dimensions:
                    dimensions.append(entry)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(cfg)
    return {
        "chart_type": chart_type,
        "dimensions": dimensions,
        "measures": measures,
        "limit": cfg.get("limit"),
    }


def _cell(value):
    if isinstance(value, str) and len(value) > MAX_CELL:
        return value[:MAX_CELL] + "…"
    return value


def shape_result(result: dict, max_rows: int) -> dict:
    columns = [c for c in (result.get("columns") or []) if not c.get("hidden")]
    names = [c["name"] for c in columns]
    rows = result.get("rows") or []
    return {
        "columns": [{"name": c["name"], "type": c.get("type")} for c in columns],
        "rows": [{n: _cell(row.get(n)) for n in names} for row in rows[:max_rows]],
        "truncated": len(rows) > max_rows,
    }


def row_budget(max_rows_per_chart: int, used: int) -> int:
    return max(0, min(max_rows_per_chart, MAX_DASHBOARD_ROWS - used))
