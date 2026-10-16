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

"""Who may run a Report, and where it came from.

Report search and the report tools share these two rules so a report the user
cannot run is never listed, and a report's origin is decided in one place.
"""

from typing import Literal

import frappe

STANDARD_APPS = ("frappe", "erpnext", "hrms")


def can_run_report(report_name: str) -> bool:
    """True when the current user may run ``report_name`` and it is enabled.

    Applies the rule Desk applies when opening a report, by calling the same
    function: the report's roles, read permission on its reference doctype, and
    the disabled flag. Custom Reports are checked against their base report.
    Denials are muted: Desk's frappe.throw would otherwise queue one error
    message per refused report for the caller's response.
    """
    from frappe.desk.query_report import get_report_doc

    previous = frappe.flags.mute_messages
    frappe.flags.mute_messages = True
    try:
        get_report_doc(report_name)
    except (frappe.PermissionError, frappe.ValidationError, frappe.DoesNotExistError):
        return False
    finally:
        frappe.flags.mute_messages = previous
    return True


def report_origin(report_name: str, module: str, is_standard: str) -> Literal["custom", "standard"]:
    """Origin is "custom" for a report built in the UI or shipped by a non-standard app."""
    if is_standard == "No":
        return "custom"

    app = (frappe.local.module_app or {}).get(frappe.scrub(module))
    return "standard" if app in STANDARD_APPS else "custom"
