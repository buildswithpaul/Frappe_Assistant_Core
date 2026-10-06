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

"""send_email moved from the faco plugin to the core plugin.

Two things need correcting on a site that already has a send_email row.

**Its stored plugin.** `FAC Tool Configuration` is named by tool_name and the
after_migrate sync skips rows that already exist, so the row would keep
`plugin_name = "faco"` forever. The admin tool list reads the live plugin, so it
looks right there — but `bulk_toggle_tools_by_category` filters the *stored*
value, so "disable every faco tool" would switch off send_email while "disable
every core tool" would miss it.

**Whether it stays available.** The core plugin cannot be disabled, so moving the
tool there makes it reachable on sites where it was not. A site that disabled the
faco plugin had no send_email; after the move it would gain the ability to send
mail from its own Email Account without anyone asking for it. Where faco is
disabled, the tool is therefore disabled at the tool level, which preserves what
the site had and leaves an administrator free to turn it on from FAC Admin.

Establishing "was faco disabled?" is the delicate part, because patches run before
after_migrate and it is after_migrate that writes the plugin rows this would like to
read. See `_faco_was_disabled`.

A site where faco is enabled keeps whatever it had, enabled or not.
"""

import json

import frappe

DOCTYPE = "FAC Tool Configuration"
TOOL = "send_email"
NEW_PLUGIN = "core"
NEW_MODULE_PATH = "frappe_assistant_core.plugins.core.tools.send_email.SendEmail"
PLUGIN_DOCTYPE = "FAC Plugin Configuration"
OLD_PLUGIN = "faco"


def execute():
    if not frappe.db.table_exists(DOCTYPE) or not frappe.db.exists(DOCTYPE, TOOL):
        return

    updates = {"plugin_name": NEW_PLUGIN, "module_path": NEW_MODULE_PATH}

    if _faco_was_disabled():
        # The tool was unreachable here, and the core plugin cannot be switched
        # off, so the tool-level flag is what preserves that.
        updates["enabled"] = 0
        frappe.logger().info(
            f"{__name__}: faco is disabled, so {TOOL} stays off after moving to the core plugin"
        )

    frappe.db.set_value(DOCTYPE, TOOL, updates, update_modified=False)


def _faco_was_disabled() -> bool:
    """Whether this site had the faco plugin switched off.

    A `FAC Plugin Configuration` row is authoritative when there is one. There
    often is not: patches run BEFORE after_migrate, and it is
    `_sync_plugin_configurations` — an after_migrate step — that creates those
    rows. So on a site upgrading from the era when plugin state lived in
    `Assistant Core Settings.enabled_plugins_list`, the row is still absent here
    and the JSON field is the only record of what the administrator chose.

    Reading an absent row as "enabled" would therefore hand send_email to exactly
    the sites this is meant to protect. The legacy field is read with the same
    rule the sync applies: a non-empty list that omits the plugin means disabled,
    while an empty or absent list means a fresh install, which is enabled.

    If neither source can be read, the conservative answer wins. Disabling a tool
    an administrator can switch back on in FAC Admin is recoverable; silently
    granting the ability to send mail from their domain is not.
    """
    if frappe.db.table_exists(PLUGIN_DOCTYPE):
        enabled = frappe.db.get_value(PLUGIN_DOCTYPE, OLD_PLUGIN, "enabled")
        if enabled is not None:
            return not int(enabled)

    try:
        legacy = frappe.db.get_single_value("Assistant Core Settings", "enabled_plugins_list")
    except Exception:
        frappe.logger().warning(
            f"{__name__}: could not read plugin state; keeping {TOOL} off so the move grants nothing"
        )
        return True

    if not legacy:
        # No record either way: a fresh install, which the sync enables.
        return False

    try:
        enabled_plugins = set(json.loads(legacy))
    except (ValueError, TypeError):
        frappe.logger().warning(f"{__name__}: enabled_plugins_list is not readable JSON; keeping {TOOL} off")
        return True

    return bool(enabled_plugins) and OLD_PLUGIN not in enabled_plugins
