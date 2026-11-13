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

"""The site profile the FAC Cloud heartbeat sends: installed apps, customisation counts, the
web-server setup and the ERPNext company's currency and country, so FAC Cloud can warn a site
early, support it and price its plans. Counts, verdicts and codes only, never record contents,
names or messages. Each part is best-effort: one that fails is left out.
"""

import frappe

from frappe_assistant_core.chat.server_setup import server_setup_report
from frappe_assistant_core.utils.customisation import server_scripts_enabled

# The figures and verdicts sent from the server-setup report; its reasons and fixes are text.
WEB_SERVER_KEYS = ("source", "worker_class", "workers", "threads", "slots", "required_slots", "status")
RELAY_KEYS = ("status", "enabled", "queue_configured", "workers", "required_workers")

# Each count's doctype and filters; Custom Fields that apps install are not the site's own.
COUNTS = {
    "custom_doctypes": ("DocType", {"custom": 1}),
    "custom_fields": ("Custom Field", {"is_system_generated": 0}),
    "server_scripts": ("Server Script", None),
    "active_server_scripts": ("Server Script", {"disabled": 0}),
    "client_scripts": ("Client Script", None),
    "fac_pages": ("FAC Page", None),
}


def _customisation_counts() -> dict:
    # A table that does not exist yet (code deployed before migrate) leaves out only its own count
    counts = {
        key: frappe.db.count(doctype, filters)
        for key, (doctype, filters) in COUNTS.items()
        if frappe.db.table_exists(doctype)
    }
    counts["server_scripts_enabled"] = server_scripts_enabled()
    return counts


def company() -> dict:
    """The ERPNext company's currency and ISO country code; FAC Cloud prices plans in that
    currency until a billing address is saved. The default company, else the only one; empty
    without ERPNext or when neither picks one."""
    if not frappe.db.exists("DocType", "Company"):
        return {}
    name = _default_company()
    if not name:
        companies = frappe.get_all("Company", pluck="name", limit=2)
        name = companies[0] if len(companies) == 1 else None
    values = name and frappe.db.get_value("Company", name, ["default_currency", "country"], as_dict=True)
    if not values:
        return {}
    code = values.country and frappe.db.get_value("Country", values.country, "code")
    return {
        key: value
        for key, value in (("currency", values.default_currency), ("country", (code or "").upper()))
        if value
    }


def _default_company() -> str | None:
    """ERPNext keeps it on Global Defaults; it is not a `default_company` default."""
    return frappe.db.get_single_value("Global Defaults", "default_company")


def site_profile(versions: dict) -> dict:
    """The profile for this site; `versions` is frappe.utils.change_log.get_versions()."""
    profile = {}
    apps = {app: info.get("version") for app, info in versions.items() if info.get("version")}
    # No apps rather than an empty list, which would replace the ones FAC Cloud stored last time
    if apps:
        profile["apps"] = apps
    try:
        profile["customisations"] = _customisation_counts()
    except Exception:
        frappe.logger("faco.billing").exception("FACO heartbeat: customisation counts failed")
    try:
        report = server_setup_report()
        profile["web_server"] = {key: report.get(key) for key in WEB_SERVER_KEYS}
        profile["relay"] = {key: report["relay"].get(key) for key in RELAY_KEYS}
    except Exception:
        frappe.logger("faco.billing").exception("FACO heartbeat: server setup report failed")
    try:
        if facts := company():
            profile["company"] = facts
    except Exception:
        frappe.logger("faco.billing").exception("FACO heartbeat: company lookup failed")
    return profile
