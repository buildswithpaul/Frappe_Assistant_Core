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

"""Make the FAC Plugin Configuration rows say what the legacy plugin list says (#34662).

`load_enabled_plugins` guarded its read of the rows with `table_exists("tabFAC Plugin
Configuration")`. `table_exists` adds the `tab` prefix itself, so that was always False and the
plugin state was read only from `Assistant Core Settings.enabled_plugins_list`, while the FAC
Admin toggle wrote only the rows. The two can disagree, and some sites have no rows at all.

The legacy list is what the site has been running on, so it is authoritative: every plugin it
names gets an enabled row and every other plugin a disabled one, and the core plugin is always on.
An empty or unreadable list is a fresh install, which the after_migrate sync seeds, so the rows
are left to it. Safe to run twice.
"""

import json

import frappe

PLUGIN_DOCTYPE = "FAC Plugin Configuration"
CORE_PLUGIN = "core"


def execute():
    if not frappe.db.table_exists(PLUGIN_DOCTYPE):
        return

    legacy = _legacy_enabled_plugins()
    if not legacy:
        return
    enabled = legacy | {CORE_PLUGIN}

    from frappe_assistant_core.utils.plugin_manager import PluginDiscovery

    discovered = PluginDiscovery().discover_plugins()
    existing = set(frappe.get_all(PLUGIN_DOCTYPE, pluck="plugin_name"))

    for name in existing | set(discovered):
        wanted = 1 if name in enabled else 0
        if name in existing:
            frappe.db.set_value(PLUGIN_DOCTYPE, name, "enabled", wanted, update_modified=False)
            continue
        info = discovered[name]
        frappe.get_doc(
            {
                "doctype": PLUGIN_DOCTYPE,
                "plugin_name": name,
                "display_name": getattr(info, "display_name", name.replace("_", " ").title()),
                "description": getattr(info, "description", ""),
                "enabled": wanted,
                "discovered_at": frappe.utils.now(),
            }
        ).insert(ignore_permissions=True)


def _legacy_enabled_plugins() -> set[str]:
    """The plugins the legacy list names; empty when it is absent, empty or not readable."""
    try:
        raw = frappe.db.get_single_value("Assistant Core Settings", "enabled_plugins_list")
        parsed = json.loads(raw) if raw else []
    except Exception:
        return set()
    return set(parsed) if isinstance(parsed, list) else set()
