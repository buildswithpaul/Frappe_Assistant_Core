

from frappe import _
import frappe
from typing import Optional
import os
import json

# Constants
DEFAULT_PORT = 8000  # Frappe's default port fallback

def get_frappe_port():
    """Get Frappe's actual running port from configuration"""
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

class assistantServer:
    """Main assistant Server class - manages MCP API state"""
    
    def __init__(self):
        self.running = False
        
    def enable(self):
        """Enable the assistant MCP API endpoints"""
        try:
            settings = frappe.get_single("Assistant Core Settings")
            
            if not settings.server_enabled:
                return {"success": False, "message": "MCP API is disabled in settings"}
            
            # Mark as enabled (API endpoints are always available when enabled)
            self.running = True
            
            frappe.logger().info("assistant MCP API endpoints enabled")
            return {"success": True, "message": f"MCP API enabled - available at /api/method/frappe_assistant_core.api.assistant_api.handle_assistant_request"}
            
        except Exception as e:
            frappe.log_error(f"Failed to enable MCP API: {str(e)}")
            return {"success": False, "message": f"Failed to enable MCP API: {str(e)}"}
    
    def disable(self):
        """Disable the assistant MCP API endpoints"""
        if not self.running:
            return {"success": False, "message": "MCP API is not enabled"}
        
        try:
            self.running = False
            
            frappe.logger().info("assistant MCP API endpoints disabled")
            return {"success": True, "message": "MCP API endpoints disabled"}
            
        except Exception as e:
            frappe.log_error(f"Failed to disable MCP API: {str(e)}")
            return {"success": False, "message": f"Failed to disable MCP API: {str(e)}"}
    
    def get_status(self):
        """Get server status including WebSocket status"""
        from frappe_assistant_core.utils.cache import get_cached_server_settings
        
        settings = get_cached_server_settings()
        
        # Server is running if it's enabled (since API endpoints are always available)
        is_running = bool(settings.get("server_enabled"))
        
        # Check WebSocket status
        websocket_status = {"enabled": False, "running": False}
        if settings.get("websocket_enabled"):
            try:
                from frappe_assistant_core.assistant_core.websocket_server import get_websocket_server
                ws_server = get_websocket_server()
                websocket_status = {
                    "enabled": True,
                    "running": ws_server.running,
                    "connections": len(ws_server.connections),
                    "endpoint": "ws://localhost:8001/mcp?api_key=YOUR_KEY&api_secret=YOUR_SECRET"
                }
            except Exception:
                websocket_status = {"enabled": True, "running": False, "error": "Failed to get WebSocket status"}
        
        return {
            "running": is_running,  # For backward compatibility
            "enabled": settings.get("server_enabled"),
            "api_endpoint": f"/api/method/frappe_assistant_core.api.assistant_api.handle_assistant_request",
            "ping_endpoint": f"/api/method/frappe_assistant_core.api.assistant_api.ping",
            "protocol": "mcp",
            "frappe_port": f"{get_frappe_port()} (detected)",
            "websocket": websocket_status,
            "status_note": "MCP API endpoints are part of Frappe's web server - no separate process required"
        }

# Global server instance
_server_instance: Optional[assistantServer] = None

def get_server_instance() -> assistantServer:
    """Get or create the global server instance"""
    global _server_instance
    if _server_instance is None:
        _server_instance = assistantServer()
    return _server_instance

@frappe.whitelist(allow_guest=False)
def enable_api():
    """Enable the assistant MCP API"""
    server = get_server_instance()
    return server.enable()

@frappe.whitelist(allow_guest=False)
def disable_api():
    """Disable the assistant MCP API"""
    server = get_server_instance()
    return server.disable()

# Legacy functions for backward compatibility
@frappe.whitelist(allow_guest=False)
def start_server():
    """Legacy: Enable the assistant MCP API"""
    return enable_api()

@frappe.whitelist(allow_guest=False)
def stop_server():
    """Legacy: Disable the assistant MCP API"""
    return disable_api()

@frappe.whitelist(allow_guest=False)
def get_server_status():
    """Get server status"""
    server = get_server_instance()
    return server.get_status()

def cleanup_old_logs():
    """Cleanup old log entries (scheduled task)"""
    try:
        settings = frappe.get_single("Assistant Core Settings")
        days_to_keep = settings.cleanup_logs_after_days or 30
        
        # Cleanup connection logs
        frappe.db.sql("""
            DELETE FROM `tabAssistant Connection Log` 
            WHERE creation < DATE_SUB(NOW(), INTERVAL %s DAY)
        """, (days_to_keep,))
        
        # Cleanup audit logs (keep more audit logs)
        audit_days = days_to_keep * 2
        frappe.db.sql("""
            DELETE FROM `tabAssistant Audit Log` 
            WHERE creation < DATE_SUB(NOW(), INTERVAL %s DAY)
        """, (audit_days,))
        
        frappe.db.commit()
        frappe.logger().info(f"Cleaned up assistant logs older than {days_to_keep} days")
        
    except Exception as e:
        frappe.log_error(f"Failed to cleanup assistant logs: {str(e)}")

def update_connection_stats():
    """Update connection statistics (scheduled task)"""
    try:
        # Mark stale connections as disconnected
        frappe.db.sql("""
            UPDATE `tabAssistant Connection Log` 
            SET status = 'Timeout', disconnected_at = NOW()
            WHERE status = 'Connected' 
            AND last_activity < DATE_SUB(NOW(), INTERVAL 1 HOUR)
        """)
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Failed to update connection stats: {str(e)}")

def start_background_server():
    """Enable API in background job (legacy)"""
    return enable_api()

def enable_background_api():
    """Enable API in background job"""
    return enable_api()