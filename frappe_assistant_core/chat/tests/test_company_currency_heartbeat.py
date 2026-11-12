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

"""The site profile tells FAC Cloud the ERPNext company's currency and country.

FAC Cloud shows plan prices in that currency until the site saves a billing
address, so the profile carries it on every heartbeat, and one heartbeat is sent
as soon as registration completes rather than up to six hours later.
"""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import AssistantRuntimeClient

from frappe_assistant_core.chat import site_profile as site_profile_module
from frappe_assistant_core.chat.site_profile import company, site_profile
from frappe_assistant_core.chat.tests.test_pending_verification_actions import (
    TOKEN,
    PendingVerificationTestCase,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"


class TestCompany(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.exists("DocType", "Company"):
            self.skipTest("ERPNext is not installed")
        self.company = frappe.get_all("Company", fields=["name", "default_currency", "country"], limit=1)[0]

    def _code(self, country):
        return frappe.db.get_value("Country", country, "code").upper()

    def test_reads_the_default_company_erpnext_set(self):
        # Nothing patched: this reads the default ERPNext's setup wizard saved.
        default = frappe.db.get_single_value("Global Defaults", "default_company")
        if not default:
            self.skipTest("This site has no default company")
        expected = frappe.db.get_value("Company", default, ["default_currency", "country"], as_dict=True)
        self.assertEqual(
            company(), {"currency": expected.default_currency, "country": self._code(expected.country)}
        )

    def test_falls_back_to_the_only_company(self):
        with patch.object(site_profile_module, "_default_company", return_value=None), patch(
            "frappe.get_all", return_value=[self.company.name]
        ):
            facts = company()
        self.assertEqual(facts["currency"], self.company.default_currency)
        self.assertEqual(facts["country"], self._code(self.company.country))

    def test_several_companies_and_no_default_send_nothing(self):
        with patch.object(site_profile_module, "_default_company", return_value=None), patch(
            "frappe.get_all", return_value=[self.company.name, "Another Company"]
        ):
            self.assertEqual(company(), {})

    def test_without_erpnext_nothing_is_sent(self):
        real_exists = frappe.db.exists

        def exists(doctype, name=None, *args, **kwargs):
            if doctype == "DocType" and name == "Company":
                return None
            return real_exists(doctype, name, *args, **kwargs)

        with patch("frappe.db.exists", side_effect=exists):
            self.assertEqual(company(), {})


class TestSiteProfileCarriesTheCompany(BaseAssistantTest):
    def test_the_profile_has_a_company_section(self):
        facts = {"currency": "INR", "country": "IN"}
        with patch.object(site_profile_module, "company", return_value=facts):
            self.assertEqual(site_profile({})["company"], facts)

    def test_no_company_leaves_the_section_out(self):
        with patch.object(site_profile_module, "company", return_value={}):
            self.assertNotIn("company", site_profile({}))

    def test_a_failed_lookup_leaves_the_rest_of_the_profile(self):
        versions = {"frappe": {"version": "16.52.0"}}
        with patch.object(site_profile_module, "company", side_effect=RuntimeError("boom")):
            profile = site_profile(versions)
        self.assertNotIn("company", profile)
        self.assertEqual(profile["apps"], {"frappe": "16.52.0"})


class TestRegistrationReportsTheSite(PendingVerificationTestCase):
    def _register(self, ar_result):
        # Imported here: a TestCase in this module's namespace would run again.
        from frappe_assistant_core.chat.tests.test_pending_verification_actions import (
            RegisterStoresPendingTokenTests,
        )

        return RegisterStoresPendingTokenTests._register(self, ar_result)

    def _assert_heartbeat_queued(self, enqueue):
        enqueue.assert_called_once_with(
            "frappe_assistant_core.chat.api.billing.sync._send_heartbeat",
            enqueue_after_commit=True,
        )

    def test_after_email_verification(self):
        from frappe_assistant_core.chat.api.settings.registration import complete_email_verification

        verified = patch("requests.post")
        post = verified.start()
        self.addCleanup(verified.stop)
        post.return_value.json.return_value = {"message": {"verified": True, "tenant_id": "tenant-1"}}

        with patch(
            "assistant_runtime_sdk.client.get_initial_secret", return_value={"tenant_secret": "s" * 40}
        ), patch("frappe.enqueue") as enqueue:
            out = complete_email_verification(TOKEN)

        self.assertTrue(out["success"])
        self._assert_heartbeat_queued(enqueue)

    def test_not_while_verification_is_pending(self):
        with patch("frappe.enqueue") as enqueue:
            self._register({"tenant_id": "tenant-1", "verification_pending": True, "pending_token": TOKEN})
        enqueue.assert_not_called()

    def test_after_an_immediate_registration(self):
        with patch("frappe.enqueue") as enqueue, patch(
            "frappe_assistant_core.chat.quota_cache.update_from_ar"
        ):
            out = self._register({"tenant_id": "tenant-1", "tenant_secret": "s" * 40, "subscription": {}})
        self.assertTrue(out["success"], out)
        self._assert_heartbeat_queued(enqueue)


class TestBillingDetailsSuggestsTheCompanyCountry(BaseAssistantTest):
    def _details(self, on_file, country_code):
        from frappe_assistant_core.chat.api.billing.combined import get_billing_details

        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.get_billing_details.return_value = on_file
        facts = {"currency": "INR", "country": country_code} if country_code else {}
        with patch(CLIENT, return_value=client), patch.object(
            site_profile_module, "company", return_value=facts
        ), patch("frappe_assistant_core.chat.api.billing.combined._require_system_manager"):
            return get_billing_details()

    def test_suggests_the_company_country_when_none_is_saved(self):
        self.assertEqual(self._details({"billing_country": ""}, "IN")["suggested_country"], "IN")

    def test_suggests_nothing_once_a_country_is_saved(self):
        self.assertNotIn("suggested_country", self._details({"billing_country": "Kenya"}, "IN"))

    def test_suggests_nothing_without_a_company(self):
        self.assertNotIn("suggested_country", self._details({"billing_country": ""}, None))
