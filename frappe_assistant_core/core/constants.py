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

"""
Constants for Frappe Assistant Core.
Centralized configuration values, limits, and system constants.
"""

# MCP Protocol Constants
MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_JSONRPC_VERSION = "2.0"

# Server Information
SERVER_NAME = "frappe-assistant-core"
DEFAULT_SERVER_VERSION = "1.0.0"

# Request/Response Limits
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50MB
DEFAULT_REQUEST_TIMEOUT = 120  # seconds
MAX_REQUEST_TIMEOUT = 600  # 10 minutes

# Tool Execution Limits
MAX_TOOL_EXECUTION_TIME = 300  # 5 minutes
DEFAULT_TOOL_TIMEOUT = 60  # 1 minute
MAX_CONCURRENT_TOOLS = 10
MAX_QUERY_RESULTS = 10000
DEFAULT_QUERY_LIMIT = 1000

# Cache Configuration
DEFAULT_CACHE_TTL = 3600  # 1 hour
TOOL_REGISTRY_CACHE_KEY = "assistant_tools"
PLUGIN_CACHE_KEY = "assistant_plugins"
SETTINGS_CACHE_KEY = "assistant_settings"
PERFORMANCE_CACHE_KEY = "assistant_metrics"

# Plugin System Constants
PLUGIN_DISCOVERY_PATHS = [
    "frappe_assistant_core.plugins",
    "plugins"
]
MAX_PLUGIN_LOAD_TIME = 30  # seconds
PLUGIN_CONFIG_VALIDATION_TIMEOUT = 10  # seconds

# Tool Categories
TOOL_CATEGORIES = {
    "DOCUMENT": "document",
    "SEARCH": "search", 
    "METADATA": "metadata",
    "REPORT": "report",
    "WORKFLOW": "workflow",
    "DATA_SCIENCE": "data_science",
    "CUSTOM": "custom"
}

# Core Tool Names
CORE_TOOLS = {
    # Document tools
    "DOCUMENT_CREATE": "document_create",
    "DOCUMENT_GET": "document_get",
    "DOCUMENT_UPDATE": "document_update",
    "DOCUMENT_DELETE": "document_delete",
    "DOCUMENT_LIST": "document_list",
    "DOCUMENT_BULK_CREATE": "document_bulk_create",
    "DOCUMENT_BULK_UPDATE": "document_bulk_update",
    
    # Search tools
    "SEARCH_GLOBAL": "search_global",
    "SEARCH_DOCTYPE": "search_doctype",
    "SEARCH_LINK": "search_link",
    
    # Metadata tools
    "METADATA_DOCTYPE": "metadata_doctype",
    "METADATA_LIST_DOCTYPES": "list_doctypes",
    "METADATA_DOCTYPE_FIELDS": "metadata_doctype_fields",
    
    # Report tools
    "REPORT_EXECUTE": "report_execute",
    "REPORT_LIST": "report_list",
    "REPORT_DETAILS": "report_details",
    
    # Workflow tools
    "WORKFLOW_ACTION": "workflow_action",
    "WORKFLOW_STATUS": "workflow_status",
    "WORKFLOW_LIST": "workflow_list"
}

# Plugin Tool Names
PLUGIN_TOOLS = {
    # Data Science tools
    "EXECUTE_PYTHON_CODE": "execute_python_code",
    "ANALYZE_FRAPPE_DATA": "analyze_frappe_data",
    "QUERY_AND_ANALYZE": "query_and_analyze",
    "CREATE_VISUALIZATION": "create_visualization"
}

# Error Codes
ERROR_CODES = {
    # JSON-RPC standard errors
    "PARSE_ERROR": -32700,
    "INVALID_REQUEST": -32600,
    "METHOD_NOT_FOUND": -32601,
    "INVALID_PARAMS": -32602,
    "INTERNAL_ERROR": -32603,
    
    # Custom application errors
    "PERMISSION_DENIED": -32001,
    "TOOL_NOT_FOUND": -32002,
    "TOOL_EXECUTION_ERROR": -32003,
    "VALIDATION_ERROR": -32004,
    "TIMEOUT_ERROR": -32005,
    "PLUGIN_ERROR": -32006,
    "CONFIGURATION_ERROR": -32007,
    "DEPENDENCY_ERROR": -32008
}

