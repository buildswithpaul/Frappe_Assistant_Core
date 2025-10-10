# Frappe Assistant Core - Services Module
# Copyright (C) 2025 Paul Clinton

"""
Services module for Frappe Assistant Core

SSE Bridge has been deprecated and removed.
Use StreamableHTTP (OAuth-based) transport instead.
"""

# Import version from parent module
try:
    from frappe_assistant_core import __version__
except ImportError:
    __version__ = "unknown"
