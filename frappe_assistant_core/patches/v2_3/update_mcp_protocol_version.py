# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Update MCP protocol version from 2025-03-26 to 2025-06-18.

The MCP 2025-06-18 spec introduces mandatory RFC 8707 resource indicators
and RFC 9728 protected resource metadata requirements. This patch updates
existing installations to advertise the new protocol version.
"""

import frappe


def execute():
    frappe.db.set_single_value("Assistant Core Settings", "mcp_protocol_version", "2025-06-18")
