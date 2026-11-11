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

"""The site profile the FAC Cloud heartbeat sends: installed apps, customisation counts and the
web-server setup, so FAC Cloud can warn a site early and support it. Counts and verdicts only,
never record contents, names or messages. Each part is best-effort: one that fails is left out.
"""

import frappe

from frappe_assistant_core.chat.server_setup import server_setup_report

# The figures and verdicts sent from the server-setup report; its reasons and fixes are text.
WEB_SERVER_KEYS = ("source", "worker_class", "workers", "threads", "slots", "required_slots", "status")
RELAY_KEYS = ("status", "enabled", "workers", "required_workers")


def _customisation_counts() -> dict:
    return {
        "custom_doctypes": frappe.db.count("DocType", {"custom": 1}),
        "custom_fields": frappe.db.count("Custom Field"),
        "server_scripts": frappe.db.count("Server Script"),
        "active_server_scripts": frappe.db.count("Server Script", {"disabled": 0}),
        "client_scripts": frappe.db.count("Client Script"),
        "fac_pages": frappe.db.count("FAC Page"),
    }


def site_profile(versions: dict) -> dict:
    """The profile for this site; `versions` is frappe.utils.change_log.get_versions()."""
    profile = {
        "apps": {app: info.get("version") for app, info in versions.items() if info.get("version")},
    }
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
    return profile
