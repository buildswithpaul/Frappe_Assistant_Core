# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Delete the stored settings of plan_questions, now dry_run_import's plan mode (#34351).

dry_run_import checks a file, or with plan every file of a migration plan and its questions, so
one tool does both. The removed tool's FAC Tool Configuration row is deleted, so a site's tool
list and its Desk settings never show a tool that isn't there. Safe to run twice.
"""

from frappe_assistant_core.patches.v3_2.remove_import_undo_tool_configurations import (
    delete_configurations,
)


def execute():
    delete_configurations(("plan_questions",))
