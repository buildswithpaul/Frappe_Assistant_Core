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

"""The tools that can answer with an MCP task, each with the adapter its tasks are polled through.

``tasks`` imports this lazily, when a task's adapter is missing, so a worker that never served the
task's tools/call still finds it. Importing it at the top of ``tasks`` would be a cycle: the tools
import ``tasks`` for the task marker.
"""

from frappe_assistant_core.mcp.tasks import register_adapter
from frappe_assistant_core.plugins.core.tools.report_tools import prepared_report_task_progress
from frappe_assistant_core.plugins.migration.tools.run_migration_plan import plan_task_progress
from frappe_assistant_core.plugins.migration.tools.start_import import import_task_progress


def register() -> None:
    register_adapter("generate_report", prepared_report_task_progress)
    register_adapter("start_import", import_task_progress)
    register_adapter("run_migration_plan", plan_task_progress)
