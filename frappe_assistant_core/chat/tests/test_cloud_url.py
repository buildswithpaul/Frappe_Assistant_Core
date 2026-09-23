"""Which AR server this site talks to.

`fac_cloud_url` is environment identity, not a user preference: the tenant
credentials are issued by whichever server it names, so pointing a registered
site somewhere else silently invalidates them. Resolution therefore lives in
site_config (per-site, outside git, devops-managed) with production compiled in
as the fallback.
"""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat import cloud_url


class TestGetFacCloudUrl(unittest.TestCase):
    def _with_conf(self, value):
        conf = frappe._dict(frappe.conf)
        if value is None:
            conf.pop("fac_cloud_url", None)
        else:
            conf["fac_cloud_url"] = value
        return patch.object(frappe.local, "conf", conf)

    def test_falls_back_to_production_when_site_config_is_silent(self):
        with self._with_conf(None):
            self.assertEqual(cloud_url.get_fac_cloud_url(), cloud_url.PRODUCTION_FAC_CLOUD_URL)

    def test_site_config_overrides_production(self):
        with self._with_conf("https://dev.fac-cloud.com"):
            self.assertEqual(cloud_url.get_fac_cloud_url(), "https://dev.fac-cloud.com")

    def test_local_ar_on_another_port_is_a_valid_override(self):
        with self._with_conf("http://localhost:8001"):
            self.assertEqual(cloud_url.get_fac_cloud_url(), "http://localhost:8001")

    def test_trailing_slash_is_stripped_so_callers_can_concatenate_paths(self):
        with self._with_conf("https://dev.fac-cloud.com/"):
            self.assertEqual(cloud_url.get_fac_cloud_url(), "https://dev.fac-cloud.com")

    def test_blank_site_config_value_is_not_an_override(self):
        # set-config with an empty string must not strand the site on "".
        with self._with_conf("   "):
            self.assertEqual(cloud_url.get_fac_cloud_url(), cloud_url.PRODUCTION_FAC_CLOUD_URL)

    def test_production_default_is_the_api_host(self):
        self.assertEqual(cloud_url.PRODUCTION_FAC_CLOUD_URL, "https://api.fac-cloud.com")
