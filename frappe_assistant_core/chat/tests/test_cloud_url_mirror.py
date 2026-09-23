# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The FAC Chat Settings `fac_cloud_url` field is a mirror, not a setting.

`sync_cloud_url_mirror` runs on migrate so Desk and the SPA show where the site
actually points. Its second job matters more: a site that gets new code before
its site_config is updated would otherwise repoint silently — still "working",
but signing requests with credentials the new server never issued. This turns
that into a named Error Log instead of a mystery auth failure.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat import cloud_url
from frappe_assistant_core.tests.base_test import BaseAssistantTest

OLD_URL = "https://dev.fac-cloud.com"


class TestSyncCloudUrlMirror(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # The enclosing transaction is per-class, so rows written by an earlier
        # test are still visible here. Count only what this test produces.
        self._preexisting = {row.name for row in self._all_drift_logs()}

    @staticmethod
    def _all_drift_logs():
        return frappe.get_all("Error Log", filters={"method": cloud_url.DRIFT_LOG_TITLE})

    def _with_conf(self, value):
        conf = frappe._dict(frappe.conf)
        if value is None:
            conf.pop("fac_cloud_url", None)
        else:
            conf["fac_cloud_url"] = value
        return patch.object(frappe.local, "conf", conf)

    def _seed(self, mirror, status):
        frappe.db.set_single_value("FAC Chat Settings", "fac_cloud_url", mirror)
        frappe.db.set_single_value("FAC Chat Settings", "registration_status", status)

    def _drift_logs(self):
        return [row for row in self._all_drift_logs() if row.name not in self._preexisting]

    def test_mirror_is_refreshed_to_the_resolved_url(self):
        self._seed(OLD_URL, "Registered")
        with self._with_conf("http://localhost:8001"):
            cloud_url.sync_cloud_url_mirror()
        self.assertEqual(
            frappe.db.get_single_value("FAC Chat Settings", "fac_cloud_url"),
            "http://localhost:8001",
        )

    def test_repointing_a_registered_site_logs_both_urls(self):
        self._seed(OLD_URL, "Registered")
        with self._with_conf(None):  # no override => falls back to production
            cloud_url.sync_cloud_url_mirror()

        logs = self._drift_logs()
        self.assertEqual(len(logs), 1, "a repointed registered site must leave exactly one log")
        message = frappe.db.get_value("Error Log", logs[0].name, "error")
        self.assertIn(OLD_URL, message)
        self.assertIn(cloud_url.PRODUCTION_FAC_CLOUD_URL, message)

    def test_unchanged_url_is_not_drift(self):
        self._seed(OLD_URL, "Registered")
        with self._with_conf(OLD_URL):
            cloud_url.sync_cloud_url_mirror()
        self.assertEqual(self._drift_logs(), [])

    def test_a_trailing_slash_alone_is_not_drift(self):
        self._seed(OLD_URL, "Registered")
        with self._with_conf(OLD_URL + "/"):
            cloud_url.sync_cloud_url_mirror()
        self.assertEqual(self._drift_logs(), [])

    def test_unregistered_site_has_no_binding_to_break(self):
        self._seed(OLD_URL, "Not Registered")
        with self._with_conf(None):
            cloud_url.sync_cloud_url_mirror()
        self.assertEqual(self._drift_logs(), [])

    def test_fresh_site_with_an_empty_mirror_is_not_drift(self):
        self._seed("", "Registered")
        with self._with_conf(None):
            cloud_url.sync_cloud_url_mirror()
        self.assertEqual(self._drift_logs(), [])
