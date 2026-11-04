# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Migration plugin for Frappe Assistant Core.
Brings a client's data into ERPNext from their old system: import sessions and the migration plan
(#33986), and the opening stock, invoices and balances.
"""

from typing import Any, Dict, List, Optional, Tuple

from frappe_assistant_core.plugins.base_plugin import BasePlugin


class MigrationPlugin(BasePlugin):
    """Data migration: a client's records and opening entries from their old system."""

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "migration",
            "display_name": "Migration",
            "description": "Import a client's data from their old system: import sessions, migration "
            "plans and the opening stock, invoices and balances",
            "version": "1.0.0",
            "dependencies": [],
            "requires_restart": False,
        }

    def get_tools(self) -> List[str]:
        return [
            # One file at a time (#33986)
            "start_import_session",
            "get_import_schema",
            "set_column_mapping",
            "dry_run_import",
            "start_import",
            # Opening entries
            "set_opening_stock",
            "import_opening_stock",
            "set_opening_invoices",
            "import_opening_invoices",
            "set_opening_balances",
            "import_opening_balances",
            # A whole migration on one approval
            "plan_migration",
            "run_migration_plan",
            "stop_migration_plan",
        ]

    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        return True, None
