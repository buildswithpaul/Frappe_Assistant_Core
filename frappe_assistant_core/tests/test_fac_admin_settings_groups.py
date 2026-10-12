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

"""The FAC Admin Settings tab's group map stays in step with both settings DocTypes."""

import copy
import json
from unittest.mock import patch

import frappe
from frappe.desk.form.save import savedocs

from frappe_assistant_core.api.admin.settings import (
    get_settings_groups,
    load_settings_map,
    missing_names,
    resolve_groups,
    unmapped_units,
)
from frappe_assistant_core.chat.tenant_credentials import read_tenant_secret, store_tenant_secret
from frappe_assistant_core.tests.base_test import BaseAssistantTest

LAYOUT = ("Section Break", "Tab Break", "Column Break")
SETTINGS_MODULE = "frappe_assistant_core.api.admin.settings"
NON_ADMIN_USER = "test_settings_nonadmin@example.com"
ASSISTANT_ADMIN_USER = "test_settings_assistant_admin@example.com"
TENANT_SECRET = "s" * 40


class TestFacAdminSettingsGroups(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.settings_map = load_settings_map()

    def _served_fields(self, settings_map=None):
        return [
            (group["doctype"], fieldname)
            for group in resolve_groups(settings_map or self.settings_map)
            for fieldname in group["fields"]
        ]

    def test_every_visible_section_is_in_a_group_or_skipped(self):
        self.assertEqual(unmapped_units(self.settings_map), {})

    def test_a_section_left_out_of_the_map_is_reported(self):
        # The guard above must be able to fail: drop a unit as a forgotten new section would be.
        changed = copy.deepcopy(self.settings_map)
        oauth = next(g for g in changed["groups"] if g["key"] == "oauth")
        oauth["units"].remove("oauth_metadata_section")
        self.assertEqual(unmapped_units(changed), {"Assistant Core Settings": ["oauth_metadata_section"]})

    def test_every_name_in_the_map_exists(self):
        self.assertEqual(missing_names(self.settings_map), [])

    def test_a_renamed_section_is_reported(self):
        changed = copy.deepcopy(self.settings_map)
        changed["groups"][0]["units"].append("no_such_section")
        self.assertEqual(missing_names(changed), ["FAC Chat Settings.no_such_section"])

    def test_no_password_or_hidden_field_is_served(self):
        for doctype, fieldname in self._served_fields():
            df = frappe.get_meta(doctype).get_field(fieldname)
            if df.fieldtype in LAYOUT:
                continue
            self.assertNotEqual(df.fieldtype, "Password", f"{doctype}.{fieldname}")
            self.assertFalse(df.hidden, f"{doctype}.{fieldname}")

    def test_tenant_secret_is_never_served(self):
        self.assertNotIn(("FAC Chat Settings", "tenant_secret"), self._served_fields())

    def test_controls_already_on_the_page_are_not_repeated(self):
        served = {fieldname for _, fieldname in self._served_fields()}
        self.assertFalse(served & {"server_enabled", "enable_fac_chat"})

    def test_groups_keep_their_fields_in_doctype_order(self):
        ocr = next(g for g in resolve_groups(self.settings_map) if g["key"] == "ocr")
        self.assertLess(ocr["fields"].index("ocr_backend"), ocr["fields"].index("ollama_api_url"))

    def test_the_endpoint_returns_the_resolved_groups_on_frappe_v15(self):
        with patch(f"{SETTINGS_MODULE}.is_frappe_v16_or_later", autospec=True, return_value=False):
            keys = [g["key"] for g in get_settings_groups()["groups"]]
        self.assertEqual(keys, ["chat_widget", "mcp_server", "oauth", "security", "ocr", "fac_cloud"])

    def test_the_endpoint_leaves_out_oauth_on_frappe_v16(self):
        # v16 reads OAuth from its native OAuth Settings (utils/oauth_compat.py), so these fields
        # would save and do nothing; the DocType form hides the tab there for the same reason.
        with patch(f"{SETTINGS_MODULE}.is_frappe_v16_or_later", autospec=True, return_value=True):
            keys = [g["key"] for g in get_settings_groups()["groups"]]
        self.assertEqual(keys, ["chat_widget", "mcp_server", "security", "ocr", "fac_cloud"])

    def test_the_endpoint_refuses_a_user_without_an_admin_role(self):
        if not frappe.db.exists("User", NON_ADMIN_USER):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": NON_ADMIN_USER,
                    "first_name": "Settings",
                    "user_type": "Website User",
                }
            ).insert(ignore_permissions=True)
        frappe.set_user(NON_ADMIN_USER)
        try:
            with self.assertRaises(frappe.PermissionError):
                get_settings_groups()
        finally:
            frappe.set_user("Administrator")

    def test_the_endpoint_serves_no_group_whose_doctype_the_user_cannot_read(self):
        # Assistant Admin may open FAC Admin, but neither settings DocType grants it read; a
        # group it cannot read would make the page's getdoc 403 and Frappe re-route the user.
        if not frappe.db.exists("User", ASSISTANT_ADMIN_USER):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": ASSISTANT_ADMIN_USER,
                    "first_name": "Assistant Admin",
                    "user_type": "System User",
                    "send_welcome_email": 0,
                    "roles": [{"role": "Assistant Admin"}],
                }
            ).insert(ignore_permissions=True)
        frappe.set_user(ASSISTANT_ADMIN_USER)
        try:
            self.assertEqual(get_settings_groups()["groups"], [])
        finally:
            frappe.set_user("Administrator")

    def _save_chat_settings_as_the_page_does(self):
        # The page sends back the doc it loaded, Password mask included, plus its edit.
        page_doc = frappe.get_single("FAC Chat Settings").as_dict()
        page_doc["max_context_tokens"] = (page_doc.get("max_context_tokens") or 0) + 1
        savedocs(json.dumps(page_doc, default=str), "Save")

    def test_saving_chat_settings_from_the_page_keeps_the_tenant_secret(self):
        # Production stores the secret at FAC Cloud registration through store_tenant_secret.
        store_tenant_secret(TENANT_SECRET)

        self._save_chat_settings_as_the_page_does()

        self.assertEqual(read_tenant_secret(), TENANT_SECRET)

    def test_saving_chat_settings_keeps_a_secret_whose_mask_is_blank(self):
        # Sites registered before store_tenant_secret kept the Singles mask in sync hold the
        # secret in __Auth with a blank mask (tenant_credentials.py, footgun 2).
        store_tenant_secret(TENANT_SECRET)
        frappe.db.set_single_value("FAC Chat Settings", "tenant_secret", "", update_modified=False)
        frappe.clear_document_cache("FAC Chat Settings", "FAC Chat Settings")

        self._save_chat_settings_as_the_page_does()

        self.assertEqual(read_tenant_secret(), TENANT_SECRET)
