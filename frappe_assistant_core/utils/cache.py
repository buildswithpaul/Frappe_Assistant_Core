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
Enhanced caching system for Frappe Assistant Core
Leverages Frappe's built-in Redis caching with smart invalidation
"""

import json
import time
from functools import wraps
from typing import Any, Dict, List

import frappe
from frappe.utils import cint, flt
from frappe.utils.caching import redis_cache, site_cache

# Cache TTL constants (in seconds)
CACHE_TTL = {
    "dashboard_stats": 300,  # 5 minutes - frequently accessed
    "server_settings": 1800,  # 30 minutes - rarely changed
    "tool_registry": 3600,  # 1 hour - stable after startup
    "user_permissions": 900,  # 15 minutes - user-specific
    "metadata": 3600,  # 1 hour - DocType metadata
    "system_health": 600,  # 10 minutes - health checks
    "analytics": 600,  # 10 minutes - performance analytics
}

# Cache key prefixes
CACHE_KEYS = {
    "dashboard": "assistant_dashboard",
    "settings": "assistant_settings",
    "tools": "assistant_tools",
    "permissions": "assistant_perms",
    "health": "assistant_health",
    "metadata": "assistant_meta",
}


def get_cache_key(prefix: str, *args) -> str:
    """Generate consistent cache keys"""
    if args:
        suffix = "_".join(str(arg) for arg in args)
        return f"{prefix}_{suffix}"
    return prefix


def cache_with_user_context(ttl=300, shared=False):
    """Custom cache decorator that includes user context"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate user-specific cache key if not shared
            user = frappe.session.user if not shared else "shared"
            cache_key = get_cache_key(func.__name__, user, *args)

            # Try to get from cache
            cached_result = frappe.cache.get_value(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            frappe.cache.set_value(cache_key, result, expires_in_sec=ttl)
            return result

        return wrapper

    return decorator


def cache_with_invalidation(ttl=300, invalidation_keys=None):
    """Cache decorator with dependency-based invalidation"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = get_cache_key(func.__name__, *args)

            # Check if any invalidation keys have changed
            if invalidation_keys:
                for inv_key in invalidation_keys:
                    last_modified = frappe.cache.get_value(f"{inv_key}_modified")
                    if last_modified:
                        # If data was modified, clear cache
                        frappe.cache.delete_key(cache_key)
                        break

            cached_result = frappe.cache.get_value(cache_key)
            if cached_result is not None:
                return cached_result

            result = func(*args, **kwargs)
            frappe.cache.set_value(cache_key, result, expires_in_sec=ttl)
            return result

        return wrapper

    return decorator


@redis_cache(ttl=CACHE_TTL["server_settings"])
def get_cached_server_settings():
    """Cached version of server settings"""
    settings = frappe.get_single("Assistant Core Settings")

    # Get full server URL for MCP endpoint
    frappe_url = frappe.utils.get_url()
    mcp_endpoint_url = f"{frappe_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
    oauth_discovery_url = f"{frappe_url}/.well-known/openid-configuration"

    return {
        "server_enabled": settings.server_enabled,
        "mcp_endpoint_url": mcp_endpoint_url,
        "oauth_discovery_url": oauth_discovery_url,
    }


@redis_cache(ttl=CACHE_TTL["dashboard_stats"], user=True)
def get_cached_dashboard_stats():
    """Cached dashboard statistics - user-specific for permission context"""
    from frappe.utils import today

    # Batch all database queries for efficiency
    stats_data = {}

    # API usage statistics (replacing connection stats)
    api_usage_today = frappe.db.count("Assistant Audit Log", filters={"creation": [">=", today()]})

    stats_data["connections"] = {
        "active": 0,  # No persistent connections in HTTP-based MCP
        "today_total": api_usage_today or 0,  # API calls today
    }

    # Tool statistics from plugin manager
    try:
        from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

        plugin_manager = get_plugin_manager()
        all_tools = plugin_manager.get_all_tools()

        stats_data["tools"] = {
            "total": len(all_tools),
            "enabled": len(all_tools),  # All loaded tools are enabled
        }
    except Exception:
        stats_data["tools"] = {"total": 0, "enabled": 0}

    # Action statistics for today
    action_stats = frappe.db.sql(
        """
        SELECT
            COUNT(*) as total_actions,
            COUNT(CASE WHEN status = 'Success' THEN 1 END) as successful_actions
        FROM `tabAssistant Audit Log`
        WHERE DATE(creation) = %s
    """,
        (today(),),
        as_dict=True,
    )

    total_actions = action_stats[0]["total_actions"] if action_stats else 0
    successful_actions = action_stats[0]["successful_actions"] if action_stats else 0
    success_rate = (successful_actions / total_actions * 100) if total_actions > 0 else 0

    stats_data["performance"] = {"actions_today": total_actions, "success_rate": round(success_rate, 2)}

    return stats_data


@redis_cache(ttl=CACHE_TTL["dashboard_stats"])
def get_cached_most_used_tools():
    """Cache most used tools separately - can have different TTL"""
    from frappe.utils import today

    most_used_tools = frappe.db.sql(
        """
        SELECT tool_name, COUNT(*) as count
        FROM `tabAssistant Audit Log`
        WHERE DATE(creation) = %s AND tool_name IS NOT NULL
        GROUP BY tool_name
        ORDER BY count DESC
        LIMIT 5
    """,
        (today(),),
        as_dict=True,
    )

    return most_used_tools


@redis_cache(ttl=CACHE_TTL["analytics"])
def get_cached_category_performance():
    """Cache category performance analytics"""
    from frappe.utils import today

    # Since we no longer have tool categories in a registry, group by tool name patterns
    category_performance = frappe.db.sql(
        """
        SELECT
            CASE
                WHEN tool_name LIKE 'document_%' THEN 'Document Operations'
                WHEN tool_name LIKE 'report_%' THEN 'Reports'
                WHEN tool_name LIKE 'search_%' THEN 'Search'
                WHEN tool_name LIKE 'metadata_%' THEN 'Metadata'
                WHEN tool_name LIKE 'execute_%' OR tool_name LIKE 'analyze_%' THEN 'Analysis'
                ELSE 'Other'
            END as category,
            AVG(execution_time) as avg_time,
            COUNT(*) as count
        FROM `tabAssistant Audit Log`
        WHERE DATE(creation) = %s AND execution_time IS NOT NULL
        GROUP BY category
        ORDER BY avg_time DESC
    """,
        (today(),),
        as_dict=True,
    )

    return category_performance


@frappe.whitelist()
def clear_all_caches():
    """Clear all assistant-related caches."""
    try:
        # Clear Redis caches
        frappe.cache().delete_keys("assistant_*")
        frappe.cache().delete_keys("tool_*")
        frappe.cache().delete_keys("plugin_*")

        # Clear site cache if available
        if hasattr(frappe.local, "site_cache"):
            frappe.local.site_cache.clear()

        return {"success": True, "message": "All caches cleared successfully"}
    except Exception as e:
        frappe.log_error(f"Failed to clear caches: {str(e)}")
        return {"success": False, "error": str(e)}


@site_cache(ttl=CACHE_TTL["tool_registry"])
def get_cached_tool_registry_stats():
    """Cache tool registry statistics - process-local cache"""
    from frappe_assistant_core.core.tool_registry import get_tool_registry

    try:
        registry = get_tool_registry()
        tools = registry.get_available_tools()
        stats = {
            "total_tools": len(tools),
            "enabled_tools": len(tools),  # All tools from registry are enabled
        }
        return stats
    except Exception as e:
        frappe.log_error(f"Tool registry stats error: {str(e)}")
        return {"error": str(e)}


@redis_cache(ttl=CACHE_TTL["user_permissions"], user=True)
def get_cached_user_tool_permissions(user=None):
    """Cache user's tool permissions"""
    from frappe_assistant_core.core.tool_registry import get_tool_registry

    user = user or frappe.session.user
    registry = get_tool_registry()
    accessible_tools = registry.get_available_tools(user)

    return {
        "user": user,
        "accessible_tools_count": len(accessible_tools),
        "tool_names": [tool.get("name") for tool in accessible_tools],
    }


@redis_cache(ttl=CACHE_TTL["system_health"])
def get_cached_system_health():
    """Cache system health check results"""
    from frappe.utils import today

    health_status = {
        "overall_status": "healthy",
        "timestamp": frappe.utils.now(),
        "checks_passed": 0,
        "warnings": 0,
        "errors": 0,
    }

    try:
        # Quick health checks
        required_doctypes = ["Assistant Core Settings", "Assistant Audit Log"]

        missing_doctypes = []
        for doctype in required_doctypes:
            if not frappe.db.table_exists(f"tab{doctype}"):
                missing_doctypes.append(doctype)

        if missing_doctypes:
            health_status["errors"] = len(missing_doctypes)
            health_status["overall_status"] = "critical"
        else:
            health_status["checks_passed"] += len(required_doctypes)

        # Check recent error rates from audit logs
        recent_errors = frappe.db.count(
            "Assistant Audit Log", filters={"status": "Error", "creation": [">=", today()]}
        )

        if recent_errors > 10:
            health_status["warnings"] += 1
            if health_status["overall_status"] == "healthy":
                health_status["overall_status"] = "warning"

        return health_status

    except Exception as e:
        return {"overall_status": "critical", "error": str(e), "timestamp": frappe.utils.now()}


# Cache invalidation functions
def invalidate_settings_cache(doc=None, method=None):
    """Invalidate settings-related caches"""
    cache_keys = [get_cache_key(CACHE_KEYS["settings"]), "get_cached_server_settings"]

    for key in cache_keys:
        frappe.cache.delete_key(key)

    # Mark settings as modified for dependent caches
    frappe.cache.set_value("settings_modified", frappe.utils.now(), expires_in_sec=3600)


def invalidate_dashboard_cache(doc=None, method=None):
    """Invalidate dashboard-related caches

    Args:
        doc: Document instance (passed by hooks)
        method: Method name (passed by hooks)
    """
    # Clear all user-specific dashboard caches
    frappe.cache.delete_keys("get_cached_dashboard_stats_*")
    frappe.cache.delete_keys("assistant_dashboard_*")
    frappe.cache.delete_key("get_cached_most_used_tools")
    frappe.cache.delete_key("get_cached_category_performance")


def invalidate_tool_registry_cache():
    """Invalidate tool registry caches"""
    from frappe_assistant_core.core.tool_registry import get_tool_registry

    # Clear registry caches
    registry = get_tool_registry()
    registry._discover_tools()  # Force refresh
    frappe.cache.delete_key("get_cached_tool_registry_stats")
    frappe.cache.delete_keys("get_cached_user_tool_permissions_*")


def invalidate_user_permission_cache(user=None):
    """Invalidate user-specific permission caches"""
    if user:
        user_cache_pattern = f"*{user}*"
        frappe.cache.delete_keys(f"get_cached_user_tool_permissions_{user_cache_pattern}")
    else:
        # Clear all user permission caches
        frappe.cache.delete_keys("get_cached_user_tool_permissions_*")


def clear_all_assistant_cache():
    """Clear all assistant-related caches"""
    cache_patterns = ["assistant_*", "get_cached_*"]

    for pattern in cache_patterns:
        frappe.cache.delete_keys(pattern)

    # Clear tool registry cache
    invalidate_tool_registry_cache()


def get_cache_statistics():
    """Get caching system statistics"""
    try:
        # This would need Redis info if available
        cache_info = {
            "cache_backend": "Redis" if frappe.cache.redis else "Memory",
            "cache_keys_active": "Unknown",  # Redis would need KEYS command
            "last_cleared": frappe.cache.get_value("last_cache_clear") or "Never",
        }

        return cache_info
    except Exception as e:
        return {"error": str(e)}


# Utility functions for cache warming
def warm_cache():
    """Pre-warm frequently used caches"""
    try:
        # Pre-load settings
        get_cached_server_settings()

        # Pre-load tool registry
        get_cached_tool_registry_stats()

        # Pre-load system health
        get_cached_system_health()

        frappe.logger().info("Assistant cache warmed successfully")
        return True

    except Exception as e:
        frappe.log_error(f"Cache warming failed: {str(e)}")
        return False


# Cache performance monitoring
def log_cache_performance(func_name, execution_time, cache_hit=False):
    """Log cache performance metrics"""
    if frappe.conf.get("assistant_cache_monitoring"):
        frappe.logger().info(f"Cache {'HIT' if cache_hit else 'MISS'}: {func_name} - {execution_time:.3f}s")
