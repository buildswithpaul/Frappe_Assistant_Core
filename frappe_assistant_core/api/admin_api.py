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

"""
Admin API facade — re-exports all whitelisted functions from submodules.

This preserves the ``frappe_assistant_core.api.admin_api.<fn>`` method path
used by all frontend ``frappe.call()`` invocations and test imports.

The ``@frappe.whitelist()`` decorator in each submodule registers the
function object when the submodule first executes. Re-importing here gives
the same object, so Frappe's whitelist check passes transparently.
"""

# Server settings
# Plugin management
from frappe_assistant_core.api.admin.plugins import (  # noqa: F401
    get_plugin_stats,
    get_tool_registry,
    get_tool_stats,
    toggle_plugin,
)

# Prompt template management
from frappe_assistant_core.api.admin.prompts import (  # noqa: F401
    get_prompt_templates_list,
    preview_prompt_template,
    toggle_prompt_template_status,
)
from frappe_assistant_core.api.admin.server import (  # noqa: F401
    get_server_settings,
    update_server_settings,
)

# Skill management
from frappe_assistant_core.api.admin.skills import (  # noqa: F401
    get_skills_list,
    toggle_skill_status,
)

# Usage statistics & connectivity
from frappe_assistant_core.api.admin.stats import (  # noqa: F401
    get_usage_statistics,
    ping,
)

# Tool configuration
from frappe_assistant_core.api.admin.tools import (  # noqa: F401
    bulk_toggle_tools,
    bulk_toggle_tools_by_category,
    get_available_roles,
    get_tool_configurations,
    toggle_tool,
    update_tool_category,
    update_tool_role_access,
)
