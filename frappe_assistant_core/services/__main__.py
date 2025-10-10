#!/usr/bin/env python3
# Frappe Assistant Core - Services Module Main Entry Point
# Copyright (C) 2025 Paul Clinton

"""
Main entry point for frappe_assistant_core.services module

SSE Bridge service has been removed - use StreamableHTTP (OAuth-based) transport instead.
"""

import sys


def main():
    """Main entry point for services module"""
    print("SSE Bridge service has been deprecated and removed.")
    print("Please use StreamableHTTP (OAuth-based) transport instead.")
    print("No additional services need to be run - everything is integrated with Frappe.")
    sys.exit(0)


if __name__ == "__main__":
    main()
