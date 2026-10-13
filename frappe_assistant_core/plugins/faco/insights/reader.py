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

"""Reading Insights as the calling user.

Insights checks document permissions where a request enters it; called from Python,
InsightsQueryv3.execute checks none. Every read here passes the gate first. Queries run
as the session user, so Insights' table, team and User Permission rules still apply.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime

from frappe_assistant_core.plugins.faco.insights.chart_data import (
    adhoc_filters_for,
    applied_filters,
    chart_row_limit,
    config_summary,
    is_fresh,
    shape_result,
)

CHART = "Insights Chart v3"
QUERY = "Insights Query v3"


def insights_access_error() -> dict | None:
    from insights.permissions import check_app_permission

    if check_app_permission():
        return None
    return {"success": False, "error": _("You don't have access to Frappe Insights.")}


def can_read(doctype: str, name) -> bool:
    return (
        bool(name)
        and bool(frappe.db.exists(doctype, name))
        and frappe.has_permission(doctype, "read", doc=name)
    )


def not_found(kind: str, name) -> dict:
    # The same answer for a missing and a forbidden name, so names cannot be probed.
    return {"success": False, "error": _("No Insights {0} named {1} that you can open.").format(kind, name)}


def _query_for(chart):
    """The chart's own data_query when fresh, else its base query; with whether it was fresh."""
    if chart.data_query and frappe.db.exists(QUERY, chart.data_query):
        data_query = frappe.get_doc(QUERY, chart.data_query)
        if is_fresh(get_datetime(data_query.modified), get_datetime(chart.modified), data_query.operations):
            return data_query, True
    if chart.query and frappe.db.exists(QUERY, chart.query):
        return frappe.get_doc(QUERY, chart.query), False
    return None, False


def _error_text(exc: Exception) -> str:
    from insights.exceptions import QueryTimeout

    if isinstance(exc, QueryTimeout):
        return _("This chart's query timed out.")
    if getattr(exc, "http_status_code", None) == 503:
        return _("Insights is busy — try again in a moment.")
    frappe.log_error(title="FAC Insights chart read failed", message=frappe.get_traceback())
    return _("This chart could not be read.")


def _execute(query, adhoc_filters: dict | None, page_size: int) -> dict:
    # Insights' set_adhoc_filters keeps what a failed build left, and a later execute without
    # filters inherits it; so each read starts and ends with none.
    frappe.local.insights_adhoc_filters = None
    try:
        return query.execute(adhoc_filters=adhoc_filters, page_size=page_size)
    finally:
        frappe.local.insights_adhoc_filters = None


def read_chart(chart_name: str, resolved_filters: list[dict], max_rows: int) -> dict:
    entry: dict = {"name": chart_name}
    try:
        if not can_read(CHART, chart_name):
            return {**entry, "error": _("You can't open this chart.")}
        chart = frappe.get_doc(CHART, chart_name)
        entry.update(title=chart.title, type=chart.chart_type)
        query, fresh = _query_for(chart)
        if query is None:
            return {**entry, "error": _("This chart has no query.")}
        if not frappe.has_permission(QUERY, "read", doc=query.name):
            return {**entry, "error": _("You can't open this chart.")}
        if max_rows <= 0:
            return {
                **entry,
                "columns": [],
                "rows": [],
                "truncated": True,
                "note": _("This call's row budget is used up; read this chart with get_insights_chart."),
            }
        if fresh:
            max_rows = min(max_rows, chart_row_limit(chart.config))
        adhoc = adhoc_filters_for(chart_name, resolved_filters) or None
        result = _execute(query, adhoc, max_rows + 1)
        entry.update(shape_result(result, max_rows))
        entry["source"] = "chart" if fresh else "raw"
        entry["applied_filters"] = applied_filters(chart_name, resolved_filters)
        # What the numbers measure: a pivot's columns are dimension values, so its rows alone do not say.
        entry["config_summary"] = config_summary(chart.chart_type, chart.config)
        if not fresh:
            entry["note"] = _(
                "These are the chart's source rows, not its aggregated values: aggregate them as "
                "config_summary describes, and say you did."
            )
    except Exception as exc:
        entry["error"] = _error_text(exc)
    return entry
