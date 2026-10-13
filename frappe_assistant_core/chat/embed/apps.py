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

"""Frappe's standalone apps (Helpdesk, Insights, CRM…) that can show the FACO widget.

Discovery reads every installed app's ``add_to_apps_screen`` hook, so a newly
installed app appears without code here. Desk routes are refused: Desk loads
the widget itself.
"""

import frappe

SETTINGS = "FAC Chat Settings"
DESK_PREFIXES = ("/app", "/desk")
ROUTES_CACHE_KEY = "fac_widget_embed_routes"


def normalise_route(route) -> str | None:
    if not isinstance(route, str) or not route.strip("/ "):
        return None
    route = "/" + route.strip().strip("/")
    if any(route == prefix or route.startswith(prefix + "/") for prefix in DESK_PREFIXES):
        return None
    return route


def discover_spa_apps() -> list[dict]:
    apps = []
    for app in frappe.get_installed_apps():
        for entry in frappe.get_hooks("add_to_apps_screen", app_name=app) or []:
            route = normalise_route(entry.get("route")) if isinstance(entry, dict) else None
            if route:
                apps.append({"app": app, "title": entry.get("title") or app, "route": route})
                break
    return apps


def enabled_app_names() -> set[str]:
    return set(
        frappe.get_all(
            "FAC Widget Embed App",
            filters={"parenttype": SETTINGS, "parent": SETTINGS},
            pluck="app_name",
        )
    )


def enabled_routes() -> list[str]:
    """Routes of enabled, still-installed apps. Cached; FAC Chat Settings' save clears it."""
    cache = frappe.cache()
    routes = cache.get_value(ROUTES_CACHE_KEY)
    if routes is None:
        enabled = enabled_app_names()
        routes = [app["route"] for app in discover_spa_apps() if app["app"] in enabled]
        cache.set_value(ROUTES_CACHE_KEY, routes)
    return routes


def clear_routes_cache() -> None:
    frappe.cache().delete_value(ROUTES_CACHE_KEY)
