# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Workflow CRUD, execution, scheduling, templates, and tool resolution."""

import frappe
from frappe import _

from .auth import _ar_user_id

#: AR reports an unusable MCP connection as a per-server error code. Map it to
#: the action the SPA can actually offer instead of showing "No tools found".
TOOL_ERROR_ACTIONS = {
    "NO_REFRESH_TOKEN": "re_authorize",
    "REFRESH_TOKEN_EXPIRED": "re_authorize",
    "AUTH_FAILED": "re_authorize",
    "MISSING_CLIENT_CREDENTIALS": "complete_registration",
    "TIMEOUT": "check_mcp_server",
    "CONNECTION_ERROR": "check_mcp_server",
    "NO_MCP_SERVERS": "add_mcp_server",
    "NOT_REGISTERED": "register",
}


def _require_admin() -> None:
    """Guard every mutating passthrough. Mirrors workflow_triggers._require_admin."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can manage workflows."), frappe.PermissionError)


def _require_login() -> None:
    """Guard every read passthrough.

    Non-admins are read-only viewers, not strangers: `get_workflow` returns
    graph_json with every system prompt and global variable value, and
    `get_workflow_run` returns the per-node input/output text — the actual
    invoice, lead or HR document that flowed through the run. That stays behind
    a session.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def list_workflows(status: str | None = None, page: int = 0, page_size: int = 20):
    """List workflows for the current tenant."""
    _require_login()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"workflows": [], "total": 0, "page": 0, "page_size": 20}

        return client.list_workflows(
            status=status,
            page=int(page),
            page_size=int(page_size),
        )

    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error listing workflows: {e!s}")
        return {"workflows": [], "total": 0, "page": 0, "page_size": 20}


