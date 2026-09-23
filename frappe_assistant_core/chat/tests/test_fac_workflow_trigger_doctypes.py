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

from frappe_assistant_core.tests.base_test import BaseAssistantTest

_FACO_INSTALLED_MSG = (
    "frappe_assistant_copilot is installed on this site; "
    "it defines the same DocType names and its module sync runs last — "
    "module will read 'Frappe Assistant Copilot' until FACO is removed."
)


class TestFACWorkflowTriggerDoctypes(BaseAssistantTest):
    """The 3 FAC Workflow Trigger DocTypes live in the Chat module.

    When frappe_assistant_copilot is installed alongside frappe_assistant_core
    on the same site, FACO's migrate sync runs after FAC's and wins the module
    field (both apps declare the same DocType names). The module assertions are
    skipped in that case; they will pass on a FAC-only site.
    """

    def _faco_installed(self) -> bool:
        return "frappe_assistant_copilot" in frappe.get_installed_apps()

    def test_fac_workflow_trigger_module_is_chat(self):
        if self._faco_installed():
            self.skipTest(_FACO_INSTALLED_MSG)
        meta = frappe.get_meta("FAC Workflow Trigger")
        self.assertEqual(meta.module, "Chat")
        self.assertEqual(meta.name, "FAC Workflow Trigger")

    def test_fac_workflow_trigger_filter_module_is_chat(self):
        if self._faco_installed():
            self.skipTest(_FACO_INSTALLED_MSG)
        meta = frappe.get_meta("FAC Workflow Trigger Filter")
        self.assertEqual(meta.module, "Chat")
        self.assertEqual(meta.name, "FAC Workflow Trigger Filter")

    def test_fac_workflow_trigger_filter_is_child_table(self):
        """fac_workflow_trigger_filter is a child table (istable=1).

        This assertion holds regardless of which app owns the module.
        """
        meta = frappe.get_meta("FAC Workflow Trigger Filter")
        self.assertTrue(meta.istable)

    def test_fac_workflow_trigger_log_module_is_chat(self):
        if self._faco_installed():
            self.skipTest(_FACO_INSTALLED_MSG)
        meta = frappe.get_meta("FAC Workflow Trigger Log")
        self.assertEqual(meta.module, "Chat")
        self.assertEqual(meta.name, "FAC Workflow Trigger Log")

    def test_python_controllers_importable(self):
        from frappe_assistant_core.chat.doctype.fac_workflow_trigger.fac_workflow_trigger import (
            FACWorkflowTrigger,
        )
        from frappe_assistant_core.chat.doctype.fac_workflow_trigger_filter.fac_workflow_trigger_filter import (
            FACWorkflowTriggerFilter,
        )
        from frappe_assistant_core.chat.doctype.fac_workflow_trigger_log.fac_workflow_trigger_log import (
            FACWorkflowTriggerLog,
        )

        self.assertEqual(FACWorkflowTrigger.__name__, "FACWorkflowTrigger")
        self.assertEqual(FACWorkflowTriggerFilter.__name__, "FACWorkflowTriggerFilter")
        self.assertEqual(FACWorkflowTriggerLog.__name__, "FACWorkflowTriggerLog")
