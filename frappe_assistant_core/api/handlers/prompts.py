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
Prompts handlers for MCP protocol - Database-driven implementation
Handles prompts/list and prompts/get requests with DocType-backed templates
"""

import re
from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from jinja2 import BaseLoader, Environment, TemplateSyntaxError

from frappe_assistant_core.constants.definitions import (
    ErrorCodes,
    ErrorMessages,
    LogMessages,
)
from frappe_assistant_core.utils.logger import api_logger


class PromptTemplateManager:
    """
    Centralized manager for prompt template operations.
    Handles querying, filtering, rendering, and permission checking.
    """

    def __init__(self):
        self.logger = frappe.logger("prompt_template_manager")
        self._jinja_env = Environment(loader=BaseLoader())

    def get_user_accessible_prompts(self, user: str = None) -> List[Dict[str, Any]]:
        """
        Get all prompts accessible to the current user.

        Includes:
        - User's own prompts (any status)
        - Published + Public prompts
        - Published + Shared prompts (if user has required role)
        - Published + System prompts

        Args:
            user: User email (defaults to current session user)

        Returns:
            List of prompt info dicts
        """
        user = user or frappe.session.user
        user_roles = frappe.get_roles(user)

        prompts = []
        seen_ids = set()

        # 1. User's own prompts (any status)
        own_prompts = frappe.get_all(
            "Prompt Template",
            filters={"owner_user": user},
            fields=["name", "prompt_id", "title", "description", "status", "category"],
        )
        for p in own_prompts:
            if p.prompt_id not in seen_ids:
                seen_ids.add(p.prompt_id)
                prompts.append(p)

        # 2. Published public prompts
        public_prompts = frappe.get_all(
            "Prompt Template",
            filters={"status": "Published", "visibility": "Public", "owner_user": ["!=", user]},
            fields=["name", "prompt_id", "title", "description", "status", "category"],
        )
        for p in public_prompts:
            if p.prompt_id not in seen_ids:
                seen_ids.add(p.prompt_id)
                prompts.append(p)

        # 3. Published shared prompts where user has required role
        shared_prompts = self._get_shared_prompts_for_user(user, user_roles)
        for p in shared_prompts:
            if p.prompt_id not in seen_ids:
                seen_ids.add(p.prompt_id)
                prompts.append(p)

        # 4. System prompts (is_system=1, status=Published)
        system_prompts = frappe.get_all(
            "Prompt Template",
            filters={"is_system": 1, "status": "Published", "owner_user": ["!=", user]},
            fields=["name", "prompt_id", "title", "description", "status", "category"],
        )
        for p in system_prompts:
            if p.prompt_id not in seen_ids:
                seen_ids.add(p.prompt_id)
                prompts.append(p)

        return prompts

    def _get_shared_prompts_for_user(self, user: str, user_roles: List[str]) -> List[Dict]:
        """Get prompts shared with roles that user has."""
        if not user_roles:
            return []

        try:
            shared_prompts = frappe.db.sql(
                """
                SELECT DISTINCT pt.name, pt.prompt_id, pt.title, pt.description,
                       pt.status, pt.category
                FROM `tabPrompt Template` pt
                INNER JOIN `tabHas Role` hr ON hr.parent = pt.name
                    AND hr.parenttype = 'Prompt Template'
                WHERE pt.status = 'Published'
                  AND pt.visibility = 'Shared'
                  AND hr.role IN %(roles)s
                  AND pt.owner_user != %(user)s
            """,
                {"roles": user_roles, "user": user},
                as_dict=True,
            )
            return shared_prompts
        except Exception as e:
            self.logger.warning(f"Error fetching shared prompts: {e}")
            return []

    def get_prompt_for_mcp(self, prompt_doc) -> Dict[str, Any]:
        """
        Convert prompt template doc to MCP format.

        Args:
            prompt_doc: Prompt Template document

        Returns:
            Dict in MCP prompts/list format
        """
        arguments = []
        for arg in prompt_doc.arguments:
            # Build description with options for select types
            description = arg.description or arg.display_label or arg.argument_name

            # For select/multiselect, append options to description for better visibility
            options = None
            if arg.argument_type in ("select", "multiselect") and arg.allowed_values:
                options = [v.strip() for v in arg.allowed_values.split(",")]
                options_str = ", ".join(options)
                description = f"{description}. Options: {options_str}"
                if arg.default_value:
                    description = f"{description}. Default: {arg.default_value}"

            arg_data = {
                "name": arg.argument_name,
                "description": description,
                "required": bool(arg.is_required),
            }

            # Include enum for select/multiselect types (non-standard but useful)
            if options:
                arg_data["enum"] = options

            # Include default value if set
            if arg.default_value:
                arg_data["default"] = arg.default_value

            arguments.append(arg_data)

        result = {
            "name": prompt_doc.prompt_id,
            "title": prompt_doc.title,
            "description": prompt_doc.description,
            "arguments": arguments,
        }

        # Include category if set (non-standard MCP field but useful for organization)
        if prompt_doc.category:
            result["category"] = prompt_doc.category

        return result

    def render_prompt(self, prompt_doc, arguments: Dict[str, Any]) -> str:
        """
        Render prompt template with provided arguments.

        Supports multiple rendering engines:
        - Jinja2 (default): Full Jinja2 templating
        - Format String: Python str.format() style
        - Raw: No substitution

        Args:
            prompt_doc: Prompt Template document
            arguments: Dict of argument values

        Returns:
            Rendered template string
        """
        template_content = prompt_doc.template_content
        engine = prompt_doc.rendering_engine or "Jinja2"

        # Validate required arguments
        self._validate_arguments(prompt_doc, arguments)

        # Apply defaults for missing optional arguments
        arguments = self._apply_defaults(prompt_doc, arguments)

        if engine == "Jinja2":
            return self._render_jinja(template_content, arguments)
        elif engine == "Format String":
            return self._render_format_string(template_content, arguments)
        else:  # Raw
            return template_content

    def _validate_arguments(self, prompt_doc, arguments: Dict[str, Any]):
        """Validate arguments against template definition."""
        for arg_def in prompt_doc.arguments:
            if arg_def.is_required and arg_def.argument_name not in arguments:
                frappe.throw(
                    _("Missing required argument: {0}").format(arg_def.argument_name), frappe.ValidationError
                )

            value = arguments.get(arg_def.argument_name)
            if value is not None:
                # Type validation
                self._validate_argument_type(arg_def, value)

                # Pattern validation
                if arg_def.validation_regex:
                    if not re.match(arg_def.validation_regex, str(value)):
                        frappe.throw(
                            _("Argument {0} does not match required pattern").format(arg_def.argument_name),
                            frappe.ValidationError,
                        )

                # Allowed values validation
                if arg_def.argument_type in ("select", "multiselect") and arg_def.allowed_values:
                    allowed = [v.strip() for v in arg_def.allowed_values.split(",")]
                    if arg_def.argument_type == "select" and value not in allowed:
                        frappe.throw(
                            _("Argument {0} must be one of: {1}").format(
                                arg_def.argument_name, ", ".join(allowed)
                            ),
                            frappe.ValidationError,
                        )

    def _validate_argument_type(self, arg_def, value):
        """Validate argument value matches expected type."""
        arg_type = arg_def.argument_type

        if arg_type == "number":
            if not isinstance(value, (int, float)):
                try:
                    float(value)
                except (ValueError, TypeError):
                    frappe.throw(
                        _("Argument {0} must be a number").format(arg_def.argument_name),
                        frappe.ValidationError,
                    )
        elif arg_type == "boolean":
            valid_bools = (True, False, "true", "false", "1", "0", 1, 0)
            if value not in valid_bools:
                frappe.throw(
                    _("Argument {0} must be a boolean").format(arg_def.argument_name), frappe.ValidationError
                )

    def _apply_defaults(self, prompt_doc, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values for missing optional arguments."""
        result = arguments.copy()
        for arg_def in prompt_doc.arguments:
            if arg_def.argument_name not in result and arg_def.default_value:
                result[arg_def.argument_name] = arg_def.default_value
        return result

    def _render_jinja(self, template: str, arguments: Dict[str, Any]) -> str:
        """Render using Jinja2."""
        try:
            jinja_template = self._jinja_env.from_string(template)
            return jinja_template.render(**arguments)
        except TemplateSyntaxError as e:
            frappe.throw(_("Template syntax error: {0}").format(str(e)), frappe.ValidationError)

    def _render_format_string(self, template: str, arguments: Dict[str, Any]) -> str:
        """Render using Python format strings."""
        try:
            return template.format(**arguments)
        except KeyError as e:
            frappe.throw(_("Missing argument for format string: {0}").format(str(e)), frappe.ValidationError)

    def increment_usage(self, prompt_name: str):
        """Increment usage counter for analytics."""
        try:
            frappe.db.sql(
                """
                UPDATE `tabPrompt Template`
                SET use_count = use_count + 1, last_used = NOW()
                WHERE name = %s
            """,
                (prompt_name,),
            )
        except Exception as e:
            self.logger.warning(f"Failed to increment usage for {prompt_name}: {e}")


