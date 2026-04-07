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


@frappe.whitelist()
def get_server_settings() -> dict:
    """Fetch assistant Server Settings with caching."""
    frappe.only_for(["System Manager", "Assistant Admin"])
    from frappe_assistant_core.utils.cache import get_cached_server_settings

    return get_cached_server_settings()


@frappe.whitelist(methods=["POST"])
def update_server_settings(**kwargs):
    """Update Assistant Core Settings."""
    frappe.only_for(["System Manager", "Assistant Admin"])
    settings = frappe.get_single("Assistant Core Settings")

    # Update only the fields that are provided
    updated = False
    for field in [
        "server_enabled",
    ]:
        if field in kwargs:
            setattr(settings, field, kwargs[field])
            updated = True

    if updated:
        settings.save()

        # Clear ALL caches using wildcard pattern to catch redis_cache decorated functions
        cache = frappe.cache()
        cache.delete_keys("*get_cached_server_settings*")
        cache.delete_keys("assistant_*")

        # Clear document cache
        frappe.clear_document_cache("Assistant Core Settings", "Assistant Core Settings")

        # Force frappe to clear its internal caches
        frappe.clear_cache(doctype="Assistant Core Settings")

    return {"message": _("Assistant Core Settings updated successfully.")}
