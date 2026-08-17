"""
Enterprise Intelligence Platform Error Handler

Centralized error handling and recovery system.
"""

from typing import Any, Dict, Optional, Callable
from datetime import datetime
import traceback
import frappe
from frappe import _


class ErrorHandler:
    """
    Centralized error handling for EIP.
    
    Handles:
    - Error logging and tracking
    - Error recovery strategies
    - Error notifications
    - Retry logic
    """

    error_registry = {}
    error_count = 0
    last_errors = []

    @classmethod
    def handle_error(
        cls,
        error: Exception,
        context: str = "Unknown",
        severity: str = "error",
        recoverable: bool = False,
        recovery_strategy: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Handle an error with full context and recovery options."""
        cls.error_count += 1
        error_id = f"err_{cls.error_count}"

        error_info = {
            "error_id": error_id,
            "type": type(error).__name__,
            "message": str(error),
            "context": context,
            "severity": severity,
            "recoverable": recoverable,
            "timestamp": datetime.now().isoformat(),
            "user": frappe.session.user if hasattr(frappe, "session") else "system",
            "traceback": traceback.format_exc(),
        }

        cls.error_registry[error_id] = error_info
        cls.last_errors.append(error_info)
        if len(cls.last_errors) > 100:
            cls.last_errors.pop(0)

        cls._log_error(error_info)

        recovery_result = None
        if recovery_strategy and recoverable:
            try:
                recovery_result = recovery_strategy()
                error_info["recovered"] = True
                error_info["recovery_result"] = recovery_result
            except Exception as recovery_error:
                frappe.logger().error(f"Recovery failed: {recovery_error}")
                error_info["recovered"] = False

        response = {
            "success": False,
            "error_id": error_id,
            "error": error_info["message"],
            "error_type": error_info["type"],
            "recoverable": recoverable,
            "recovered": error_info.get("recovered", False),
        }

        if severity == "critical":
            cls._send_critical_alert(error_info)

        return response

    @classmethod
    def _log_error(cls, error_info: Dict[str, Any]) -> None:
        """Log error to Frappe error log."""
        frappe.log_error(
            title=_(f"EIP Error: {error_info['context']}"),
            message=(
                f"Error ID: {error_info['error_id']}\n"
                f"Type: {error_info['type']}\n"
                f"Message: {error_info['message']}\n"
                f"Severity: {error_info['severity']}\n"
                f"Traceback:\n{error_info['traceback']}"
            ),
        )

    @classmethod
    def _send_critical_alert(cls, error_info: Dict[str, Any]) -> None:
        """Send alert for critical errors."""
        try:
            admins = frappe.db.get_list(
                "User",
                filters={"user_type": "System User", "enabled": 1},
                fields=["email"],
            )

            if admins:
                subject = f"🔴 Critical EIP Error: {error_info['context']}"
                message = (
                    f"<h3>Critical Error Alert</h3>"
                    f"<p><strong>Error ID:</strong> {error_info['error_id']}</p>"
                    f"<p><strong>Type:</strong> {error_info['type']}</p>"
                    f"<p><strong>Message:</strong> {error_info['message']}</p>"
                    f"<p><strong>Time:</strong> {error_info['timestamp']}</p>"
                )

                for admin in admins:
                    try:
                        frappe.sendmail(
                            recipients=[admin["email"]],
                            subject=subject,
                            message=message,
                        )
                    except Exception as e:
                        frappe.logger().warning(f"Failed to send alert: {e}")
        except Exception as e:
            frappe.logger().warning(f"Failed to send critical alert: {e}")

    @classmethod
    def get_error_info(cls, error_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific error."""
        return cls.error_registry.get(error_id)

    @classmethod
    def get_recent_errors(cls, limit: int = 10) -> list:
        """Get recent errors."""
        return cls.last_errors[-limit:]

    @classmethod
    def get_error_stats(cls) -> Dict[str, Any]:
        """Get error statistics."""
        error_types = {}
        for error_info in cls.last_errors:
            error_type = error_info["type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "total_errors": cls.error_count,
            "error_types": error_types,
            "recent_errors_count": len(cls.last_errors),
        }

    @classmethod
    def clear_registry(cls) -> None:
        """Clear error registry."""
        cls.error_registry.clear()
        cls.last_errors.clear()
        cls.error_count = 0