# Global manager instance
_prompt_manager = None


def get_prompt_manager() -> PromptTemplateManager:
    """Get singleton instance of PromptTemplateManager."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptTemplateManager()
    return _prompt_manager


def handle_prompts_list(request_id: Optional[Any]) -> Dict[str, Any]:
    """Handle prompts/list request - return available prompts."""
    try:
        api_logger.debug(LogMessages.PROMPTS_LIST_REQUEST)

        # Check if database prompts are available
        if _should_use_database_prompts():
            manager = get_prompt_manager()
            prompt_infos = manager.get_user_accessible_prompts()

            prompts = []
            for prompt_info in prompt_infos:
                try:
                    prompt_doc = frappe.get_doc("Prompt Template", prompt_info["name"])
                    prompts.append(manager.get_prompt_for_mcp(prompt_doc))
                except Exception as e:
                    api_logger.warning(f"Error loading prompt {prompt_info['name']}: {e}")
        else:
            # Fallback to legacy hardcoded prompts
            prompts = _get_legacy_prompt_definitions()

        response = {"jsonrpc": "2.0", "result": {"prompts": prompts}}

        if request_id is not None:
            response["id"] = request_id

        api_logger.info(f"Prompts list request completed, returned {len(prompts)} prompts")
        return response

    except Exception as e:
        api_logger.error(f"Error in handle_prompts_list: {e}")
        return _error_response(ErrorCodes.INTERNAL_ERROR, ErrorMessages.INTERNAL_ERROR, str(e), request_id)


def handle_prompts_get(params: Dict[str, Any], request_id: Optional[Any]) -> Dict[str, Any]:
    """Handle prompts/get request - return specific prompt content."""
    try:
        api_logger.debug(LogMessages.PROMPTS_GET_REQUEST.format(params))

        prompt_name = params.get("name")
        arguments = params.get("arguments", {})

        if not prompt_name:
            return _error_response(
                ErrorCodes.INVALID_PARAMS, ErrorMessages.MISSING_PROMPT_NAME, None, request_id
            )

        manager = get_prompt_manager()

        # Try database first
        prompt_result = _get_prompt_from_database(prompt_name, arguments, manager)

        # Fallback to legacy if not found
        if prompt_result is None:
            prompt_result = _generate_legacy_prompt_content(prompt_name, arguments)

        if prompt_result is None:
            return _error_response(
                ErrorCodes.INVALID_PARAMS, ErrorMessages.UNKNOWN_PROMPT.format(prompt_name), None, request_id
            )

        response = {"jsonrpc": "2.0", "result": prompt_result}

        if request_id is not None:
            response["id"] = request_id

        api_logger.info(f"Prompts get request completed for: {prompt_name}")
        return response

    except frappe.ValidationError as e:
        api_logger.warning(f"Validation error in handle_prompts_get: {e}")
        return _error_response(ErrorCodes.INVALID_PARAMS, str(e), None, request_id)
    except frappe.PermissionError as e:
        api_logger.warning(f"Permission error in handle_prompts_get: {e}")
        return _error_response(ErrorCodes.AUTHENTICATION_REQUIRED, str(e), None, request_id)
    except Exception as e:
        api_logger.error(f"Error in handle_prompts_get: {e}")
        return _error_response(ErrorCodes.INTERNAL_ERROR, ErrorMessages.INTERNAL_ERROR, str(e), request_id)


def _get_prompt_from_database(
    prompt_id: str, arguments: Dict[str, Any], manager: PromptTemplateManager
) -> Optional[Dict[str, Any]]:
    """Get prompt from database and render it."""
    try:
        # Find prompt by prompt_id
        prompt_name = frappe.db.get_value(
            "Prompt Template", {"prompt_id": prompt_id, "status": ["in", ["Published", "Draft"]]}, "name"
        )

        if not prompt_name:
            return None

        prompt_doc = frappe.get_doc("Prompt Template", prompt_name)

        # Check permission
        if not _user_can_access_prompt(prompt_doc):
            frappe.throw(_("You don't have permission to access this prompt"), frappe.PermissionError)

        # Render the template
        rendered_content = manager.render_prompt(prompt_doc, arguments)

        # Increment usage counter
        manager.increment_usage(prompt_name)

        return {
            "description": prompt_doc.description,
            "messages": [{"role": "user", "content": {"type": "text", "text": rendered_content}}],
        }

    except frappe.DoesNotExistError:
        return None
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        api_logger.warning(f"Error fetching prompt from database: {e}")
        return None


def _user_can_access_prompt(prompt_doc) -> bool:
    """Check if current user can access the prompt."""
    user = frappe.session.user

    # Owner can always access
    if prompt_doc.owner_user == user:
        return True

    # System Manager can access all
    if "System Manager" in frappe.get_roles(user):
        return True

    # Check visibility
    if prompt_doc.visibility == "Public" and prompt_doc.status == "Published":
        return True

    if prompt_doc.visibility == "Shared" and prompt_doc.status == "Published":
        user_roles = set(frappe.get_roles(user))
        shared_roles = {r.role for r in prompt_doc.shared_with_roles}
        if user_roles & shared_roles:
            return True

    if prompt_doc.is_system and prompt_doc.status == "Published":
        return True

    return False


def _should_use_database_prompts() -> bool:
    """Check if we should use database prompts or fallback."""
    try:
        # Note: table_exists() expects DocType name, not "tab" prefixed table name
        if not frappe.db.table_exists("Prompt Template"):
            return False
        count = frappe.db.count("Prompt Template", {"status": "Published"})
        return count > 0
    except Exception:
        return False


# Legacy functions for backward compatibility
def _get_legacy_prompt_definitions() -> List[Dict[str, Any]]:
    """
    Fallback prompt definitions when no database prompts exist.

    Note: System prompt templates are now installed via 'bench migrate'.
    If you see this fallback being used, run 'bench migrate' to install
    the proper system prompt templates from fixtures.
    """
    api_logger.warning(
        "Using legacy fallback prompts. Run 'bench migrate' to install system prompt templates."
    )
    return [
        {
            "name": "setup_required",
            "description": "System prompt templates not installed. Run 'bench migrate' to install them.",
            "arguments": [],
        }
    ]


def _generate_legacy_prompt_content(prompt_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Generate fallback prompt content.

    Note: This should rarely be called as system prompts are installed via migration.
    """
    if prompt_name == "setup_required":
        return {
            "description": "System prompt templates not installed",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": "System prompt templates are not installed. Please run 'bench migrate' to install the system prompt templates, or create your own Prompt Template in Frappe.",
                    },
                }
            ],
        }

    return None


def _error_response(code: int, message: str, data: Any, request_id: Optional[Any]) -> Dict[str, Any]:
    """Build error response."""
    response = {"jsonrpc": "2.0", "error": {"code": code, "message": message}}
    if data:
        response["error"]["data"] = data
    if request_id is not None:
        response["id"] = request_id
    return response
