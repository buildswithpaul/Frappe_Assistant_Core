# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Delete the stored settings of apply_import_preset, now part of start_import_session (#34000).

start_import_session tries the import presets itself, so every file takes one call. The removed
tool's FAC Tool Configuration row is deleted, so a site's tool list and its Desk settings never
show a tool that isn't there. Safe to run twice.
"""

from frappe_assistant_core.patches.v3_2.remove_import_undo_tool_configurations import (
    delete_configurations,
)


def execute():
    delete_configurations(("apply_import_preset",))
