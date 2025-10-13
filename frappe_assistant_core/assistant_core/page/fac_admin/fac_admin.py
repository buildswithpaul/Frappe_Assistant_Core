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

import frappe
from frappe import _


def get_context(context):
    context.title = _("assistant Server Management")
    context.description = _("Manage the assistant Server settings and tools.")

    # Fetch assistant Server Settings
    context.settings = frappe.get_single("assistant Server Settings")

    # Fetch assistant Tool Registry
    context.tools = frappe.get_all(
        "assistant Tool Registry", filters={"enabled": 1}, fields=["tool_name", "tool_description"]
    )