@frappe.whitelist(methods=["POST"])
def create_workflow(
    workflow_name: str | None = None,
    graph_json: str | None = None,
    description: str = "",
    default_model_id: str | None = None,
    default_user_id: str | None = None,
    error_strategy: str = "fail_fast",
    timeout_seconds: int = 600,
):
    """Create a new workflow. Admin only."""
    _require_admin()

    if not workflow_name:
        frappe.throw(_("workflow_name is required"), frappe.ValidationError)

    # Provide a default graph with input + output nodes if none given
    if not graph_json:
        import json

        graph_json = json.dumps(
            {
                "version": "1.0",
                "nodes": [
                    {
                        "id": "input_1",
                        "type": "input",
                        "label": "Input",
                        "position": {"x": 100, "y": 200},
                        "config": {},
                    },
                    {
                        "id": "output_1",
                        "type": "output",
                        "label": "Output",
                        "position": {"x": 500, "y": 200},
                        "config": {},
                    },
                ],
                "edges": [{"id": "e-input_1-output_1", "source": "input_1", "target": "output_1"}],
                "global_settings": {},
            }
        )

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.create_workflow(
            workflow_name=workflow_name,
            graph_json=graph_json,
            description=description,
            default_model_id=default_model_id,
            default_user_id=default_user_id,
            error_strategy=error_strategy,
            timeout_seconds=int(timeout_seconds),
        )

    except frappe.PermissionError:
        raise
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error creating workflow: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def get_workflow(name: str | None = None, workflow_name: str | None = None):
    """Get a workflow definition."""
    _require_login()

    if not name and not workflow_name:
        frappe.throw(_("Either name or workflow_name is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.get_workflow(name=name, workflow_name=workflow_name)

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error getting workflow: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def update_workflow(
    name: str | None = None,
    graph_json: str | None = None,
    workflow_name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    default_model_id: str | None = None,
    default_user_id: str | None = None,
    error_strategy: str | None = None,
    timeout_seconds: int | None = None,
    max_node_executions: int | None = None,
    max_retries: int | None = None,
):
    """Update a workflow. Admin only."""
    _require_admin()

    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        kwargs = {"name": name}
        if graph_json is not None:
            kwargs["graph_json"] = graph_json
        if workflow_name is not None:
            kwargs["workflow_name"] = workflow_name
        if description is not None:
            kwargs["description"] = description
        if status is not None:
            kwargs["status"] = status
        if default_model_id is not None:
            kwargs["default_model_id"] = default_model_id
        if default_user_id is not None:
            kwargs["default_user_id"] = default_user_id
        if error_strategy is not None:
            kwargs["error_strategy"] = error_strategy
        if timeout_seconds is not None:
            kwargs["timeout_seconds"] = int(timeout_seconds)
        if max_node_executions is not None:
            kwargs["max_node_executions"] = int(max_node_executions)
        if max_retries is not None:
            kwargs["max_retries"] = int(max_retries)

        return client.update_workflow(**kwargs)

    except frappe.PermissionError:
        raise
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error updating workflow: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def delete_workflow(name: str | None = None):
    """Delete (archive) a workflow. Admin only."""
    _require_admin()

    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.delete_workflow(name)

    except frappe.PermissionError:
        raise
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error deleting workflow: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def execute_workflow(name: str | None = None, input_data: str | None = None, user_id: str | None = None):
    """Execute a workflow. Admin only."""
    _require_admin()

    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.execute_workflow(
            name=name,
            input_data=input_data,
            user_id=_ar_user_id(user_id or frappe.session.user),
        )

    except frappe.PermissionError:
        raise
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error executing workflow: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def cancel_workflow_run(run_name: str | None = None):
    """Cancel a running workflow. Admin only."""
    _require_admin()

    if not run_name:
        frappe.throw(_("run_name is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.cancel_workflow_run(run_name)

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error cancelling workflow run: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def get_workflow_run(run_name: str | None = None):
    """Get workflow run details."""
    _require_login()

    if not run_name:
        frappe.throw(_("run_name is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.get_workflow_run(run_name)

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error getting workflow run: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def list_workflow_runs(
    workflow_name: str | None = None, status: str | None = None, page: int = 0, page_size: int = 20
):
    """List workflow execution runs."""
    _require_login()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"runs": [], "total": 0, "page": 0, "page_size": 20}

        return client.list_workflow_runs(
            workflow_name=workflow_name,
            status=status,
            page=int(page),
            page_size=int(page_size),
        )

    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error listing workflow runs: {e!s}")
        return {"runs": [], "total": 0, "page": 0, "page_size": 20}


@frappe.whitelist(methods=["GET"])
def get_workflow_audit_summary(workflow_id: str | None = None, window: str = "last_7_days"):
    """Get audit dashboard summary for a single workflow.

    Powers the per-workflow Audit tab in the SPA. Read-only.
    Returns the AR endpoint's payload verbatim.
    """
    _require_login()

    if not workflow_id:
        frappe.throw(_("workflow_id is required"), frappe.ValidationError)

    if window not in {"this_week", "last_7_days", "last_30_days"}:
        frappe.throw(
            _("Invalid window — use this_week, last_7_days, or last_30_days"), frappe.ValidationError
        )

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.get_workflow_audit_summary(workflow_id=workflow_id, window=window)

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error fetching audit summary: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def set_workflow_schedule(
    name: str | None = None,
    cron_expression: str | None = None,
    timezone: str = "UTC",
    enabled: bool = True,
    default_input: str | None = None,
):
    """Set workflow schedule. Admin only."""
    _require_admin()

    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)
    if not cron_expression:
        frappe.throw(_("cron_expression is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        # Convert string 'true'/'false' from frontend
        if isinstance(enabled, str):
            enabled = enabled.lower() in ("true", "1", "yes")

        return client.set_workflow_schedule(
            name=name,
            cron_expression=cron_expression,
            timezone=timezone,
            enabled=enabled,
            default_input=default_input,
        )

    except frappe.PermissionError:
        raise
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error setting schedule: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def validate_workflow_graph(graph_json: str | None = None):
    """Validate a workflow graph JSON."""
    _require_login()

    if not graph_json:
        frappe.throw(_("graph_json is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.validate_workflow_graph(graph_json)

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error validating graph: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def test_workflow_node(
    node_json: str | None = None,
    input_text: str = "Test input",
    default_model_id: str | None = None,
    default_user_id: str | None = None,
):
    """Test a single workflow node. Admin only."""
    _require_admin()

    if not node_json:
        frappe.throw(_("node_json is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.test_workflow_node(
            node_json=node_json,
            input_text=input_text,
            default_model_id=default_model_id,
            default_user_id=default_user_id,
        )

    except frappe.PermissionError:
        raise
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error testing node: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def run_workflow_node(
    name: str | None = None,
    node_id: str | None = None,
    input_text: str = "Test input",
    user_id: str | None = None,
):
    """Run a single node from a saved workflow. Admin only."""
    _require_admin()

    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)
    if not node_id:
        frappe.throw(_("node_id is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        # AR keys tenant users by email, and on this endpoint user_id OVERRIDES
        # the workflow's configured runtime user — so it is normalised when the
        # caller sends one, and left absent when they do not.
        return client.run_workflow_node(
            name=name,
            node_id=node_id,
            input_text=input_text,
            user_id=_ar_user_id(user_id) if user_id else None,
        )

    except frappe.PermissionError:
        raise
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error running node: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


# NOTE: list_workflow_templates / get_workflow_template / import_workflow_template
# were removed in the marketplace extraction (chunk 4). Their replacements live in
# api/marketplace.py: list_listings / get_listing / import_listing — accessed by
# the frontend via api.list_listings etc.


# export_workflow_template / upload_workflow_template / download_workflow_template /
# rate_workflow_template removed in chunk 5. Their replacements live in
# api/marketplace.py:
#   - publish_workflow (export + create listing in one call)
#   - upload_listing_from_json (file upload + create listing)
#   - download_listing_as_json
#   - rate_listing (already moved in chunk 4)


@frappe.whitelist(methods=["GET"])
def list_user_tools():
    """List all available tools from the current user's MCP servers.

    A discovery failure is reported as a failure. Returning
    ``{"success": True, "tools": []}`` for an expired OAuth token turned a
    one-click reconnect into "No tools found", which reads as "you have no
    tools" and leaves the user with nothing to do.
    """
    _require_login()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return _tool_failure(
                _("This site is not connected to FAC Cloud."),
                error_code="NOT_REGISTERED",
            )

        result = client.list_tools(user_id=_ar_user_id(frappe.session.user)) or {}

        # AR answers a tenant/user-level failure with {error, error_code,
        # action_required} and no `tools` key at all.
        if result.get("error"):
            return _tool_failure(
                result.get("error"),
                error_code=result.get("error_code"),
                action_required=result.get("action_required"),
            )

        tools = result.get("tools", [])
        errors = result.get("errors")

        # Per-server failures with nothing discovered: every server the user has
        # is unreachable, so this is a failure however AR framed it.
        if not tools and errors:
            first = errors[0] if isinstance(errors, list) and errors else {}
            code = first.get("error_code") if isinstance(first, dict) else None
            return _tool_failure(
                first.get("error") if isinstance(first, dict) else str(errors),
                error_code=code,
                errors=errors,
            )

        return {
            "success": True,
            "tools": tools,
            "servers_queried": result.get("servers_queried", []),
            "errors": errors,
        }

    except Exception as e:
        frappe.log_error(title="FACO Tools", message=f"Error listing user tools: {e!s}")
        return _tool_failure(str(e), error_code=getattr(e, "error_code", None) or "TOOL_DISCOVERY_FAILED")


def _tool_failure(
    message: str | None,
    error_code: str | None = None,
    action_required: str | None = None,
    errors: list | None = None,
) -> dict:
    """Uniform failure envelope for tool discovery, carrying a next step."""
    return {
        "success": False,
        "tools": [],
        "servers_queried": [],
        "errors": errors,
        "error": message or _("Could not read your MCP tools."),
        "error_code": error_code,
        "action_required": action_required or TOOL_ERROR_ACTIONS.get(error_code or "", "contact_support"),
    }


# get_workflow_creator_stats / report_workflow_template / list_pending_template_reviews /
# approve_workflow_template / reject_workflow_template were removed in chunk 4. Their
# replacements live in api/marketplace.py: get_creator_stats / report_listing /
# list_pending_reviews / approve_listing / reject_listing.


# check_workflow_template_updates / check_all_workflow_template_updates removed in
# chunk 5 — superseded by api/marketplace.py: check_workflow_update /
# check_all_workflow_updates.


@frappe.whitelist(methods=["POST"])
def resolve_workflow_tools(tool_directives: str | list | None = None):
    """Preview how tool directives resolve against the current user's MCP tools.

    A read: it reports only on the caller's own MCP inventory, so a read-only
    viewer sees honest resolution badges instead of an empty panel.
    """
    _require_login()

    try:
        import json as _json

        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        if isinstance(tool_directives, str):
            tool_directives = _json.loads(tool_directives)

        if not tool_directives:
            return {"resolved": [], "all_tools_available": True, "missing_tools": []}

        return client.resolve_workflow_tools(
            user_id=_ar_user_id(frappe.session.user),
            tool_directives=tool_directives,
        )

    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Workflows", message=f"Error resolving workflow tools: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))
