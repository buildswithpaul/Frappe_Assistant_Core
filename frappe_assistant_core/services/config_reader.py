#!/usr/bin/env python3
# Frappe Assistant Core - Configuration Reader for SSE Bridge
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Configuration reader for SSE Bridge settings.
Reads configuration from Assistant Core Settings doctype with fallback to environment variables.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# SSE bridge configuration removed - SSE transport is deprecated
# Use StreamableHTTP (OAuth-based) transport instead


def get_frappe_redis_config() -> Optional[Dict[str, Any]]:
    """
    Get Redis configuration using Frappe's existing methods.

    Returns:
        Optional[Dict[str, Any]]: Redis configuration or None if not available
    """
    try:
        import frappe
        from frappe.utils.background_jobs import get_redis_conn

        # Try to get Redis connection to validate configuration
        redis_conn = get_redis_conn()

        # Extract connection info from Redis connection
        connection_pool = redis_conn.connection_pool

        redis_config = {
            "host": connection_pool.connection_kwargs.get("host", "localhost"),
            "port": connection_pool.connection_kwargs.get("port", 6379),
            "db": connection_pool.connection_kwargs.get("db", 0),
            "username": connection_pool.connection_kwargs.get("username"),
            "password": connection_pool.connection_kwargs.get("password"),
            "decode_responses": True,
        }

        # Remove None values
        redis_config = {k: v for k, v in redis_config.items() if v is not None}

        logger.info(
            f"Redis config from Frappe: {redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
        )
        return redis_config

    except Exception as e:
        logger.info(f"Failed to get Frappe Redis config ({e}), will fall back to manual discovery")
        return None


def get_fallback_redis_config() -> Dict[str, Any]:
    """
    Get Redis configuration by reading bench config files directly.
    This is used when Frappe context is not available.

    Returns:
        Dict[str, Any]: Redis configuration
    """
    redis_config = {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "decode_responses": True,
    }

    try:
        # Try to find bench directory and read Redis config
        bench_dir = os.getcwd()
        config_paths = [
            os.path.join(bench_dir, "config", "redis_cache.conf"),
            os.path.join(bench_dir, "config", "redis_queue.conf"),
        ]

        for config_path in config_paths:
            try:
                with open(config_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("port "):
                            redis_config["port"] = int(line.split()[1])
                        elif line.startswith("bind "):
                            bind_addr = line.split()[1]
                            if bind_addr != "127.0.0.1":
                                redis_config["host"] = bind_addr
                break  # Use first available config
            except FileNotFoundError:
                continue

        logger.info(
            f"Fallback Redis config: {redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
        )

    except Exception as e:
        logger.warning(f"Failed to read bench Redis config ({e}), using defaults")

    return redis_config


# is_sse_bridge_enabled() removed - SSE transport is deprecated


def get_redis_config() -> Dict[str, Any]:
    """
    Get complete Redis configuration.
    Tries Frappe's method first, then falls back to manual discovery.

    Returns:
        Dict[str, Any]: Redis configuration
    """
    # Try to get Frappe Redis config
    redis_config = get_frappe_redis_config()

    # Return Frappe Redis config if available
    if redis_config:
        return redis_config

    # Fall back to manual discovery
    return get_fallback_redis_config()
