"""The data migration tools moved from the core plugin to their own, migration.

Two things need correcting on a site that already has them.

**Their stored plugin.** `FAC Tool Configuration` is named by tool_name and the after_migrate sync
skips rows that already exist, so each row would keep `plugin_name = "core"` and core's module path
for ever, and "disable every core tool" in FAC Admin would still switch them off.

**Whether they stay available.** They were in core, which can't be switched off, so every site had
them. The migration plugin is new: the after_migrate sync makes its row enabled only when the site's
legacy plugin list is empty or names it, so on most sites it would come up disabled and the whole
migration would vanish. The plugin is therefore switched on here, before that sync runs, in the
plugin row and in the legacy list both. An administrator can then switch it off in FAC Admin.

Safe to run twice.
"""

import json

import frappe

TOOL_DOCTYPE = "FAC Tool Configuration"
PLUGIN_DOCTYPE = "FAC Plugin Configuration"
OLD_PLUGIN, NEW_PLUGIN = "core", "migration"
MODULE = "frappe_assistant_core.plugins.migration.tools.{0}.{1}"

#: tool name -> its class, for the module path the row records
TOOLS = {
    "start_import_session": "StartImportSession",
    "get_import_schema": "GetImportSchema",
    "set_column_mapping": "SetColumnMapping",
    "dry_run_import": "DryRunImport",
    "start_import": "StartImport",
    "set_opening_stock": "SetOpeningStock",
    "import_opening_stock": "ImportOpeningStock",
    "set_opening_invoices": "SetOpeningInvoices",
    "import_opening_invoices": "ImportOpeningInvoices",
    "set_opening_balances": "SetOpeningBalances",
    "import_opening_balances": "ImportOpeningBalances",
    "plan_migration": "PlanMigration",
    "run_migration_plan": "RunMigrationPlan",
    "stop_migration_plan": "StopMigrationPlan",
}


def execute():
    enable_plugin()
    if not frappe.db.table_exists(TOOL_DOCTYPE):
        return
    for tool, cls in TOOLS.items():
        if frappe.db.exists(TOOL_DOCTYPE, tool):
            frappe.db.set_value(
                TOOL_DOCTYPE,
                tool,
                {"plugin_name": NEW_PLUGIN, "module_path": MODULE.format(tool, cls)},
                update_modified=False,
            )


def enable_plugin():
    """Switch the migration plugin on, so the tools stay where every site had them."""
    if frappe.db.table_exists(PLUGIN_DOCTYPE) and not frappe.db.exists(PLUGIN_DOCTYPE, NEW_PLUGIN):
        frappe.get_doc(
            {
                "doctype": PLUGIN_DOCTYPE,
                "plugin_name": NEW_PLUGIN,
                "display_name": "Migration",
                "enabled": 1,
                "discovered_at": frappe.utils.now(),
            }
        ).insert(ignore_permissions=True)
    try:
        legacy = frappe.db.get_single_value("Assistant Core Settings", "enabled_plugins_list")
    except Exception:
        return
    try:
        enabled = json.loads(legacy) if legacy else []
    except (ValueError, TypeError):
        return
    # An empty list is a fresh install, which the sync enables; a list that names plugins must
    # name this one too, or a site still reading the list would lose the migration.
    if enabled and NEW_PLUGIN not in enabled:
        frappe.db.set_single_value(
            "Assistant Core Settings", "enabled_plugins_list", json.dumps([*enabled, NEW_PLUGIN])
        )
