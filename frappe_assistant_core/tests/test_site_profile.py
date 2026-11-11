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

"""The site profile the FAC Cloud heartbeat sends (#34906): apps, customisation counts and
the web-server setup. Counts and verdicts only, never record contents, names or messages.
"""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import AssistantRuntimeClient

from frappe_assistant_core.chat import site_profile as site_profile_module
from frappe_assistant_core.chat.api.billing import sync
from frappe_assistant_core.chat.site_profile import site_profile
from frappe_assistant_core.tests.base_test import BaseAssistantTest

REPORT = {
    "source": "gunicorn",
    "worker_class": "sync",
    "workers": 2,
    "threads": 1,
    "timeout": 120,
    "status": "warning",
    "slots": 2,
    "required_slots": 20,
    "reasons": ["Gunicorn runs sync workers..."],
    "fix": "--worker-class gthread --threads 8",
    "relay": {
        "status": "warning",
        "enabled": True,
        "queue_configured": True,
        "workers": 2,
        "busy": 1,
        "queued": 0,
        "required_workers": 10,
        "reasons": ["Only 2 relay workers..."],
        "fix": "bench worker --queue faco_relay",
    },
}


class TestSiteProfile(BaseAssistantTest):
    def test_apps_come_from_the_versions_given(self):
        versions = {"frappe": {"version": "16.52.0"}, "erpnext": {"version": "16.20.1"}}
        self.assertEqual(site_profile(versions)["apps"], {"frappe": "16.52.0", "erpnext": "16.20.1"})

    def test_a_new_client_script_is_counted(self):
        before = site_profile({})["customisations"]["client_scripts"]
        frappe.get_doc(
            {
                "doctype": "Client Script",
                "name": "FAC Site Profile Probe",
                "dt": "ToDo",
                "script": "// probe",
                "enabled": 0,
            }
        ).insert(ignore_permissions=True)
        self.assertEqual(site_profile({})["customisations"]["client_scripts"], before + 1)

    def test_a_disabled_server_script_counts_but_is_not_active(self):
        before = site_profile({})["customisations"]
        frappe.get_doc(
            {
                "doctype": "Server Script",
                "name": "FAC Site Profile Probe",
                "script_type": "API",
                "api_method": "fac_site_profile_probe",
                "script": "pass",
                "disabled": 1,
            }
        ).insert(ignore_permissions=True)

        after = site_profile({})["customisations"]
        self.assertEqual(after["server_scripts"], before["server_scripts"] + 1)
        self.assertEqual(after["active_server_scripts"], before["active_server_scripts"])

    def test_the_setup_report_keeps_figures_and_verdicts_but_no_text(self):
        with patch.object(site_profile_module, "server_setup_report", autospec=True, return_value=REPORT):
            profile = site_profile({})

        self.assertEqual(
            profile["web_server"],
            {
                "source": "gunicorn",
                "worker_class": "sync",
                "workers": 2,
                "threads": 1,
                "slots": 2,
                "required_slots": 20,
                "status": "warning",
            },
        )
        self.assertEqual(
            profile["relay"], {"status": "warning", "enabled": True, "workers": 2, "required_workers": 10}
        )

    def test_a_section_that_fails_is_left_out_and_the_rest_is_sent(self):
        with patch.object(
            site_profile_module, "server_setup_report", autospec=True, side_effect=RuntimeError("no psutil")
        ):
            profile = site_profile({"frappe": {"version": "16.52.0"}})

        self.assertNotIn("web_server", profile)
        self.assertNotIn("relay", profile)
        self.assertIn("customisations", profile)
        self.assertEqual(profile["apps"], {"frappe": "16.52.0"})


class TestHeartbeatSendsSiteProfile(BaseAssistantTest):
    def test_the_heartbeat_sends_the_site_profile(self):
        # autospec of the real SDK client: a heartbeat() without site_profile raises TypeError here
        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.heartbeat.return_value = {"status": "ok"}
        profile = {"apps": {"frappe": "16.52.0"}}

        with (
            patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client),
            patch.object(sync, "site_profile", autospec=True, return_value=profile),
        ):
            sync._send_heartbeat()

        self.assertEqual(client.heartbeat.call_args.kwargs["site_profile"], profile)
