# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Marketplace writes need the same role as create_workflow, and errors stay clean.

Importing a workflow listing creates an AR Workflow; editing or deleting a
listing changes what the tenant publishes. Both were open to any logged-in
user. Raw exception text (table names, SQL, module paths) reached the toast.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api import marketplace
from frappe_assistant_core.chat.fac_cloud_client import ARAPIError
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
NON_ADMIN = "marketplace-viewer@example.com"


def _make_non_admin(email):
    # Production: any tenant user without the System Manager role (a plain member).
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "Viewer", "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    user.set("roles", [])
    user.save(ignore_permissions=True)


class _MarketClient:
    def __init__(self, listing_type="Workflow", raise_on=None):
        self.listing_type = listing_type
        self.raise_on = raise_on or {}
        self.calls = []

    def _maybe_raise(self, method):
        if method in self.raise_on:
            raise self.raise_on[method]

    def get_listing(self, **kwargs):
        self.calls.append(("get_listing", kwargs))
        self._maybe_raise("get_listing")
        return {
            "name": kwargs["name"],
            "listing_type": self.listing_type,
            "source": {"variables_schema": "{}"},
        }

    def import_listing(self, **kwargs):
        self.calls.append(("import_listing", kwargs))
        self._maybe_raise("import_listing")
        return {"target_doctype": "AR Workflow", "target_name": "WF-00009"}

    def update_listing(self, **kwargs):
        self.calls.append(("update_listing", kwargs))
        return {"ok": True}

    def delete_listing(self, **kwargs):
        self.calls.append(("delete_listing", kwargs))
        return {"ok": True}

    def called(self, method):
        return [kw for name, kw in self.calls if name == method]


class TestMarketplaceGuards(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        _make_non_admin(NON_ADMIN)
        self.addCleanup(frappe.set_user, "Administrator")

    def _as(self, user, client):
        # Production gets this client from get_fac_cloud_client() once the site is registered.
        frappe.set_user(user)
        p = patch(CLIENT, return_value=client)
        p.start()
        self.addCleanup(p.stop)

    def test_non_admin_cannot_import_a_workflow_listing(self):
        client = _MarketClient("Workflow")
        self._as(NON_ADMIN, client)
        with self.assertRaises(frappe.PermissionError):
            marketplace.import_listing(name="LST-1")
        self.assertEqual(client.called("import_listing"), [])

    def test_non_admin_may_still_import_a_prompt(self):
        client = _MarketClient("Prompt")
        self._as(NON_ADMIN, client)
        marketplace.import_listing(name="LST-2")
        self.assertEqual(len(client.called("import_listing")), 1)

    def test_import_denies_non_admin_when_listing_is_unclassifiable(self):
        for bad in (None, {}, {"name": "LST-1"}, {"listing_type": "Mystery"}):
            client = _MarketClient("Workflow")
            client.get_listing = lambda _bad=bad, **kw: _bad
            self._as(NON_ADMIN, client)
            with self.assertRaises(frappe.PermissionError, msg=repr(bad)):
                marketplace.import_listing(name="LST-1")
            self.assertEqual(client.called("import_listing"), [], msg=repr(bad))

    def test_admin_imports_a_workflow(self):
        client = _MarketClient("Workflow")
        self._as("Administrator", client)
        marketplace.import_listing(name="LST-1")
        self.assertEqual(len(client.called("import_listing")), 1)

    def test_non_admin_cannot_update_or_delete(self):
        client = _MarketClient()
        self._as(NON_ADMIN, client)
        with self.assertRaises(frappe.PermissionError):
            marketplace.update_listing(name="LST-1", title="x")
        with self.assertRaises(frappe.PermissionError):
            marketplace.delete_listing(name="LST-1")
        self.assertEqual(client.calls, [])


class TestMarketplaceErrorsAreClean(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")

    def _import_raising(self, error):
        # The SDK raises ARAPIError for non-2xx answers other than 401 (ARAuthenticationError),
        # 429 and timeouts; response_data holds the parsed JSON body when there is one.
        client = _MarketClient(raise_on={"import_listing": error})
        with patch(CLIENT, return_value=client), self.assertRaises(frappe.ValidationError) as caught:
            marketplace.import_listing(name="LST-1")
        return str(caught.exception)

    def test_a_4xx_shows_fac_clouds_own_message(self):
        message = self._import_raising(
            ARAPIError(
                "Your plan does not include this listing.",
                status_code=403,
                response_data={
                    "exception": "frappe.exceptions.ValidationError: Your plan does not include this listing."
                },
            )
        )
        self.assertIn("Your plan does not include this listing.", message)
        self.assertNotIn("HTTP_403", message)

    def test_a_5xx_never_shows_internals(self):
        message = self._import_raising(
            ARAPIError('(1054, "Unknown column in `tabAR Marketplace Listing`")', status_code=500)
        )
        self.assertNotIn("tabAR", message)
        self.assertNotIn("1054", message)
        self.assertIn("marketplace could not complete", message)

    def test_a_missing_listing_reads_as_not_found(self):
        client = _MarketClient(
            raise_on={
                "get_listing": ARAPIError(
                    "Listing not found",
                    status_code=404,
                    response_data={"exception": "frappe.exceptions.DoesNotExistError: Listing not found"},
                )
            }
        )
        with patch(CLIENT, return_value=client), self.assertRaises(frappe.ValidationError) as caught:
            marketplace.import_listing(name="LST-404")
        self.assertIn("Listing not found", str(caught.exception))

    def test_a_non_json_4xx_never_shows_the_request_url(self):
        message = self._import_raising(
            ARAPIError(
                "404 Client Error: Not Found for url: https://ar.example/api/method/x?tenant_id=T",
                status_code=404,
            )
        )
        self.assertNotIn("ar.example", message)
        self.assertNotIn("tenant_id", message)
        self.assertIn("marketplace could not complete", message)

    def test_a_json_4xx_without_a_message_never_shows_the_request_url(self):
        # The SDK builds its message from str(HTTPError) when the JSON body has no
        # message key, so response_data is non-empty and the text embeds the URL.
        message = self._import_raising(
            ARAPIError(
                "404 Client Error: Not Found for url: https://ar.example/api/method/x?tenant_id=T",
                status_code=404,
                response_data={"exc_type": "DoesNotExistError"},
            )
        )
        self.assertNotIn("ar.example", message)
        self.assertNotIn("tenant_id", message)
        self.assertIn("marketplace could not complete", message)
