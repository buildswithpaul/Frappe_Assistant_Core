#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Frappe Assistant Core - Services Module Main Entry Point
# Copyright (C) 2025 Paul Clinton

"""
Main entry point for frappe_assistant_core.services module

This allows running services as: python -m frappe_assistant_core.services.sse_bridge
"""

import sys
import os

def main():
    """Main entry point for services module"""
    if len(sys.argv) < 2:
        print("Usage: python -m frappe_assistant_core.services <service_name>")
        print("Available services:")
        print("  sse_bridge - SSE MCP Bridge for Claude API integration")
        sys.exit(1)
    
    service_name = sys.argv[1]
    
    if service_name == "sse_bridge":
        from .sse_bridge import main as sse_main
        sse_main()
    else:
        print(f"Unknown service: {service_name}")
        sys.exit(1)

if __name__ == "__main__":
    main()