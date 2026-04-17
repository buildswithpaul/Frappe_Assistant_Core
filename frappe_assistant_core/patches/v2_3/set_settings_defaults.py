# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Set default values for Assistant Core Settings fields.

Frappe's cint() casts None → 0 for Int/Check fields, so defaults defined
in the DocType JSON are not applied when the Single DocType is first created.
This one-time patch sets all defaults for existing sites.
"""

import frappe


def execute():
    frappe.reload_doc("assistant_core", "doctype", "assistant_core_settings")

    defaults = {
        "server_enabled": 1,
        "ocr_backend": "paddleocr",
        "ocr_language": "en",
        "paddleocr_timeout": 120,
        "paddleocr_max_memory_mb": 2048,
        "ollama_api_url": "http://localhost:11434",
        "ollama_vision_model": "deepseek-ocr:latest",
        "ollama_request_timeout": 120,
        "code_execution_timeout": 30,
        "code_execution_max_memory_mb": 512,
        "code_execution_max_cpu_seconds": 60,
        "code_execution_max_recursion": 500,
        "audit_log_retention_days": 180,
        "mcp_server_name": "frappe-assistant-core",
        "enable_dynamic_client_registration": 1,
        "show_auth_server_metadata": 1,
        "show_protected_resource_metadata": 1,
        "resource_name": "Frappe Assistant Core",
    }

    for field, value in defaults.items():
        frappe.db.set_single_value("Assistant Core Settings", field, value)
