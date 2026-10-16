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

"""Assistant Core Settings' plugin-status HTML draws icons Desk can render on v15 and v16."""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.assistant_core.doctype.assistant_core_settings.assistant_core_settings import (
    _icon,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

FRAPPE_MAJOR = int(frappe.__version__.split(".")[0])


class TestAssistantCoreSettingsIcons(BaseAssistantTest):
    def test_v16_uses_lucide_sprite(self):
        with patch.object(frappe, "__version__", "16.52.0"):
            html = _icon("puzzle", "fa-puzzle-piece")
        self.assertIn('href="#icon-puzzle"', html)
        self.assertNotIn("fa-puzzle-piece", html)

    def test_v15_uses_font_awesome(self):
        with patch.object(frappe, "__version__", "15.82.1"):
            html = _icon("puzzle", "fa-puzzle-piece")
        self.assertEqual(html, '<i class="fa fa-puzzle-piece" aria-hidden="true"></i>')

    @unittest.skipIf(FRAPPE_MAJOR < 16, "Font Awesome is still bundled on Frappe 15")
    def test_plugin_status_html_has_no_font_awesome_on_v16(self):
        html = frappe.get_single("Assistant Core Settings").get_plugin_status()["html"]
        self.assertNotIn('class="fa ', html)
        self.assertIn('href="#icon-settings-2"', html)