# HTTP Status Codes
HTTP_STATUS = {
    "OK": 200,
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "METHOD_NOT_ALLOWED": 405,
    "TIMEOUT": 408,
    "PAYLOAD_TOO_LARGE": 413,
    "TOO_MANY_REQUESTS": 429,
    "INTERNAL_SERVER_ERROR": 500,
    "SERVICE_UNAVAILABLE": 503
}

# Logging Levels
LOG_LEVELS = {
    "DEBUG": "debug",
    "INFO": "info",
    "WARNING": "warning",
    "ERROR": "error",
    "CRITICAL": "critical"
}

# Performance Monitoring
PERFORMANCE_METRICS = {
    "TOOL_EXECUTION_TIME": "tool_execution_time",
    "REQUEST_PROCESSING_TIME": "request_processing_time",
    "CACHE_HIT_RATE": "cache_hit_rate",
    "ERROR_RATE": "error_rate",
    "CONCURRENT_REQUESTS": "concurrent_requests",
    "MEMORY_USAGE": "memory_usage"
}

# Data Science Constants
DATA_SCIENCE_LIMITS = {
    "MAX_DATAFRAME_ROWS": 100000,
    "MAX_VISUALIZATION_POINTS": 5000,
    "MAX_CODE_EXECUTION_TIME": 60,
    "MAX_MEMORY_USAGE": 512 * 1024 * 1024,  # 512MB
    "ALLOWED_LIBRARIES": [
        "pandas", "numpy", "matplotlib", "seaborn", 
        "plotly", "scipy", "sklearn", "statsmodels"
    ],
    "RESTRICTED_MODULES": [
        "os", "sys", "subprocess", "socket", "urllib",
        "requests", "http", "ftplib", "smtplib"
    ]
}



# Security Constants
SECURITY_CONFIG = {
    "MAX_LOGIN_ATTEMPTS": 5,
    "LOGIN_LOCKOUT_TIME": 300,  # 5 minutes
    "SESSION_TIMEOUT": 86400,  # 24 hours
    "API_RATE_LIMIT": 60,  # requests per minute
    "MAX_REQUEST_RETRIES": 3,
    "ALLOWED_CONTENT_TYPES": [
        "application/json",
        "text/plain",
        "multipart/form-data"
    ]
}

# File Processing Constants
FILE_PROCESSING = {
    "MAX_FILE_SIZE": 50 * 1024 * 1024,  # 50MB
    "ALLOWED_EXTENSIONS": [
        ".json", ".csv", ".xlsx", ".txt", ".pdf",
        ".png", ".jpg", ".jpeg", ".gif", ".svg"
    ],
    "TEMP_FILE_CLEANUP_HOURS": 24,
    "MAX_CONCURRENT_UPLOADS": 5
}

# Database Query Constants
DATABASE_LIMITS = {
    "MAX_QUERY_LENGTH": 50000,  # characters
    "DEFAULT_FETCH_SIZE": 1000,
    "MAX_FETCH_SIZE": 10000,
    "QUERY_TIMEOUT": 300,  # 5 minutes
    "MAX_JOIN_TABLES": 10,
    "MAX_WHERE_CONDITIONS": 20
}

# API Endpoint Paths
API_ENDPOINTS = {
    "MCP_HANDLER": "/api/method/frappe_assistant_core.api.mcp.handle_mcp_request",
    "PLUGIN_MANAGEMENT": "/api/method/frappe_assistant_core.api.plugin_api",
    "ADMIN_ENDPOINTS": "/api/method/frappe_assistant_core.api.admin",
    "HEALTH_CHECK": "/api/method/frappe_assistant_core.api.health",
    "WEBSOCKET_ENDPOINT": "/ws/assistant"
}

# Plugin Status Values
PLUGIN_STATUS = {
    "DISCOVERED": "discovered",
    "ENABLED": "enabled",
    "DISABLED": "disabled",
    "ERROR": "error",
    "LOADING": "loading",
    "UNLOADING": "unloading"
}

