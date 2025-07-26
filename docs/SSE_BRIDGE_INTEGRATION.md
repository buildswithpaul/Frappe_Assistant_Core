# SSE Bridge Integration Guide

## Table of Contents
- [Overview](#overview)
- [Why SSE Bridge Was Created](#why-sse-bridge-was-created)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Development Environment](#development-environment)
- [Production Environment](#production-environment)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## Overview

The SSE (Server-Sent Events) Bridge is a critical component of Frappe Assistant Core that enables real-time communication between Claude API and Frappe through the Model Context Protocol (MCP). It provides a robust, production-ready bridge that handles race conditions and maintains persistent connections for streaming responses.

**Key Features:**
- ✅ Real-time streaming communication with Claude API
- ✅ Robust race condition handling 
- ✅ Request buffering for delayed connections
- ✅ Multiple authentication methods (Bearer tokens, API keys)
- ✅ Automatic cleanup and connection management
- ✅ Health monitoring and metrics
- ✅ Production-ready with proper logging

## Why SSE Bridge Was Created

### The Problem

Initially, Frappe Assistant Core attempted to implement SSE streaming natively within the Frappe framework. However, this approach faced fundamental limitations:

1. **Frappe's SSE Limitations**: Frappe doesn't support true SSE streaming with persistent `text/event-stream` connections
2. **Claude API Requirements**: Claude's MCP implementation requires genuine SSE streaming for real-time communication
3. **Framework Constraints**: Frappe's request/response model isn't designed for long-lived streaming connections

### The Solution

The SSE Bridge acts as an external service that:

- **Bridges the Gap**: Provides true SSE streaming capabilities that Frappe cannot natively support
- **Maintains Compatibility**: Works seamlessly with Frappe's authentication and API systems
- **Enables Real-time Communication**: Allows Claude to receive streaming responses as required by MCP
- **Handles Complexity**: Manages connection lifecycle, race conditions, and error recovery

### Design Decisions

1. **External Service Approach**: Deployed as a separate FastAPI service for true SSE capabilities
2. **Integrated Lifecycle**: Managed through Frappe's bench system for seamless operation
3. **Optional Dependencies**: Added as optional `[sse-bridge]` extras to avoid forcing dependencies
4. **Production Ready**: Designed for both development and production deployment scenarios

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Claude API    │◄──►│   SSE Bridge    │◄──►│  Frappe Server  │
│   (MCP Client)  │    │  (FastAPI App)  │    │ (Assistant API) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │                       │                       │
        ▼                       ▼                       ▼
   SSE Streaming          Race Condition           MCP Request
   Real-time             Handling &               Processing &
   Communication         Request Buffering        Tool Execution
```

### Components

1. **SSE Bridge Service** (`frappe_assistant_core.services.sse_bridge`)
   - FastAPI application providing SSE endpoints
   - Handles MCP protocol communication
   - Manages connection lifecycle and cleanup

2. **Connection Manager**
   - Tracks active SSE connections per user
   - Buffers requests before connection establishment
   - Implements cleanup for idle connections

3. **Authentication Handler**
   - Supports Bearer tokens (OAuth2.0)
   - Supports API key:secret authentication
   - Validates with Frappe backend

4. **Request Processor**
   - Routes MCP requests to appropriate handlers
   - Queues responses for SSE delivery
   - Handles JSON-RPC 2.0 format validation

## Installation

### Prerequisites

- Frappe Assistant Core app installed
- Python 3.8+ environment
- Network access for Claude API integration

### Install Dependencies

The SSE Bridge requires additional dependencies that are installed as optional extras:

```bash
# Install with SSE Bridge support
pip install frappe_assistant_core[sse-bridge]

# Or install individual dependencies
pip install "fastapi>=0.100.0" "uvicorn>=0.20.0" "python-dotenv>=1.0.0" "python-multipart>=0.0.6"
```

### Verify Installation

```bash
# Test module import
python -c "from frappe_assistant_core.services.sse_bridge import main; print('✅ SSE Bridge ready!')"

# Check app creation
python -c "from frappe_assistant_core.services.sse_bridge import create_app; app = create_app(); print(f'✅ {app.title} v{app.version}')"
```

## Configuration

### Environment Variables

The SSE Bridge supports configuration through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8080` | Server port (avoid 8000 - used by bench) |
| `DEBUG` | `false` | Enable debug mode with verbose logging |
| `FRAPPE_API_SECRET` | `None` | API secret for legacy API key authentication |
| `LOG_LEVEL` | `info` | Logging level (debug, info, warning, error) |

### Configuration Methods

#### Method 1: Environment Variables (Recommended for Production)
```bash
export HOST=0.0.0.0
export PORT=8080
export DEBUG=false
export LOG_LEVEL=info
```

#### Method 2: .env File (Development)
Create `.env` file in your working directory:
```env
# SSE MCP Bridge Configuration
HOST=0.0.0.0
PORT=8080
DEBUG=true
LOG_LEVEL=debug
FRAPPE_API_SECRET=your_api_secret_here
```

#### Method 3: Procfile Integration (Bench)
Configuration is handled automatically through the Procfile:
```procfile
sse_bridge: PORT=8080 python -c "from frappe_assistant_core.services.sse_bridge import main; main()"
```

## Development Environment

### Using with Bench

The SSE Bridge is automatically integrated with bench's process management:

```bash
# Start all services including SSE Bridge
bench start

# Start only the SSE Bridge
bench start sse_bridge

# Check if SSE Bridge is running
curl http://localhost:8080/health
```

### Manual Development Startup

For development and testing:

```bash
# Set environment variables
export PORT=8080
export DEBUG=true
export LOG_LEVEL=debug

# Start the service directly
python -c "from frappe_assistant_core.services.sse_bridge import main; main()"

# Or with uvicorn for advanced options
uvicorn frappe_assistant_core.services.sse_bridge:create_app --factory --host 0.0.0.0 --port 8080 --reload
```

### Development Configuration

```env
# .env for development
HOST=0.0.0.0
PORT=8080
DEBUG=true
LOG_LEVEL=debug

# Optional: API secret for testing legacy clients
FRAPPE_API_SECRET=your_development_secret
```

### Logging in Development

With `DEBUG=true`, you'll see detailed logs:
```
2025-01-26 22:35:27 - frappe_assistant_core.services.sse_bridge - INFO - Starting Frappe Assistant Core SSE MCP Bridge on 0.0.0.0:8080
2025-01-26 22:35:27 - frappe_assistant_core.services.sse_bridge - DEBUG - Authorization header: Bearer abc123...
2025-01-26 22:35:27 - frappe_assistant_core.services.sse_bridge - INFO - SSE connection established: user_john_doe_12345678 for user: user_john_doe
```

## Production Environment

### Deployment Options

#### Option 1: Systemd Service (Recommended)

Create `/etc/systemd/system/frappe-sse-bridge.service`:
```ini
[Unit]
Description=Frappe Assistant Core SSE Bridge
After=network.target
Requires=network.target

[Service]
Type=simple
User=frappe
Group=frappe
WorkingDirectory=/path/to/frappe-bench
Environment=PATH=/path/to/frappe-bench/env/bin
Environment=HOST=0.0.0.0
Environment=PORT=8080
Environment=DEBUG=false
Environment=LOG_LEVEL=info
ExecStart=/path/to/frappe-bench/env/bin/python -c "from frappe_assistant_core.services.sse_bridge import main; main()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable frappe-sse-bridge
sudo systemctl start frappe-sse-bridge
sudo systemctl status frappe-sse-bridge
```

#### Option 2: Supervisor Configuration

Add to supervisor configuration:
```ini
[program:frappe-sse-bridge]
command=/path/to/frappe-bench/env/bin/python -c "from frappe_assistant_core.services.sse_bridge import main; main()"
directory=/path/to/frappe-bench
user=frappe
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/frappe/sse-bridge.log
environment=HOST="0.0.0.0",PORT="8080",DEBUG="false",LOG_LEVEL="info"
```

#### Option 3: Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN pip install .[sse-bridge]

EXPOSE 8080

ENV HOST=0.0.0.0
ENV PORT=8080
ENV DEBUG=false
ENV LOG_LEVEL=info

CMD ["python", "-c", "from frappe_assistant_core.services.sse_bridge import main; main()"]
```

### Production Configuration

```bash
# Environment variables for production
export HOST=0.0.0.0
export PORT=8080
export DEBUG=false
export LOG_LEVEL=info

# Optional: Configure API secret
export FRAPPE_API_SECRET=your_production_secret

# For high availability
export WORKER_CONNECTIONS=1000
export KEEP_ALIVE=2
```

### Load Balancing

For high-traffic deployments, run multiple instances:

```bash
# Instance 1
PORT=8080 python -c "from frappe_assistant_core.services.sse_bridge import main; main()" &

# Instance 2  
PORT=8081 python -c "from frappe_assistant_core.services.sse_bridge import main; main()" &

# Instance 3
PORT=8082 python -c "from frappe_assistant_core.services.sse_bridge import main; main()" &
```

Configure nginx load balancer:
```nginx
upstream sse_bridge {
    server localhost:8080;
    server localhost:8081;
    server localhost:8082;
}

server {
    listen 80;
    location / {
        proxy_pass http://sse_bridge;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SSE specific headers
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

### Monitoring in Production

#### Health Checks

```bash
# Basic health check
curl http://localhost:8080/health

# Response format
{
    "status": "healthy",
    "service": "frappe-assistant-core-sse-bridge", 
    "active_connections": 5,
    "pending_requests": 2
}
```

#### Log Monitoring

Monitor logs for production issues:
```bash
# Systemd logs
journalctl -u frappe-sse-bridge -f

# File logs (if configured)
tail -f /var/log/frappe/sse-bridge.log

# Key log patterns to monitor
grep "ERROR" /var/log/frappe/sse-bridge.log
grep "Connection.*closed" /var/log/frappe/sse-bridge.log
```

#### Metrics Collection

The health endpoint provides metrics for monitoring:
- `active_connections`: Current SSE connections
- `pending_requests`: Buffered requests waiting for connections
- Response time and error rates via external monitoring

## Usage Examples

### Basic Claude Integration

```python
# Claude MCP client configuration
{
    "mcpServers": {
        "frappe-assistant": {
            "command": "uv",
            "args": ["--directory", "/path/to/sse-bridge", "run", "python", "-m", "sse_mcp_bridge"],
            "env": {
                "SERVER_URL": "https://your-frappe-site.com",
                "API_KEY": "your-api-key",
                "API_SECRET": "your-api-secret"
            }
        }
    }
}
```

### Authentication Examples

#### Bearer Token Authentication
```bash
curl -H "Authorization: Bearer your-oauth-token" \
     "http://localhost:8080/mcp/sse?server_url=https://your-site.com"
```

#### API Key Authentication  
```bash
curl -H "Authorization: token your-api-key:your-api-secret" \
     "http://localhost:8080/mcp/sse?server_url=https://your-site.com"
```

### MCP Request Example

```json
POST /mcp/messages?session_id=user_john_doe_12345678
Content-Type: application/json
Authorization: Bearer your-token

{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
}
```

### SSE Stream Example

```javascript
// JavaScript client
const eventSource = new EventSource(
    'http://localhost:8080/mcp/sse?server_url=https://your-site.com',
    {
        headers: {
            'Authorization': 'Bearer your-token'
        }
    }
);

eventSource.addEventListener('endpoint', (event) => {
    console.log('Endpoint URL:', event.data);
});

eventSource.addEventListener('message', (event) => {
    const response = JSON.parse(event.data);
    console.log('MCP Response:', response);
});

eventSource.addEventListener('ping', (event) => {
    const ping = JSON.parse(event.data);
    console.log('Ping:', ping.counter, 'Active connections:', ping.active_connections);
});
```

## Troubleshooting

### Common Issues

#### 1. Port Conflicts
**Problem**: `[Errno 48] address already in use`
**Solution**: 
```bash
# Check what's using the port
lsof -i :8080

# Use a different port
PORT=8081 python -c "from frappe_assistant_core.services.sse_bridge import main; main()"
```

#### 2. Import Errors
**Problem**: `ModuleNotFoundError: No module named 'fastapi'`
**Solution**:
```bash
# Install SSE bridge dependencies
pip install frappe_assistant_core[sse-bridge]
```

#### 3. Authentication Failures
**Problem**: `401 Invalid or missing authorization token`
**Solutions**:
```bash
# Check Bearer token format
curl -H "Authorization: Bearer your-actual-token" ...

# Check API key format  
curl -H "Authorization: token key:secret" ...

# Verify Frappe server is accessible
curl https://your-site.com/api/method/frappe.auth.get_logged_user
```

#### 4. Connection Issues
**Problem**: SSE connections dropping frequently
**Solutions**:
- Check network stability
- Verify nginx/proxy configuration doesn't buffer SSE
- Monitor server resources (memory, CPU)
- Check firewall settings

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Development
DEBUG=true LOG_LEVEL=debug python -c "from frappe_assistant_core.services.sse_bridge import main; main()"

# Production - temporary debugging
export DEBUG=true
export LOG_LEVEL=debug
systemctl restart frappe-sse-bridge
```

Debug logs show detailed information:
```
DEBUG - Authorization header: Bearer abc123...
DEBUG - Sending to server https://site.com: {"jsonrpc": "2.0", "method": "ping"}
DEBUG - Received from server: {"jsonrpc": "2.0", "result": {...}}
```

### Performance Tuning

#### Connection Limits
Adjust connection limits based on usage:

```python
# In production, modify these values in sse_bridge.py
self.connection_grace_period = 10.0  # Increase for slow networks
self.max_idle_time = 600.0  # 10 minutes for longer sessions
```

#### Memory Usage
Monitor memory usage with many connections:
```bash
# Check memory usage
ps aux | grep sse_bridge
top -p $(pgrep -f sse_bridge)
```

#### Cleanup Frequency
Adjust cleanup intervals:
```python
# Modify cleanup frequency in sse_bridge.py
await asyncio.sleep(30)  # Run cleanup every 30 seconds instead of 10
```

## API Reference

### Endpoints

#### `GET /health`
Returns service health status and metrics.

**Response:**
```json
{
    "status": "healthy",
    "service": "frappe-assistant-core-sse-bridge",
    "active_connections": 5,
    "pending_requests": 2
}
```

#### `GET /mcp/sse`
Establishes SSE connection for MCP communication.

**Parameters:**
- `server_url` (query): Frappe server URL
- `Authorization` (header): Bearer token or API key

**Response:** SSE stream with events:
- `endpoint`: Provides message endpoint URL
- `message`: MCP response data
- `ping`: Connection keepalive
- `error`: Error information

#### `POST /mcp/messages`
Sends MCP requests through established SSE connection.

**Parameters:**
- `session_id` (query): Session ID from SSE endpoint event
- `Authorization` (header): Same as SSE connection

**Body:** JSON-RPC 2.0 MCP request

**Response:**
```json
{
    "status": "accepted"
}
```

### Authentication

Supports multiple authentication methods:

1. **Bearer Tokens** (OAuth2.0)
   ```
   Authorization: Bearer your-oauth-token
   ```

2. **API Keys** (Legacy)
   ```
   Authorization: token api-key:api-secret
   ```

### Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 400 | Invalid session ID | Session not found or expired |
| 401 | Invalid authorization | Authentication failed |
| 500 | Internal server error | Server-side processing error |

---

## Next Steps

After setting up the SSE Bridge:

1. **Configure Claude**: Update your Claude MCP configuration to use the SSE bridge
2. **Test Integration**: Verify MCP communication works end-to-end
3. **Monitor Performance**: Set up monitoring for production deployments
4. **Scale as Needed**: Deploy multiple instances for high availability

For additional help, refer to:
- [TECHNICAL_DOCUMENTATION.md](./TECHNICAL_DOCUMENTATION.md) - Deep technical details
- [API_REFERENCE.md](./API_REFERENCE.md) - Frappe Assistant Core API reference
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Overall system architecture

---

**Last Updated:** July 2025  
**Version:** 2.0.0  
**Maintainer:** Frappe Assistant Core Team