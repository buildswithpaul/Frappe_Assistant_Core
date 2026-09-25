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

"""The install welcome email must be FAC Cloud onboarding, not the OSS one.

Also guards the defect this file was rewritten for: FAC runs on the
customer's own site, `assistant_runtime` (the SaaS server) runs on a separate
deployment, and FAC only ever depends on `assistant_runtime_sdk`. Nothing
under the `frappe_assistant_core` package may import `assistant_runtime` at
module scope, or a real customer install ImportErrors — and since this exact
email used to be sent from an install hook, it would fail the install itself.

The guard covers test modules too. It did not until 3.0, and two chat tests
duly imported AR's test base: locally they passed, because AR happens to be
installed on the development bench, while CI could not so much as discover
the suite.
"""

import os
import re
from unittest.mock import patch

import frappe
from frappe.utils.jinja import get_email_from_template

from frappe_assistant_core.chat.gate import clear_chat_gate_cache
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.email_invite import send_fac_admin_invite

RETIRED_CONTENT = (
    "github.com",
    "erp.promantia.in",
    "ai-support@promantia.com",
    "b-cdn.net",
    "FAC Starter",
    "FAC Pro",
    "ask Claude",
)

# Anchored at column 0 (true module scope, not an indented/lazy import) and
# word-bounded so `assistant_runtime_sdk` — the allowed client library —
# never matches: the boundary check fails on the "_" right after "runtime".
ASSISTANT_RUNTIME_IMPORT = re.compile(r"^(?:from|import)\s+assistant_runtime\b", re.MULTILINE)

# Directories that are not part of the importable `frappe_assistant_core`
# package at all.
_SKIP_DIRS = {"node_modules", "__pycache__", ".git"}


def _rendered_message(sendmail_mock):
    kwargs = sendmail_mock.call_args.kwargs
    message, _text = get_email_from_template(kwargs["template"], kwargs["args"])
    return message


def _package_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for filename in filenames:
            if filename.endswith(".py"):
                yield os.path.join(dirpath, filename)


def _assistant_runtime_import_violations():
    root = frappe.get_app_path("frappe_assistant_core")
    violations = []
    for path in _package_py_files(root):
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        if ASSISTANT_RUNTIME_IMPORT.search(content):
            violations.append(os.path.relpath(path, root))
    return violations


class TestFacWelcomeEmail(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)
        frappe.clear_cache()
        clear_chat_gate_cache()
        self.addCleanup(clear_chat_gate_cache)

    def test_chat_disabled_sends_nothing(self):
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 0)
        frappe.clear_cache()
        clear_chat_gate_cache()
        with patch(
            "frappe_assistant_core.utils.email_invite._get_system_manager_emails"
        ) as recipients, patch("frappe_assistant_core.utils.email_invite.frappe.sendmail") as sendmail:
            send_fac_admin_invite()

        recipients.assert_not_called()
        sendmail.assert_not_called()

    def test_missing_chat_field_sends_nothing(self):
        with patch.object(
            frappe.db,
            "get_single_value",
            side_effect=frappe.ValidationError("Field enable_fac_chat does not exist"),
        ), patch("frappe_assistant_core.utils.email_invite._get_system_manager_emails") as recipients, patch(
            "frappe_assistant_core.utils.email_invite.frappe.sendmail"
        ) as sendmail:
            send_fac_admin_invite()

        recipients.assert_not_called()
        sendmail.assert_not_called()

    def test_welcome_email_is_fac_cloud_branded(self):
        with patch(
            "frappe_assistant_core.utils.email_invite._get_system_manager_emails",
            return_value=["admin@acme.com"],
        ), patch("frappe_assistant_core.utils.email_invite.frappe.sendmail", return_value=True) as sendmail:
            send_fac_admin_invite()

        sendmail.assert_called_once_with(
            recipients=["admin@acme.com"],
            subject=frappe._("Your FAC Cloud workspace is ready"),
            template="fac_welcome",
            args={"heading": frappe._("You're all set"), "cta_url": frappe.utils.get_url("/copilot/")},
            delayed=True,
        )
        message = _rendered_message(sendmail)
        self.assertIn("FAC Cloud", message)
        self.assertNotIn("Frappe Assistant Core", message)

    def test_welcome_email_drops_every_retired_link_and_pitch(self):
        with patch(
            "frappe_assistant_core.utils.email_invite._get_system_manager_emails",
            return_value=["admin@acme.com"],
        ), patch("frappe_assistant_core.utils.email_invite.frappe.sendmail", return_value=True) as sendmail:
            send_fac_admin_invite()

        message = _rendered_message(sendmail)
        for retired in RETIRED_CONTENT:
            with self.subTest(retired=retired):
                self.assertNotIn(retired, message)

    def test_no_recipients_sends_nothing(self):
        with patch(
            "frappe_assistant_core.utils.email_invite._get_system_manager_emails",
            return_value=[],
        ), patch("frappe_assistant_core.utils.email_invite.frappe.sendmail") as sendmail:
            send_fac_admin_invite()

        sendmail.assert_not_called()

    def test_package_never_imports_assistant_runtime_at_module_scope(self):
        self.assertEqual(_assistant_runtime_import_violations(), [])
