# -*- coding: utf-8 -*-
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
from frappe import _
from frappe.utils import today

# Constants
DEFAULT_PORT = 8000  # Frappe's default port fallback

def get_frappe_port():
    """Get Frappe's actual running port from configuration"""
    import os
    import json
    
    try:
        # Method 1: Try to get from Frappe configuration
        if hasattr(frappe, 'conf') and hasattr(frappe.conf, 'webserver_port'):
            return int(frappe.conf.webserver_port)
        
        # Method 2: Try to find common_site_config.json by traversing up
        current_dir = os.getcwd()
        search_dir = current_dir
        
        # Walk up the directory tree to find the bench root (contains sites folder)
        for _ in range(10):  # Limit iterations
            sites_path = os.path.join(search_dir, 'sites')
            config_file = os.path.join(sites_path, 'common_site_config.json')
            
            if os.path.exists(sites_path) and os.path.isdir(sites_path):
                if os.path.exists(config_file):
                    with open(config_file, 'r') as f:
                        common_config = json.load(f)
                        if 'webserver_port' in common_config:
                            return int(common_config['webserver_port'])
                break  # Found sites directory, stop searching
            
            parent_dir = os.path.dirname(search_dir)
            if parent_dir == search_dir:  # Reached root
                break
            search_dir = parent_dir
        
        # Method 3: Try to get from environment
        if 'FRAPPE_SITE_PORT' in os.environ:
            return int(os.environ['FRAPPE_SITE_PORT'])
        
        # Fallback to default
        return DEFAULT_PORT
        
    except Exception:
        return DEFAULT_PORT

