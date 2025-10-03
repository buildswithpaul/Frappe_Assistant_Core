#!/usr/bin/env python3
# Frappe Assistant Core - SSE MCP Bridge Service
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Enhanced SSE MCP Bridge Service for Frappe Assistant Core
Improvements:
- Proper connection ID management (no user collisions)
- Support for multiple connections per user
- Optional Redis storage for horizontal scaling
- Better error handling and recovery
- Connection health monitoring
- Graceful cleanup mechanisms
"""

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

try:
    import httpx
    from dotenv import load_dotenv
    from fastapi import FastAPI, Header, HTTPException, Query, Request
    from fastapi.responses import JSONResponse, StreamingResponse
    from pydantic import BaseModel
except ImportError as e:
    print(f"Missing required dependencies for SSE bridge: {e}")
    print("Dependencies should already be installed with frappe_assistant_core")
    print("If you see this error, please check your installation")
    exit(1)

# Import configuration reader
try:
    from .config_reader import get_redis_config, get_sse_bridge_config, is_sse_bridge_enabled

    CONFIG_READER_AVAILABLE = True
except ImportError:
    CONFIG_READER_AVAILABLE = False

# Use Frappe's Redis configuration
try:
    import frappe
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Load environment variables from various sources
load_dotenv()  # Load from .env file if present
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class StorageBackend(Enum):
    """Storage backend types"""

    MEMORY = "memory"
    REDIS = "redis"


class MCPRequest(BaseModel):
    """MCP request model"""

    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Any] = None


@dataclass
class ConnectionInfo:
    """Enhanced connection information"""

    connection_id: str
    user_context: str
    server_url: str
    auth_token: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    active: bool = True
    queue: Optional[asyncio.Queue] = None  # Only for memory backend

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage"""
        return {
            "connection_id": self.connection_id,
            "user_context": self.user_context,
            "server_url": self.server_url,
            "auth_token": self.auth_token,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "device_info": self.device_info,
            "ip_address": self.ip_address,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectionInfo":
        """Create from dictionary (for Redis storage)"""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["last_activity"] = datetime.fromisoformat(data["last_activity"])
        return cls(**data)


@dataclass
class PendingRequest:
    """Represents a pending request waiting for SSE connection"""

    request_data: Dict[str, Any]
    server_url: str
    auth_token: str
    timestamp: float = field(default_factory=time.time)
    connection_id: Optional[str] = None  # Target specific connection


class SSEMCPBridge:
    def __init__(self):
        # Storage backend - start with memory, detect Redis during initialization
        self.storage_backend = StorageBackend.MEMORY  # Default to memory

        # Redis configuration
        self.redis_client: Optional[Any] = None  # Will be redis.Redis if available
        self.redis_key_prefix = "sse_bridge:"

        # Enhanced in-memory storage
        self.connections: Dict[str, ConnectionInfo] = {}  # connection_id -> ConnectionInfo
        self.user_connections: Dict[str, Set[str]] = {}  # user_context -> set of connection_ids
        self.connection_queues: Dict[str, asyncio.Queue] = {}  # connection_id -> Queue

        # Pending requests buffer (by connection_id now)
        self.pending_requests: Dict[str, List[PendingRequest]] = {}

        # Configuration - using sensible defaults for Frappe integration
        self.connection_grace_period = 5.0  # seconds to wait for SSE connection
        self.max_idle_time = 300.0  # 5 minutes before cleanup
        self.heartbeat_interval = 30.0  # 30 seconds ping interval
        self.max_connections_per_user = 5  # max devices per user

        # Statistics
        self.stats = {"total_connections": 0, "active_connections": 0, "messages_sent": 0, "errors_count": 0}

    async def initialize(self):
        """Initialize the bridge (connect to Redis if available)"""
        if REDIS_AVAILABLE:
            try:
                # Get Redis configuration from config reader
                if CONFIG_READER_AVAILABLE:
                    redis_config = get_redis_config()
                    logger.info(f"Using Redis config from Frappe: {redis_config}")
                else:
                    # Fallback to manual discovery
                    redis_config = {"host": "localhost", "port": 6379, "db": 0, "decode_responses": True}

                    # Try to read Redis config from bench config files
                    import os

                    bench_dir = os.getcwd()
                    config_paths = [
                        os.path.join(bench_dir, "config", "redis_cache.conf"),
                        os.path.join(bench_dir, "config", "redis_queue.conf"),
                    ]

                    for config_path in config_paths:
                        try:
                            with open(config_path) as f:
                                for line in f:
                                    if line.startswith("port "):
                                        redis_config["port"] = int(line.split()[1])
                                    elif line.startswith("bind "):
                                        bind_addr = line.split()[1]
                                        if bind_addr != "127.0.0.1":
                                            redis_config["host"] = bind_addr
                            break
                        except FileNotFoundError:
                            continue

                # Try to connect to Redis
                self.redis_client = await redis.Redis(**redis_config)
                await self.redis_client.ping()
                self.storage_backend = StorageBackend.REDIS
                logger.info(
                    f"Connected to Redis at {redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
                )

            except Exception as e:
                logger.info(f"Redis not available ({e}), using memory storage for SSE bridge")
                self.storage_backend = StorageBackend.MEMORY

    async def cleanup(self):
        """Cleanup resources"""
        if self.redis_client:
            await self.redis_client.close()

    async def validate_authorization(self, authorization: Optional[str], server_url: str) -> Optional[str]:
        """Validate authorization (Bearer token or API key) with Frappe and return user context"""
        logger.debug(f"Authorization header: {authorization[:50] if authorization else 'None'}...")

        if not authorization:
            logger.warning("Missing authorization header")
            return None

        try:
            frappe_server_url = server_url.rstrip("/")

            # Try OAuth Bearer token first
            if authorization.startswith("Bearer "):
                return await self._validate_auth_token(authorization, frappe_server_url)

            # Try API key:secret format (like stdio bridge)
            elif authorization.startswith("token "):
                return await self._validate_api_key(authorization, frappe_server_url)

            # Try as raw API key (assume it needs a secret from env)
            else:
                # Treat as API key, try to get secret from environment
                api_secret = os.environ.get("FRAPPE_API_SECRET")
                if api_secret:
                    token_auth = f"token {authorization}:{api_secret}"
                    return await self._validate_api_key(token_auth, frappe_server_url)
                else:
                    logger.warning("No FRAPPE_API_SECRET found for API key validation")
                    return None

        except Exception as e:
            logger.error(f"Authorization validation error: {e}")
            return None

    async def _validate_auth_token(self, authorization: str, frappe_server_url: str) -> Optional[str]:
        """Validate OAuth Bearer token"""
        token = authorization.split(" ")[1]
        logger.info(f"Validating OAuth token: {token[:10]}...")

        headers = {"Authorization": authorization, "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{frappe_server_url}/api/method/frappe.auth.get_logged_user", headers=headers, timeout=10.0
            )

        if response.status_code == 200:
            result = response.json()
            user_email = None

            if isinstance(result, dict):
                if "message" in result:
                    user_email = result["message"]
                elif "user" in result:
                    user_email = result["user"]

            if user_email:
                user_context = f"user_{user_email.replace('@', '_').replace('.', '_')}"
                logger.info(f"OAuth validation successful for user: {user_context}")
                return user_context
            else:
                logger.warning("OAuth validation failed - no user in response")
                return None
        else:
            logger.warning(f"OAuth validation failed - status {response.status_code}: {response.text}")
            return None

    async def _validate_api_key(self, authorization: str, frappe_server_url: str) -> Optional[str]:
        """Validate API key:secret token (like stdio bridge)"""
        if authorization.startswith("token "):
            token_part = authorization.split(" ")[1]
            logger.info(f"Validating API key: {token_part.split(':')[0][:10]}...")
        else:
            logger.info(f"Validating API key: {authorization[:10]}...")

        headers = {"Authorization": authorization, "Content-Type": "application/json"}

        # Try the same endpoint as stdio bridge
        test_request = {"jsonrpc": "2.0", "method": "ping", "id": 1}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{frappe_server_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
                headers=headers,
                json=test_request,
                timeout=10.0,
            )

        if response.status_code == 200:
            # Extract user context from API key
            if authorization.startswith("token "):
                api_key = authorization.split(" ")[1].split(":")[0]
            else:
                api_key = authorization.split(":")[0]

            user_context = f"user_{api_key[:10]}"
            logger.info(f"API key validation successful for user: {user_context}")
            return user_context
        else:
            logger.warning(f"API key validation failed - status {response.status_code}: {response.text}")
            return None

    async def create_connection(
        self,
        user_context: str,
        server_url: str,
        auth_token: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> ConnectionInfo:
        """Create a new connection with proper ID management"""
        # Generate unique connection ID
        connection_id = f"{user_context}_{uuid.uuid4().hex[:8]}"

        # Check max connections per user
        if user_context in self.user_connections:
            if len(self.user_connections[user_context]) >= self.max_connections_per_user:
                # Remove oldest connection
                oldest_id = min(self.user_connections[user_context])
                await self.remove_connection(oldest_id)

        # Create connection info
        connection = ConnectionInfo(
            connection_id=connection_id,
            user_context=user_context,
            server_url=server_url,
            auth_token=auth_token,
            device_info=device_info,
            ip_address=ip_address,
        )

        # Store connection
        if self.storage_backend == StorageBackend.REDIS and self.redis_client:
            await self.redis_client.hset(
                f"{self.redis_key_prefix}connections", connection_id, json.dumps(connection.to_dict())
            )
            await self.redis_client.sadd(f"{self.redis_key_prefix}user:{user_context}", connection_id)
        else:
            # Memory storage
            self.connections[connection_id] = connection
            if user_context not in self.user_connections:
                self.user_connections[user_context] = set()
            self.user_connections[user_context].add(connection_id)

            # Create queue for this connection
            self.connection_queues[connection_id] = asyncio.Queue()
            connection.queue = self.connection_queues[connection_id]

        # Update stats
        self.stats["total_connections"] += 1
        self.stats["active_connections"] += 1

        logger.info(f"Created connection {connection_id} for user {user_context}")
        return connection

    async def get_connection(self, connection_id: str) -> Optional[ConnectionInfo]:
        """Get connection by ID"""
        if self.storage_backend == StorageBackend.REDIS and self.redis_client:
            data = await self.redis_client.hget(f"{self.redis_key_prefix}connections", connection_id)
            if data:
                return ConnectionInfo.from_dict(json.loads(data))
        else:
            return self.connections.get(connection_id)
        return None

    async def update_connection_activity(self, connection_id: str):
        """Update last activity timestamp"""
        connection = await self.get_connection(connection_id)
        if connection:
            connection.last_activity = datetime.utcnow()

            if self.storage_backend == StorageBackend.REDIS and self.redis_client:
                await self.redis_client.hset(
                    f"{self.redis_key_prefix}connections", connection_id, json.dumps(connection.to_dict())
                )

    async def remove_connection(self, connection_id: str):
        """Remove a connection properly"""
        connection = await self.get_connection(connection_id)
        if not connection:
            return

        if self.storage_backend == StorageBackend.REDIS and self.redis_client:
            await self.redis_client.hdel(f"{self.redis_key_prefix}connections", connection_id)
            await self.redis_client.srem(
                f"{self.redis_key_prefix}user:{connection.user_context}", connection_id
            )
        else:
            # Memory storage cleanup
            if connection_id in self.connections:
                user_context = self.connections[connection_id].user_context
                del self.connections[connection_id]

                if user_context in self.user_connections:
                    self.user_connections[user_context].discard(connection_id)
                    if not self.user_connections[user_context]:
                        del self.user_connections[user_context]

                if connection_id in self.connection_queues:
                    del self.connection_queues[connection_id]

        # Clean up pending requests
        if connection_id in self.pending_requests:
            del self.pending_requests[connection_id]

        # Update stats
        self.stats["active_connections"] -= 1

        logger.info(f"Removed connection {connection_id}")

    async def send_to_server(
        self, request_data: Dict[str, Any], server_url: str, authorization: str
    ) -> Dict[str, Any]:
        """Send request to HTTP MCP server using authorization header"""
        try:
            server_url = server_url.rstrip("/")

            headers = {"Authorization": authorization, "Content-Type": "application/json"}

            logger.debug(f"Sending to server {server_url}: {request_data}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{server_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
                    headers=headers,
                    json=request_data,
                    timeout=30.0,
                )

            if response.status_code == 200:
                result = response.json()
                # logger.debug(f"Received from server: {result}")

                if isinstance(result, dict) and "message" in result:
                    extracted = result["message"]
                    final_response = self.validate_jsonrpc_response(extracted, request_data.get("id"))
                else:
                    final_response = self.validate_jsonrpc_response(result, request_data.get("id"))

                # Log the actual response being sent back
                if request_data.get("method") == "tools/list":
                    tools_count = 0
                    if isinstance(final_response, dict) and "result" in final_response:
                        if isinstance(final_response["result"], dict) and "tools" in final_response["result"]:
                            tools_count = len(final_response["result"]["tools"])
                    logger.info(f"tools/list response contains {tools_count} tools")

                return final_response
            else:
                logger.error(f"Server returned status {response.status_code}: {response.text}")
                return self.format_error_response(
                    -32603, f"Server error: {response.status_code}", response.text, request_data.get("id")
                )

        except Exception as e:
            logger.error(f"Request failed: {e}")
            return self.format_error_response(-32603, "Internal error", str(e), request_data.get("id"))

    def validate_jsonrpc_response(self, response: Any, request_id: Any = None) -> Dict[str, Any]:
        """Validate and fix JSON-RPC response format"""
        if not isinstance(response, dict):
            return {"jsonrpc": "2.0", "id": request_id, "result": response}

        if "jsonrpc" not in response:
            response["jsonrpc"] = "2.0"

        # Always ensure id field is present for JSON-RPC compliance
        # This is especially important for error responses
        if "id" not in response:
            response["id"] = request_id

        if "result" not in response and "error" not in response:
            return {"jsonrpc": "2.0", "id": request_id, "result": response}

        return response

    def format_error_response(
        self, code: int, message: str, data: Any = None, request_id: Any = None
    ) -> Dict[str, Any]:
        """Format a JSON-RPC error response"""
        response = {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            # Always include id field, even if null, to comply with JSON-RPC spec
            "id": request_id,
        }

        if data is not None:
            response["error"]["data"] = data

        return response

    async def handle_initialization(
        self, request: Dict[str, Any], server_url: str, auth_token: str
    ) -> Dict[str, Any]:
        """Handle MCP initialization - fetch capabilities from actual server"""
        try:
            # Forward initialization to the actual Frappe server to get real capabilities
            server_response = await self.send_to_server(request, server_url, auth_token)

            # If server responded with capabilities, use them
            if (
                isinstance(server_response, dict)
                and "result" in server_response
                and isinstance(server_response["result"], dict)
                and "capabilities" in server_response["result"]
            ):
                logger.info("Using capabilities from Frappe server")
                return server_response

        except Exception as e:
            logger.warning(f"Failed to get capabilities from server: {e}")

        # Fallback to default capabilities
        logger.info("Using default SSE bridge capabilities")
        response = {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "prompts": {"listChanged": True},
                    "resources": {"listChanged": True},
                },
                "serverInfo": {"name": "frappe-mcp-sse-bridge", "version": "2.0.0"},
            },
        }

        if "id" in request and request["id"] is not None:
            response["id"] = request["id"]

        return response

    def handle_resources_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request"""
        response = {"jsonrpc": "2.0", "result": {"resources": []}}

        if "id" in request and request["id"] is not None:
            response["id"] = request["id"]

        return response

    def handle_ping(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request for connection testing"""
        response = {
            "jsonrpc": "2.0",
            "result": {
                "status": "ok",
                "timestamp": time.time(),
                "service": "frappe-mcp-sse-bridge",
                "message": "pong",
            },
        }

        if "id" in request and request["id"] is not None:
            response["id"] = request["id"]

        return response

    def handle_notifications_initialized(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle notifications/initialized - MCP protocol notification sent after initialization"""
        # This is a notification (no id field expected), just acknowledge it
        # Notifications don't require a response in MCP protocol
        logger.info("Client sent notifications/initialized - client is ready")

        # Since this is a notification (no id), we shouldn't send a response
        # But if it has an id (which would be non-standard), respond appropriately
        if "id" in request and request["id"] is not None:
            return {"jsonrpc": "2.0", "id": request["id"], "result": {"status": "acknowledged"}}

        # For standard notifications (no id), return empty response that won't be sent
        return None

    async def queue_response_for_connection(self, connection_id: str, response: Dict[str, Any]):
        """Queue a response to be sent via SSE to specific connection"""
        if self.storage_backend == StorageBackend.REDIS and self.redis_client:
            # For Redis, use pub/sub or a list
            await self.redis_client.rpush(
                f"{self.redis_key_prefix}queue:{connection_id}", json.dumps(response)
            )
        else:
            # Memory queue
            if connection_id in self.connection_queues:
                await self.connection_queues[connection_id].put(response)
                self.stats["messages_sent"] += 1
                logger.info(f"Queued response for connection {connection_id}: id={response.get('id')}")
            else:
                logger.warning(f"No active queue for connection {connection_id}")

    async def get_queued_response(self, connection_id: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Get queued response for a connection"""
        if self.storage_backend == StorageBackend.REDIS and self.redis_client:
            # Use blocking pop with timeout
            result = await self.redis_client.blpop(
                f"{self.redis_key_prefix}queue:{connection_id}", timeout=int(timeout)
            )
            if result:
                return json.loads(result[1])
        else:
            # Memory queue
            if connection_id in self.connection_queues:
                try:
                    return await asyncio.wait_for(
                        self.connection_queues[connection_id].get(), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    return None
        return None

    async def broadcast_to_user(self, user_context: str, message: Dict[str, Any]):
        """Broadcast message to all connections of a user"""
        connection_ids = []

        if self.storage_backend == StorageBackend.REDIS and self.redis_client:
            connection_ids = await self.redis_client.smembers(f"{self.redis_key_prefix}user:{user_context}")
            connection_ids = [cid.decode() for cid in connection_ids]
        else:
            connection_ids = list(self.user_connections.get(user_context, []))

        for connection_id in connection_ids:
            await self.queue_response_for_connection(connection_id, message)

    async def process_pending_requests(self, connection_id: str):
        """Process any pending requests for a connection once established"""
        if connection_id in self.pending_requests:
            pending = self.pending_requests.pop(connection_id)
            logger.info(f"Processing {len(pending)} pending requests for connection {connection_id}")

            for req in pending:
                try:
                    response = await self.send_to_server(req.request_data, req.server_url, req.auth_token)
                    await self.queue_response_for_connection(connection_id, response)
                except Exception as e:
                    logger.error(f"Error processing pending request: {e}")

    async def cleanup_idle_connections(self):
        """Remove idle connections that exceed max idle time"""
        current_time = datetime.utcnow()
        idle_threshold = current_time - timedelta(seconds=self.max_idle_time)

        connections_to_remove = []

        if self.storage_backend == StorageBackend.REDIS and self.redis_client:
            # Get all connections from Redis
            all_connections = await self.redis_client.hgetall(f"{self.redis_key_prefix}connections")
            for conn_id, conn_data in all_connections.items():
                connection = ConnectionInfo.from_dict(json.loads(conn_data))
                if connection.last_activity < idle_threshold:
                    connections_to_remove.append(conn_id.decode())
        else:
            # Check memory connections
            for conn_id, connection in self.connections.items():
                if connection.last_activity < idle_threshold:
                    connections_to_remove.append(conn_id)

        # Remove idle connections
        for conn_id in connections_to_remove:
            logger.info(f"Removing idle connection: {conn_id}")
            await self.remove_connection(conn_id)

    async def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics"""
        stats = self.stats.copy()

        if self.storage_backend == StorageBackend.REDIS and self.redis_client:
            # Get active connections from Redis
            all_connections = await self.redis_client.hlen(f"{self.redis_key_prefix}connections")
            stats["active_connections"] = all_connections
        else:
            stats["active_connections"] = len(self.connections)
            stats["users_connected"] = len(self.user_connections)

        stats["storage_backend"] = self.storage_backend.value
        return stats

    async def process_mcp_request(
        self,
        request_data: Dict[str, Any],
        server_url: str,
        auth_token: str,
        connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process MCP request and optionally queue response for SSE"""
        try:
            method = request_data.get("method")
            request_id = request_data.get("id")

            logger.info(
                f"Processing MCP request: {method} (id: {request_id}) for connection: {connection_id}"
            )

            # Handle methods locally or forward to HTTP server
            if method == "initialize":
                response = await self.handle_initialization(request_data, server_url, auth_token)
            elif method == "resources/list":
                response = self.handle_resources_list(request_data)
            elif method == "ping":
                # Handle ping request - this is for JSON-RPC ping, not SSE keep-alive
                response = self.handle_ping(request_data)
            elif method == "notifications/initialized":
                # Handle MCP protocol notification - client is ready
                response = self.handle_notifications_initialized(request_data)
            else:
                # Forward all other requests to HTTP server
                response = await self.send_to_server(request_data, server_url, auth_token)

            # If connection_id provided, queue the response for SSE
            if connection_id:
                # Only queue response if it's not None (notifications may not need responses)
                if response is not None:
                    await self.queue_response_for_connection(connection_id, response)
                    await self.update_connection_activity(connection_id)
                # Return a simple acknowledgment for POST request
                return {"status": "accepted", "id": request_id, "connection_id": connection_id}
            else:
                # Return response directly (for non-SSE requests)
                return response

        except Exception as e:
            logger.error(f"Error processing MCP request: {e}")
            self.stats["errors_count"] += 1
            error_response = self.format_error_response(
                -32603, "Internal error", str(e), request_data.get("id")
            )

            if connection_id:
                await self.queue_response_for_connection(connection_id, error_response)
                return {"status": "error", "id": request_id, "connection_id": connection_id}
            else:
                return error_response


# Initialize bridge
bridge = SSEMCPBridge()


# Background tasks
async def cleanup_task():
    """Periodically cleanup idle connections"""
    while True:
        await asyncio.sleep(60)  # Run every minute
        try:
            await bridge.cleanup_idle_connections()
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")


async def stats_logger():
    """Periodically log statistics"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        try:
            stats = await bridge.get_stats()
            logger.info(f"Bridge stats: {stats}")
        except Exception as e:
            logger.error(f"Stats logger error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting Enhanced Frappe Assistant Core SSE MCP Bridge")

    # Initialize bridge
    await bridge.initialize()

    # Start background tasks
    cleanup = asyncio.create_task(cleanup_task())
    stats_log = asyncio.create_task(stats_logger())

    yield

    # Cancel background tasks
    cleanup.cancel()
    stats_log.cancel()

    # Cleanup bridge
    await bridge.cleanup()

    logger.info("Shutting down Enhanced Frappe Assistant Core SSE MCP Bridge")


# Create FastAPI app
def create_app():
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title="Frappe Assistant Core SSE Bridge",
        description="SSE bridge for Frappe Assistant Core MCP integration",
        version="2.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        stats = await bridge.get_stats()
        return {"status": "healthy", "service": "frappe-assistant-core-sse-bridge-enhanced", **stats}

    @app.get("/stats")
    async def get_statistics():
        """Get detailed bridge statistics"""
        return await bridge.get_stats()

    @app.get("/mcp/sse")
    async def mcp_sse_endpoint_get(
        request: Request,
        server_url: str = Query(..., description="Frappe server URL"),
        device: Optional[str] = Query(None, description="Device identifier"),
        authorization: Optional[str] = Header(None),
    ):
        """SSE endpoint for MCP - establishes SSE stream with enhanced connection management"""

        # Get client IP
        client_ip = request.client.host if request.client else None

        # Validate authorization
        user_context = await bridge.validate_authorization(authorization, server_url)
        if not user_context:
            raise HTTPException(status_code=401, detail="Invalid or missing authorization")

        async def generate_sse_stream() -> AsyncGenerator[str, None]:
            """Generate SSE stream for MCP responses"""

            # Create connection with enhanced management
            connection = await bridge.create_connection(
                user_context=user_context,
                server_url=server_url,
                auth_token=authorization,
                device_info=device,
                ip_address=client_ip,
            )

            connection_id = connection.connection_id

            try:
                logger.info(f"SSE connection established: {connection_id}")

                # Send connection info to client (use 'endpoint' event for MCP SDK compatibility)
                yield "event: endpoint\n"
                yield f"data: /mcp/messages?cid={connection_id}\n\n"

                # Process any pending requests for this connection
                await bridge.process_pending_requests(connection_id)

                # Keep connection alive and send queued responses
                ping_counter = 0
                while True:
                    try:
                        # Get queued response with timeout
                        response = await bridge.get_queued_response(connection_id, timeout=5.0)

                        if response:
                            yield "event: message\n"
                            yield f"data: {json.dumps(response)}\n\n"
                            await bridge.update_connection_activity(connection_id)
                        else:
                            # Send ping to keep alive
                            ping_counter += 1
                            yield f": ping {ping_counter}\n\n"

                    except Exception as e:
                        logger.error(f"Error in SSE stream {connection_id}: {e}")
                        error_response = bridge.format_error_response(-32603, "Stream error", str(e), None)
                        yield "event: error\n"
                        yield f"data: {json.dumps(error_response)}\n\n"
                        break

            except Exception as e:
                logger.error(f"SSE connection error {connection_id}: {e}")

            finally:
                await bridge.remove_connection(connection_id)
                logger.info(f"SSE connection closed: {connection_id}")

        return StreamingResponse(
            generate_sse_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization",
            },
        )

    @app.post("/mcp/messages")
    async def mcp_messages_endpoint(
        request: Request,
        cid: str = Query(..., description="Connection ID"),
        authorization: Optional[str] = Header(None),
    ):
        """MCP message endpoint - handles POST messages from client"""

        # Get connection
        connection = await bridge.get_connection(cid)
        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")

        # Validate authorization matches
        validated_user = await bridge.validate_authorization(authorization, connection.server_url)
        if not validated_user or validated_user != connection.user_context:
            raise HTTPException(status_code=401, detail="Authorization mismatch")

        try:
            # Read MCP request
            body = await request.body()
            mcp_request = json.loads(body.decode("utf-8"))

            logger.info(f"Received MCP message: {mcp_request.get('method')} from {cid}")

            # Process request and queue response
            await bridge.process_mcp_request(
                mcp_request, connection.server_url, connection.auth_token, connection_id=cid
            )

            return JSONResponse(content={"status": "accepted", "connection_id": cid}, status_code=202)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in POST request: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        except Exception as e:
            logger.error(f"Error processing MCP message: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Add other endpoints...
    return app


def create_pid_file():
    """Create PID file for process management"""
    pid_file = "/tmp/frappe_sse_bridge.pid"
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    return pid_file


def cleanup_pid_file(pid_file):
    """Clean up PID file"""
    try:
        if os.path.exists(pid_file):
            os.remove(pid_file)
            logger.info(f"Cleaned up PID file: {pid_file}")
    except Exception as e:
        logger.warning(f"Could not remove PID file {pid_file}: {e}")


def setup_signal_handlers(pid_file):
    """Setup signal handlers for graceful shutdown"""
    import signal

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        cleanup_pid_file(pid_file)
        # Let the asyncio event loop handle the shutdown
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def main():
    """Main entry point for the enhanced SSE bridge service"""
    import uvicorn

    # Create PID file for process management
    pid_file = create_pid_file()
    logger.info(f"SSE bridge PID file created: {pid_file} (PID: {os.getpid()})")

    # Setup signal handlers
    setup_signal_handlers(pid_file)

    # Get configuration from config reader or environment variables
    if CONFIG_READER_AVAILABLE:
        config = get_sse_bridge_config()
        host = config["host"]
        port = config["port"]
        debug = config["debug"]
        enabled = config["enabled"]

        if not enabled:
            logger.info("SSE bridge is disabled in Assistant Core Settings - exiting")
            logger.info("To enable: Go to Assistant Core Settings and check 'Enable SSE Bridge'")
            cleanup_pid_file(pid_file)
            return

        logger.info("Using configuration from Assistant Core Settings")
        logger.info(f"SSE Bridge enabled: {enabled}")
    else:
        # Fallback to environment variables
        host = os.environ.get("SSE_BRIDGE_HOST", os.environ.get("HOST", "0.0.0.0"))
        port = int(os.environ.get("SSE_BRIDGE_PORT", os.environ.get("PORT", "8080")))
        debug = os.environ.get("SSE_BRIDGE_DEBUG", os.environ.get("DEBUG", "false")).lower() == "true"
        enabled = os.environ.get("SSE_BRIDGE_ENABLED", "true").lower() == "true"

        if not enabled:
            logger.info("SSE bridge is disabled via environment variable SSE_BRIDGE_ENABLED=false")
            cleanup_pid_file(pid_file)
            return

        logger.info("Using configuration from environment variables")

    logger.info(f"Starting Frappe Assistant Core SSE MCP Bridge on {host}:{port}")
    logger.info(f"Process ID: {os.getpid()}")
    logger.info("Storage backend: Will be determined during initialization")
    logger.info(f"Max connections per user: {bridge.max_connections_per_user}")
    logger.info(f"Max idle time: {bridge.max_idle_time}s")
    logger.info(f"Debug mode: {'enabled' if debug else 'disabled'}")
    logger.info("Integration: Independent process with Frappe settings coordination")

    # Create app
    app = create_app()

    try:
        uvicorn.run(app, host=host, port=port, reload=debug, log_level="info" if not debug else "debug")
    except KeyboardInterrupt:
        logger.info("SSE bridge shutting down gracefully...")
    except Exception as e:
        logger.error(f"SSE bridge encountered an error: {e}")
    finally:
        cleanup_pid_file(pid_file)


if __name__ == "__main__":
    main()


# Make this module executable via python -m
def __main__():
    main()
