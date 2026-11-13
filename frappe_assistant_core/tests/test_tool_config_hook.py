# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The `assistant_tool_configs` hook must reach a tool's get_config().

An app overrides a tool's default_config by declaring, in its hooks.py:

    assistant_tool_configs = {"simple_greeting": {"max_name_length": 100}}

BaseTool._get_app_config imported `get_hooks` from `frappe.utils`, which has no
such name, and a bare `except` turned the ImportError into an empty config. The
hook never applied to any tool. Reading it through frappe.get_hooks would not
work either: Frappe merges dict hooks by turning every value into a list
({"max_name_length": [100]}).
"""

import sys
import types
from unittest.mock import patch

import frappe

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.tests.base_test import BaseAssistantTest

FIRST_APP = "fac_test_tool_config_first"
SECOND_APP = "fac_test_tool_config_second"


class _ConfiguredTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "fac_test_configured_tool"
        self.default_config = {"max_rows": 10, "style": "plain", "doctypes": ["Item"]}

    def execute(self, arguments):
        return {}


def _hooks_module(app, tool_configs):
    module = types.ModuleType(f"{app}.hooks")
    module.assistant_tool_configs = tool_configs
    return module


class TestToolConfigHook(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # An installed app is reached through its `<app>.hooks` module, the way
        # an app such as byot declares assistant_tool_configs in production.
        installed = frappe.get_installed_apps()
        self.modules = {
            f"{FIRST_APP}.hooks": _hooks_module(
                FIRST_APP,
                {"fac_test_configured_tool": {"max_rows": 100, "doctypes": ["Customer", "Supplier"]}},
            ),
            f"{SECOND_APP}.hooks": _hooks_module(
                SECOND_APP,
                {"fac_test_configured_tool": {"style": "fancy"}, "another_tool": {"max_rows": 1}},
            ),
        }
        patcher = patch.dict(sys.modules, self.modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        apps = patch(
            "frappe.get_installed_apps",
            autospec=True,
            return_value=[*installed, FIRST_APP, SECOND_APP],
        )
        apps.start()
        self.addCleanup(apps.stop)

    def test_an_apps_settings_override_the_tool_defaults(self):
        config = _ConfiguredTool().get_config()

        self.assertEqual(config["max_rows"], 100)
        self.assertEqual(config["style"], "fancy")

    def test_a_list_setting_arrives_as_the_list_the_app_wrote(self):
        config = _ConfiguredTool().get_config()

        self.assertEqual(config["doctypes"], ["Customer", "Supplier"])

    def test_a_later_app_overrides_an_earlier_one(self):
        self.modules[f"{SECOND_APP}.hooks"].assistant_tool_configs["fac_test_configured_tool"]["max_rows"] = 5

        config = _ConfiguredTool().get_config()

        self.assertEqual(config["max_rows"], 5)

    def test_site_config_still_overrides_the_apps(self):
        with patch.dict(frappe.conf, {"assistant_tools": {"fac_test_configured_tool": {"max_rows": 7}}}):
            config = _ConfiguredTool().get_config()

        self.assertEqual(config["max_rows"], 7)
        self.assertEqual(config["style"], "fancy")

    def test_a_malformed_entry_is_skipped(self):
        self.modules[f"{FIRST_APP}.hooks"].assistant_tool_configs = {"fac_test_configured_tool": ["max_rows"]}

        config = _ConfiguredTool().get_config()

        self.assertEqual(config["max_rows"], 10)
        self.assertEqual(config["style"], "fancy")