# Tool Status Values
TOOL_STATUS = {
    "AVAILABLE": "available",
    "EXECUTING": "executing",
    "ERROR": "error",
    "TIMEOUT": "timeout",
    "DISABLED": "disabled"
}

# MCP Content Types
MCP_CONTENT_TYPES = {
    "TEXT": "text",
    "IMAGE": "image",
    "RESOURCE": "resource"
}

# System Health Status
HEALTH_STATUS = {
    "HEALTHY": "healthy",
    "DEGRADED": "degraded", 
    "UNHEALTHY": "unhealthy",
    "UNKNOWN": "unknown"
}

# Feature Flags
FEATURE_FLAGS = {
    "ENABLE_PERFORMANCE_MONITORING": True,
    "ENABLE_DETAILED_LOGGING": True,
    "ENABLE_CACHE_COMPRESSION": False,
    "ENABLE_ASYNC_TOOLS": False,
    "ENABLE_TOOL_CHAINING": False,
    "ENABLE_CUSTOM_VALIDATORS": True,
    "ENABLE_PLUGIN_SANDBOXING": True
}

# Default Settings
DEFAULT_SETTINGS = {
    "enable_assistant": True,
    "max_request_size": MAX_REQUEST_SIZE,
    "request_timeout": DEFAULT_REQUEST_TIMEOUT,
    "cache_enabled": True,
    "cache_ttl": DEFAULT_CACHE_TTL,
    "log_level": "info",
    "enable_performance_monitoring": True,
    "enable_detailed_audit": False,
    "max_concurrent_requests": 10,
    "enable_rate_limiting": True,
    "rate_limit_per_minute": 60
}

# Validation Patterns
VALIDATION_PATTERNS = {
    "TOOL_NAME": r"^[a-z][a-z0-9_]*$",
    "PLUGIN_NAME": r"^[a-z][a-z0-9_]*$",
    "VERSION": r"^\d+\.\d+\.\d+.*$",
    "EMAIL": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "URL": r"^https?://[^\s/$.?#].[^\s]*$",
    "DOCTYPE_NAME": r"^[A-Z][A-Za-z0-9\s]*$",
    "FIELD_NAME": r"^[a-z][a-z0-9_]*$"
}

# Message Templates
MESSAGE_TEMPLATES = {
    "TOOL_EXECUTION_SUCCESS": "Tool '{tool_name}' executed successfully",
    "TOOL_EXECUTION_ERROR": "Tool '{tool_name}' execution failed: {error}",
    "PLUGIN_ENABLED": "Plugin '{plugin_name}' enabled successfully",
    "PLUGIN_DISABLED": "Plugin '{plugin_name}' disabled successfully",
    "PLUGIN_ERROR": "Plugin '{plugin_name}' error: {error}",
    "VALIDATION_ERROR": "Validation failed for '{field}': {error}",
    "PERMISSION_DENIED": "Insufficient permissions to access '{resource}'",
    "TIMEOUT_ERROR": "Operation timed out after {timeout} seconds",
    "RATE_LIMIT_EXCEEDED": "Rate limit exceeded. Try again in {retry_after} seconds"
}

# Environment Variables
ENV_VARS = {
    "FRAPPE_ASSISTANT_DEBUG": "FRAPPE_ASSISTANT_DEBUG",
    "FRAPPE_ASSISTANT_LOG_LEVEL": "FRAPPE_ASSISTANT_LOG_LEVEL",
    "FRAPPE_ASSISTANT_CACHE_TTL": "FRAPPE_ASSISTANT_CACHE_TTL",
    "FRAPPE_ASSISTANT_MAX_REQUESTS": "FRAPPE_ASSISTANT_MAX_REQUESTS",
    "FRAPPE_ASSISTANT_TIMEOUT": "FRAPPE_ASSISTANT_TIMEOUT",
    "FRAPPE_ASSISTANT_PLUGIN_PATH": "FRAPPE_ASSISTANT_PLUGIN_PATH"
}