@frappe.whitelist()
def get_assistant_dashboard_data():
    """Get comprehensive assistant dashboard data with enhanced caching"""
    from frappe_assistant_core.utils.cache import (
        get_cached_server_settings,
        get_cached_dashboard_stats,
        get_cached_most_used_tools,
        get_cached_category_performance
    )
    
    try:
        # Get cached server settings
        settings = get_cached_server_settings()
        
        # Get cached dashboard statistics
        dashboard_stats = get_cached_dashboard_stats()
        
        # Get cached most used tools
        most_used_tools = get_cached_most_used_tools()
        
        # Get cached category performance
        category_performance = get_cached_category_performance()
        
        # Get recent errors (not cached - real-time data)
        recent_errors = frappe.get_all(
            "Assistant Audit Log",
            filters={
                "status": ["in", ["Error", "Timeout", "Permission Denied"]],
                "creation": [">=", today()]
            },
            fields=["tool_name", "user", "error_message", "timestamp"],
            order_by="timestamp desc",
            limit=5
        )
        
        return {
            "server_info": {
                "enabled": settings.get("server_enabled"),
                "port": get_frappe_port(),
                "enforce_artifact_streaming": settings.get("enforce_artifact_streaming", True),
                "response_limit_prevention": settings.get("response_limit_prevention", True)
            },
            "connections": dashboard_stats.get("connections", {}),
            "tools": {
                **dashboard_stats.get("tools", {}),
                "most_used": most_used_tools
            },
            "performance": {
                **dashboard_stats.get("performance", {}),
                "category_performance": category_performance
            },
            "issues": {
                "recent_errors": recent_errors
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Dashboard data error: {str(e)}", "Assistant Dashboard")
        return {"error": str(e)}

@frappe.whitelist()
def get_system_health_check():
    """Perform comprehensive system health check"""
    health_status = {
        "overall_status": "healthy",
        "checks": [],
        "warnings": [],
        "errors": []
    }
    
    try:
        # Check 1: DocTypes exist and are properly configured
        required_doctypes = [
            "assistant Server Settings",
            "assistant Tool Registry", 
            "assistant Connection Log",
            "assistant Audit Log"
        ]
        
        for doctype in required_doctypes:
            if not frappe.db.table_exists(f"tab{doctype}"):
                health_status["errors"].append(f"DocType '{doctype}' table does not exist")
                health_status["overall_status"] = "critical"
            else:
                health_status["checks"].append(f"DocType '{doctype}' exists")
        
        # Check 2: Server settings are configured
        try:
            settings = frappe.get_single("assistant Server Settings")
            if not settings:
                health_status["warnings"].append("assistant Server Settings not found")
            else:
                health_status["checks"].append("assistant Server Settings configured")
                
                # Port configuration no longer needed (uses Frappe's default port)
                health_status["checks"].append("Using Frappe's default port (8000)")
                    
        except Exception as e:
            health_status["errors"].append(f"Cannot access assistant Server Settings: {str(e)}")
            health_status["overall_status"] = "critical"
        
        # Check 3: Tools are registered
        tool_count = frappe.db.count("assistant Tool Registry")
        if tool_count == 0:
            health_status["warnings"].append("No tools registered in assistant Tool Registry")
        else:
            enabled_tools = frappe.db.count("assistant Tool Registry", filters={"enabled": 1})
            health_status["checks"].append(f"{enabled_tools} of {tool_count} tools enabled")
        
        # Check 4: Recent connection issues
        recent_errors = frappe.db.count("assistant Connection Log", 
                                       filters={
                                           "status": "Error",
                                           "creation": [">=", today()]
                                       })
        
        if recent_errors > 10:
            health_status["warnings"].append(f"High number of connection errors today: {recent_errors}")
        elif recent_errors > 0:
            health_status["checks"].append(f"Minor connection issues: {recent_errors} errors today")
        else:
            health_status["checks"].append("No connection errors today")
        
        # Check 5: Tool execution health
        failed_executions = frappe.db.count("assistant Audit Log",
                                           filters={
                                               "status": ["in", ["Error", "Timeout"]],
                                               "creation": [">=", today()]
                                           })
        
        total_executions = frappe.db.count("assistant Audit Log",
                                          filters={"creation": [">=", today()]})
        
        if total_executions > 0:
            failure_rate = (failed_executions / total_executions) * 100
            if failure_rate > 20:
                health_status["warnings"].append(f"High tool failure rate: {failure_rate:.1f}%")
                health_status["overall_status"] = "warning" if health_status["overall_status"] == "healthy" else health_status["overall_status"]
            else:
                health_status["checks"].append(f"Tool execution health good: {failure_rate:.1f}% failure rate")
        
        # Set overall status based on findings
        if health_status["errors"]:
            health_status["overall_status"] = "critical"
        elif health_status["warnings"] and health_status["overall_status"] == "healthy":
            health_status["overall_status"] = "warning"
            
        return health_status
        
    except Exception as e:
        return {
            "overall_status": "critical",
            "error": f"Health check failed: {str(e)}",
            "checks": [],
            "warnings": [],
            "errors": [f"System health check error: {str(e)}"]
        }

@frappe.whitelist()
def cleanup_old_data():
    """Clean up old logs and data based on settings"""
    try:
        # Default to 30 days for log cleanup
        cleanup_days = 30
        
        # Clean connection logs
        old_connection_logs = frappe.db.sql("""
            DELETE FROM `tabassistant Connection Log`
            WHERE creation < DATE_SUB(NOW(), INTERVAL %s DAY)
        """, (cleanup_days,))
        
        # Clean audit logs (keep longer for compliance)
        audit_cleanup_days = cleanup_days * 2
        old_audit_logs = frappe.db.sql("""
            DELETE FROM `tabassistant Audit Log`
            WHERE creation < DATE_SUB(NOW(), INTERVAL %s DAY)
        """, (audit_cleanup_days,))
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Cleaned up logs older than {cleanup_days} days",
            "connection_logs_deleted": old_connection_logs,
            "audit_logs_deleted": old_audit_logs
        }
        
    except Exception as e:
        frappe.log_error(f"Cleanup error: {str(e)}", "assistant Cleanup")
        return {
            "success": False,
            "error": str(e)
        }