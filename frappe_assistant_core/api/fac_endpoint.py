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
MCP StreamableHTTP Endpoint

Custom MCP implementation that properly handles JSON serialization
and integrates seamlessly with Frappe's existing tool infrastructure.
"""

import frappe
from frappe import _

from frappe_assistant_core.mcp.server import MCPServer


def _get_mcp_server_name():
    """Get MCP server name from settings or use default."""
    try:
        settings = frappe.get_single("Assistant Core Settings")
        return settings.mcp_server_name or "frappe-assistant-core"
    except Exception:
        return "frappe-assistant-core"


# Create MCP server instance with name from settings
mcp = MCPServer(_get_mcp_server_name())


def _check_assistant_enabled(user: str) -> bool:
    """Check if assistant is enabled for user."""
    try:
        assistant_enabled = frappe.db.get_value("User", user, "assistant_enabled")
        if assistant_enabled is None:
            return False
        return bool(int(assistant_enabled)) if assistant_enabled else False
    except Exception:
        return False


def _build_tool_registry(profile_name=None):
    """
    Build a per-request tool registry for the current user.

    Returns a fresh ``OrderedDict`` (name -> tool_dict) built on the call stack
    rather than mutating the module-level ``mcp`` instance. This keeps
    concurrent MCP requests isolated from each other: one in-flight request can
    no longer clear or overwrite the tool set another request is validating or
    executing against (issue #197). The set is also genuinely per-user, since
    ``get_available_tools`` filters by the requesting user's permissions.

    Each tool dict carries MCP annotation hints derived from its FAC tool
    category, so MCP clients (e.g. Claude Desktop) can group tools into
    Read-only vs Write/delete instead of an undifferentiated "Other tools"
    bucket. The category is the same one shown/overridable on the FAC admin
    page (FAC Tool Configuration.tool_category) — single source of truth.

    Returns:
        OrderedDict mapping tool name to its MCP tool dict.
    """
    from collections import OrderedDict

    registry_dict = OrderedDict()
    try:
        from frappe_assistant_core.core.tool_registry import get_tool_registry
        from frappe_assistant_core.mcp.tool_adapter import build_tool_dict
        from frappe_assistant_core.utils.tool_category_detector import category_to_annotations

        # Get available instances in one pass. The previous metadata -> name ->
        # get_tool loop rediscovered every external hook tool for every item.
        registry = get_tool_registry()
        selected_tools = None
        if profile_name:
            profile = registry.get_tool_profile(profile_name)
            if not profile:
                frappe.logger().warning(
                    f"Unknown MCP tool profile '{profile_name}'; exposing no tools for this request"
                )
                return registry_dict
            selected_tools = profile.get("tools") or []

        if selected_tools is None:
            available_tools = registry.get_available_tool_instances(user=frappe.session.user)
        else:
            available_tools = registry.get_available_tool_instances(
                user=frappe.session.user,
                tool_names=selected_tools,
            )

        # Resolve each tool's category once (honors admin overrides stored on
        # FAC Tool Configuration; falls back to auto-detection).
        categories = _resolve_tool_categories(
            list(available_tools), registry, tool_instances=available_tools
        )

        for tool_name, tool_instance in available_tools.items():
            tool_dict = build_tool_dict(tool_instance)
            annotations = category_to_annotations(categories.get(tool_name, "read_write"))
            if annotations:
                # Merge with any annotations the tool already declared.
                tool_dict["annotations"] = {**(tool_dict.get("annotations") or {}), **annotations}
            registry_dict[tool_name] = tool_dict

        profile_label = profile_name or "all"
        frappe.logger().info(
            f"Built {len(registry_dict)} enabled tools for user {frappe.session.user} "
            f"with profile {profile_label}"
        )

    except Exception as e:
        frappe.log_error(title="Tool Import Error", message=f"Error importing tools: {str(e)}")

    return registry_dict


def _resolve_tool_categories(tool_names: list, registry, tool_instances=None) -> dict:
    """
    Resolve the FAC tool category for each tool name.

    Resolution order per tool:
      1. Stored ``FAC Tool Configuration.tool_category`` (honors admin override).
      2. Auto-detected category via ``detect_tool_category`` (no config row yet).
      3. ``"read_write"`` fallback (maps to no annotation hints — safe default).

    Stored categories are batch-fetched in one query to avoid a DB read per tool.

    Args:
        tool_names: Tool names to resolve.
        registry: The tool registry (used to fetch instances for auto-detection).

    Returns:
        Dict mapping tool name -> category string.
    """
    from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

    categories = {}

    # 1. Batch-fetch stored categories.
    try:
        rows = frappe.get_all(
            "FAC Tool Configuration",
            filters={"tool_name": ["in", tool_names]} if tool_names else {},
            fields=["tool_name", "tool_category"],
            ignore_permissions=True,
        )
        for row in rows:
            if row.get("tool_category"):
                categories[row["tool_name"]] = row["tool_category"]
    except Exception as e:
        frappe.logger().warning(f"Could not batch-fetch tool categories: {e}")

    # 2 & 3. Fill gaps via auto-detection, defaulting to read_write.
    for tool_name in tool_names:
        if tool_name in categories:
            continue
        try:
            tool_instance = (tool_instances or {}).get(tool_name) or registry.get_tool(tool_name)
            categories[tool_name] = detect_tool_category(tool_instance) if tool_instance else "read_write"
        except Exception:
            categories[tool_name] = "read_write"

    return categories


def _requested_tool_profile(registry):
    """Resolve an optional profile from request header, site config or hooks.

    A profile only narrows the already permission-filtered registry. Unknown
    names fail closed in `_build_tool_registry` instead of exposing all tools.
    """
    header_profile = ""
    try:
        header_profile = frappe.request.headers.get("X-Assistant-Tool-Profile") or ""
    except Exception:
        pass

    configured_profile = ""
    try:
        configured_profile = frappe.conf.get("fac_mcp_tool_profile") or ""
    except Exception:
        pass

    return str(
        header_profile or configured_profile or registry.get_default_tool_profile_name() or ""
    ).strip() or None


def _authenticate_mcp_request():
    """
    Authenticate MCP requests using OAuth Bearer tokens or API key/secret.

    Supports two authentication methods:
    1. OAuth 2.0 Bearer tokens: "Authorization: Bearer <token>"
    2. API Key/Secret: "Authorization: token <api_key>:<api_secret>"

    Returns:
        str: Authenticated username
        None: Authentication failed (returns 401 response directly)
    """
    from werkzeug.wrappers import Response

    from frappe_assistant_core.api.oauth_discovery import get_public_base_url

    auth_header = frappe.request.headers.get("Authorization", "")

    # Try OAuth Bearer token authentication first
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        try:
            # Validate token using Frappe's OAuth Bearer Token doctype
            bearer_token = frappe.get_doc("OAuth Bearer Token", {"access_token": token})

            # Check if token is active
            if bearer_token.status != "Active":
                frappe.logger().error(f"Token is not active. Status: {bearer_token.status}")
                raise frappe.AuthenticationError("Token is not active")

            # Check if token has expired
            # Use Frappe's now_datetime() for timezone-aware comparison
            from frappe.utils import now_datetime

            current_time = now_datetime()
            if bearer_token.expiration_time < current_time:
                frappe.logger().error(
                    f"Token has expired. Expiration: {bearer_token.expiration_time}, Now: {current_time}"
                )
                raise frappe.AuthenticationError("Token has expired")

            # Set the user session
            # nosemgrep: frappe-setuser — user resolved from validated, non-expired OAuth bearer token
            frappe.set_user(bearer_token.user)
            frappe.logger().info(f"OAuth token validated successfully for user: {bearer_token.user}")
            return bearer_token.user

        except frappe.DoesNotExistError:
            frappe.logger().error("OAuth Bearer Token not found")
            # Token not found - return 401
            frappe_url = get_public_base_url()
            metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

            response = Response()
            response.status_code = 401
            response.headers["WWW-Authenticate"] = (
                f'Bearer realm="Frappe Assistant Core", '
                f'error="invalid_token", '
                f'error_description="Token not found", '
                f'resource_metadata="{metadata_url}"'
            )
            response.headers["Content-Type"] = "application/json"
            response.data = frappe.as_json({"error": "invalid_token", "message": "Token not found"})
            return response

        except Exception as e:
            # Log the error for debugging
            frappe.logger().error(f"OAuth token validation error: {type(e).__name__}: {str(e)}")
            frappe.log_error(title="OAuth Token Validation Error", message=f"{type(e).__name__}: {str(e)}")

            # Return 401 for invalid/expired tokens
            frappe_url = get_public_base_url()
            metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

            response = Response()
            response.status_code = 401
            response.headers["WWW-Authenticate"] = (
                f'Bearer realm="Frappe Assistant Core", '
                f'error="invalid_token", '
                f'error_description="{str(e)}", '
                f'resource_metadata="{metadata_url}"'
            )
            response.headers["Content-Type"] = "application/json"
            response.data = frappe.as_json({"error": "invalid_token", "message": str(e)})
            return response

    # Try API Key/Secret authentication (for STDIO clients)
    elif auth_header.startswith("token "):
        try:
            # Extract token from "token api_key:api_secret" format
            token_part = auth_header[6:]  # Remove "token " prefix
            if ":" in token_part:
                api_key, api_secret = token_part.split(":", 1)
                frappe.logger().debug("Attempting API key authentication")

                # Validate using database lookup
                user_data = frappe.db.get_value(
                    "User", {"api_key": api_key, "enabled": 1}, ["name", "api_secret"]
                )

                if user_data:
                    user, _ = user_data
                    # Compare the provided secret with stored secret
                    from frappe.utils.password import get_decrypted_password

                    decrypted_secret = get_decrypted_password("User", user, "api_secret")

                    if api_secret == decrypted_secret:
                        # Set user context for this request
                        # nosemgrep: frappe-setuser — user authenticated via API key:secret comparison above
                        frappe.set_user(str(user))
                        frappe.logger().info(f"API key authentication successful for user: {user}")
                        return str(user)
                    else:
                        frappe.logger().warning("API secret mismatch")
                        raise frappe.AuthenticationError("Invalid API credentials")
                else:
                    frappe.logger().warning("API key not found")
                    raise frappe.AuthenticationError("Invalid API credentials")
            else:
                frappe.logger().warning("Invalid API key format - missing colon separator")
                raise frappe.AuthenticationError("Invalid API key format")

        except frappe.AuthenticationError as e:
            # Return 401 for invalid API credentials
            frappe_url = get_public_base_url()
            metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

            response = Response()
            response.status_code = 401
            response.headers["WWW-Authenticate"] = (
                f'Bearer realm="Frappe Assistant Core", ' f'resource_metadata="{metadata_url}"'
            )
            response.headers["Content-Type"] = "application/json"
            response.data = frappe.as_json({"error": "invalid_credentials", "message": str(e)})
            return response

        except Exception as e:
            frappe.logger().error(f"API key authentication error: {type(e).__name__}: {str(e)}")
            frappe.log_error(title="API Key Authentication Error", message=f"{type(e).__name__}: {str(e)}")

            # Return 401 for other errors
            frappe_url = get_public_base_url()
            metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

            response = Response()
            response.status_code = 401
            response.headers["WWW-Authenticate"] = (
                f'Bearer realm="Frappe Assistant Core", ' f'resource_metadata="{metadata_url}"'
            )
            response.headers["Content-Type"] = "application/json"
            response.data = frappe.as_json({"error": "authentication_error", "message": str(e)})
            return response

    # No valid authentication method found
    frappe.logger().warning("No valid authentication method found in request")
    frappe_url = get_public_base_url()
    metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

    response = Response()
    response.status_code = 401
    response.headers["WWW-Authenticate"] = (
        f'Bearer realm="Frappe Assistant Core", ' f'resource_metadata="{metadata_url}"'
    )
    response.headers["Content-Type"] = "application/json"
    response.data = frappe.as_json({"error": "unauthorized", "message": "Authentication required"})
    return response


@mcp.register(allow_guest=True, xss_safe=True, methods=["GET", "POST", "HEAD"])
def handle_mcp():
    """
    MCP StreamableHTTP endpoint.

    This is the main entry point for all MCP requests. It uses our custom
    MCP server implementation which properly handles JSON serialization.

    Endpoint: /api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp
    Protocol: MCP 2025-06-18 StreamableHTTP

    Supports two authentication methods:
    1. OAuth 2.0 Bearer tokens: "Authorization: Bearer <token>" (for web clients)
    2. API Key/Secret: "Authorization: token <api_key>:<api_secret>" (for STDIO clients)
    """
    from werkzeug.wrappers import Response

    from frappe_assistant_core.api.oauth_discovery import get_public_base_url

    # Handle HEAD request for connectivity check (Claude Web uses this)
    if frappe.request.method == "HEAD":
        # Return 401 with WWW-Authenticate header to indicate auth is required
        frappe_url = get_public_base_url()
        metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

        response = Response()
        response.status_code = 401
        response.headers["WWW-Authenticate"] = (
            f'Bearer realm="Frappe Assistant Core", ' f'resource_metadata="{metadata_url}"'
        )
        return response

    # Authenticate the request (supports both OAuth and API key)
    auth_result = _authenticate_mcp_request()

    # If authentication failed, auth_result is a Response object with 401
    if isinstance(auth_result, Response):
        return auth_result

    # Authentication successful - auth_result is the username
    authenticated_user = auth_result

    # Check if user has assistant access enabled
    if not _check_assistant_enabled(authenticated_user):
        frappe.throw(
            _("Assistant access is disabled for user {0}").format(authenticated_user), frappe.PermissionError
        )

    # Only tool discovery and execution need the registry. Initialisation,
    # ping, prompt and resource calls avoid importing and permission-checking
    # the complete tool portfolio.
    try:
        payload = frappe.request.get_json(silent=True) or {}
    except Exception:
        payload = {}
    if payload.get("method") not in {"tools/list", "tools/call"}:
        return None

    # Build a per-request tool registry (isolated from concurrent requests) and
    # hand it back to the MCP server wrapper, which passes it into handle().
    from frappe_assistant_core.core.tool_registry import get_tool_registry

    profile_name = _requested_tool_profile(get_tool_registry())
    return _build_tool_registry(profile_name=profile_name)
