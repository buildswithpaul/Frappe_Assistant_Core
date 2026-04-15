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

import json
from typing import Any, Dict, Optional

import frappe
from frappe.utils import now

# Allowed values for Assistant Audit Log `status` — must match the DocType Select.
AUDIT_STATUS_SUCCESS = "Success"
AUDIT_STATUS_ERROR = "Error"
AUDIT_STATUS_TIMEOUT = "Timeout"
AUDIT_STATUS_PERMISSION_DENIED = "Permission Denied"
_VALID_STATUSES = {
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_TIMEOUT,
    AUDIT_STATUS_PERMISSION_DENIED,
}

# Output data is stored as JSON text in a Code field; cap to keep audit rows
# from bloating when a tool returns a large payload.
_OUTPUT_DATA_MAX_BYTES = 50_000

# Keys that should never appear in audit logs in cleartext. Matched
# case-insensitively on substring, same heuristic as BaseTool._sanitize_arguments.
_SENSITIVE_KEY_SUBSTRINGS = ("password", "api_key", "secret", "token", "auth")


def _sanitize_arguments(arguments: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Defensive sanitization at the audit sink — callers are expected to
    sanitize too, but this ensures secrets never land in the table even
    when a non-BaseTool call site forgets."""
    if not isinstance(arguments, dict):
        return arguments
    sanitized: Dict[str, Any] = {}
    for key, value in arguments.items():
        if any(sub in key.lower() for sub in _SENSITIVE_KEY_SUBSTRINGS):
            sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value
    return sanitized


def log_document_change(doc, method):
    """Log document changes for audit trail"""
    if should_log_document(doc.doctype):
        try:
            frappe.get_doc(
                {
                    "doctype": "Assistant Audit Log",
                    "action": "update_document",
                    "user": frappe.session.user,
                    "status": "Success",
                    "timestamp": now(),
                    "target_doctype": doc.doctype,
                    "target_name": doc.name,
                    "ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None,
                }
            ).insert(ignore_permissions=True)
        except Exception:
            pass  # Ignore audit logging errors


def log_document_submit(doc, method):
    """Log document submissions"""
    if should_log_document(doc.doctype):
        try:
            frappe.get_doc(
                {
                    "doctype": "Assistant Audit Log",
                    "action": "update_document",
                    "user": frappe.session.user,
                    "status": "Success",
                    "timestamp": now(),
                    "target_doctype": doc.doctype,
                    "target_name": doc.name,
                    "ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None,
                }
            ).insert(ignore_permissions=True)
        except Exception:
            pass


def log_document_cancel(doc, method):
    """Log document cancellations"""
    if should_log_document(doc.doctype):
        try:
            frappe.get_doc(
                {
                    "doctype": "Assistant Audit Log",
                    "action": "update_document",
                    "user": frappe.session.user,
                    "status": "Success",
                    "timestamp": now(),
                    "target_doctype": doc.doctype,
                    "target_name": doc.name,
                    "ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None,
                }
            ).insert(ignore_permissions=True)
        except Exception:
            pass


def should_log_document(doctype):
    """Check if document type should be logged"""
    # Don't log assistant internal documents to avoid recursion
    if doctype.startswith("assistant "):
        return False

    # try:
    #     # Get audit settings using the correct method
    #     audit_doctypes = frappe.db.get_single_value("assistant Server Settings", "audit_doctypes") or ""

    #     if audit_doctypes:
    #         return doctype in audit_doctypes.split(",")
    # except Exception:
    #     # If assistant Server Settings doesn't exist or has issues, don't log
    #     pass

    # By default, don't audit everything to avoid performance impact
    return False


def log_tool_execution(
    tool_name: str,
    user: str,
    arguments: Optional[Dict[str, Any]],
    status: str,
    execution_time: float,
    source_app: Optional[str] = None,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
    traceback_str: Optional[str] = None,
    output_data: Optional[Any] = None,
):
    """
    Log tool execution for comprehensive audit trail.

    Args:
        tool_name: Name of the executed tool
        user: User who executed the tool
        arguments: Tool arguments (sensitive data should be pre-sanitized; the
            sink re-sanitizes defensively)
        status: One of "Success", "Error", "Timeout", "Permission Denied".
            Unknown values are coerced to "Error" with a warning.
        execution_time: Time taken in seconds
        source_app: App that provides the tool
        error_message: Error message if execution failed
        error_type: Exception class name or semantic category (e.g.
            "PermissionError", "ValidationError", "ToolReportedError")
        traceback_str: Full Python traceback (exception paths only)
        output_data: Tool output data for audit trail
    """
    try:
        if status not in _VALID_STATUSES:
            frappe.logger("audit_trail").warning(
                f"log_tool_execution: invalid status {status!r} for tool {tool_name}; coercing to 'Error'"
            )
            status = AUDIT_STATUS_ERROR

        sanitized_arguments = _sanitize_arguments(arguments)

        # Extract target information from arguments (after sanitization so we
        # can't leak secrets via target fields either)
        target_doctype = None
        target_name = None
        if isinstance(sanitized_arguments, dict):
            target_doctype = sanitized_arguments.get("doctype")
            target_name = sanitized_arguments.get("name")

        # Serialize output for storage, clamp oversized payloads
        output_data_str, output_truncated = _serialize_for_audit(output_data)

        input_data_str = None
        if sanitized_arguments is not None:
            try:
                input_data_str = json.dumps(sanitized_arguments, default=str)
            except (TypeError, ValueError):
                input_data_str = str(sanitized_arguments)[:_OUTPUT_DATA_MAX_BYTES]

        audit_doc = frappe.get_doc(
            {
                "doctype": "Assistant Audit Log",
                "action": tool_name,
                "tool_name": tool_name,
                "user": user,
                "status": status,
                "timestamp": now(),
                "execution_time": execution_time,
                "target_doctype": target_doctype,
                "target_name": target_name,
                "client_id": getattr(frappe.local, "assistant_client_id", None),
                "session_id": getattr(frappe.local, "assistant_session_id", None),
                "source_app": source_app,
                "ip_address": getattr(frappe.local, "request_ip", None),
                "input_data": input_data_str,
                "output_data": output_data_str,
                "output_truncated": 1 if output_truncated else 0,
                "error_message": error_message,
                "error_type": error_type,
                "traceback": traceback_str,
            }
        )

        audit_doc.insert(ignore_permissions=True)

    except Exception as e:
        # Don't fail tool execution due to audit logging issues
        frappe.logger("audit_trail").warning(f"Failed to log tool execution: {str(e)}")


def _serialize_for_audit(output_data: Any) -> tuple:
    """Serialize tool output for the audit row. Returns (json_str_or_none, truncated_bool)."""
    if output_data is None:
        return None, False
    try:
        serialized = json.dumps(output_data, default=str)
    except (TypeError, ValueError):
        serialized = str(output_data)
    if len(serialized) > _OUTPUT_DATA_MAX_BYTES:
        return serialized[:_OUTPUT_DATA_MAX_BYTES], True
    return serialized, False


def log_tool_discovery(app_name: str, tools_found: int, errors: int, discovery_time: float):
    """
    Log tool discovery events.

    Args:
        app_name: Name of the app being scanned
        tools_found: Number of tools discovered
        errors: Number of discovery errors
        discovery_time: Time taken for discovery
    """
    try:
        payload = {
            "app_name": app_name,
            "tools_found": tools_found,
            "errors": errors,
            "discovery_time": discovery_time,
        }
        output_str, truncated = _serialize_for_audit(payload)
        audit_doc = frappe.get_doc(
            {
                "doctype": "Assistant Audit Log",
                "action": "discover_tools",
                "user": frappe.session.user or "System",
                "status": AUDIT_STATUS_SUCCESS if errors == 0 else AUDIT_STATUS_ERROR,
                "timestamp": now(),
                "execution_time": discovery_time,
                "target_doctype": "Tool Discovery",
                "target_name": app_name,
                "source_app": app_name,
                "output_data": output_str,
                "output_truncated": 1 if truncated else 0,
            }
        )

        audit_doc.insert(ignore_permissions=True)

    except Exception as e:
        frappe.logger("audit_trail").warning(f"Failed to log tool discovery: {str(e)}")


def log_security_event(event_type: str, user: str, details: Dict[str, Any], severity: str = "Medium"):
    """
    Log security-related events.

    Args:
        event_type: Type of security event (e.g., 'permission_denied', 'suspicious_activity')
        user: User associated with the event
        details: Event details dictionary
        severity: Event severity (Low, Medium, High, Critical)
    """
    try:
        payload = {"event_type": event_type, "severity": severity, **details}
        output_str, truncated = _serialize_for_audit(payload)
        audit_doc = frappe.get_doc(
            {
                "doctype": "Assistant Audit Log",
                "action": f"security_{event_type}",
                "user": user,
                "status": AUDIT_STATUS_PERMISSION_DENIED
                if event_type == "permission_denied"
                else AUDIT_STATUS_ERROR,
                "error_type": f"Security:{severity}",
                "timestamp": now(),
                "target_doctype": "Security Event",
                "target_name": event_type,
                "client_id": getattr(frappe.local, "assistant_client_id", None),
                "session_id": getattr(frappe.local, "assistant_session_id", None),
                "ip_address": getattr(frappe.local, "request_ip", None),
                "output_data": output_str,
                "output_truncated": 1 if truncated else 0,
            }
        )

        audit_doc.insert(ignore_permissions=True)

        # For critical events, also log to error log
        if severity == "Critical":
            frappe.log_error(
                title=f"Critical Security Event: {event_type}",
                message=f"User: {user}, Details: {json.dumps(details, default=str)}",
            )

    except Exception as e:
        frappe.logger("audit_trail").warning(f"Failed to log security event: {str(e)}")


def get_audit_summary(user: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
    """
    Get audit trail summary for monitoring.

    Args:
        user: Filter by specific user (None for all users)
        days: Number of days to include

    Returns:
        Audit summary statistics
    """
    try:
        from frappe.utils import add_days

        # Calculate date range
        from_date = add_days(now(), -days)

        # Build filters
        filters = {"timestamp": [">=", from_date]}
        if user:
            filters["user"] = user

        # Get audit logs
        logs = frappe.get_all(
            "Assistant Audit Log",
            filters=filters,
            fields=["action", "status", "user", "timestamp"],
            order_by="timestamp desc",
            limit=1000,
        )

        # Calculate statistics
        summary = {
            "total_events": len(logs),
            "date_range": {"from": from_date, "to": now()},
            "user_filter": user,
            "actions": {},
            "status_breakdown": {},
            "recent_events": logs[:10],  # Last 10 events
        }

        # Action breakdown
        for log in logs:
            action = log.get("action", "unknown")
            summary["actions"][action] = summary["actions"].get(action, 0) + 1

        # Status breakdown
        for log in logs:
            status = log.get("status", "unknown")
            summary["status_breakdown"][status] = summary["status_breakdown"].get(status, 0) + 1

        return summary

    except Exception as e:
        frappe.logger("audit_trail").error(f"Failed to get audit summary: {str(e)}")
        return {"total_events": 0, "error": str(e)}
