# SSE Bridge Quick Reference

## 🚀 Quick Start

### Install Dependencies
```bash
pip install frappe_assistant_core[sse-bridge]
```

### Start with Bench
```bash
bench start  # SSE bridge runs automatically on port 8080
```

### Health Check
```bash
curl http://localhost:8080/health
```

## 📋 Configuration

### Environment Variables
```bash
export HOST=0.0.0.0      # Server address
export PORT=8080         # Server port (avoid 8000)
export DEBUG=false       # Debug mode
export LOG_LEVEL=info    # Logging level
```

### Development (.env file)
```env
HOST=0.0.0.0
PORT=8080
DEBUG=true
LOG_LEVEL=debug
FRAPPE_API_SECRET=your_secret
```

## 🔧 Manual Operations

### Start Manually
```bash
python -c "from frappe_assistant_core.services.sse_bridge import main; main()"
```

### Test Module Import
```bash
python -c "from frappe_assistant_core.services.sse_bridge import create_app; print('✅ Ready!')"
```

### Start with Uvicorn
```bash
uvicorn frappe_assistant_core.services.sse_bridge:create_app --factory --host 0.0.0.0 --port 8080
```

## 🏗️ Production Deployment

### Systemd Service
```ini
[Unit]
Description=Frappe SSE Bridge
After=network.target

[Service]
Type=simple
User=frappe
WorkingDirectory=/path/to/frappe-bench
Environment=HOST=0.0.0.0
Environment=PORT=8080
Environment=DEBUG=false
ExecStart=/path/to/frappe-bench/env/bin/python -c "from frappe_assistant_core.services.sse_bridge import main; main()"
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install .[sse-bridge]
EXPOSE 8080
ENV HOST=0.0.0.0 PORT=8080 DEBUG=false
CMD ["python", "-c", "from frappe_assistant_core.services.sse_bridge import main; main()"]
```

## 🔐 Authentication

### Bearer Token
```bash
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8080/mcp/sse?server_url=https://your-site.com"
```

### API Key
```bash
curl -H "Authorization: token api-key:api-secret" \
  "http://localhost:8080/mcp/sse?server_url=https://your-site.com"
```

## 🛠️ Troubleshooting

### Common Issues

**Port in use:**
```bash
lsof -i :8080                    # Check what's using port
PORT=8081 bench start sse_bridge # Use different port
```

**Module not found:**
```bash
pip install frappe_assistant_core[sse-bridge]  # Install dependencies
```

**Authentication failed:**
```bash
# Check token format and server accessibility
curl https://your-site.com/api/method/frappe.auth.get_logged_user
```

**Debug mode:**
```bash
DEBUG=true LOG_LEVEL=debug python -c "from frappe_assistant_core.services.sse_bridge import main; main()"
```

## 📊 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Service health and metrics |
| `/mcp/sse` | GET | Establish SSE connection |
| `/mcp/messages` | POST | Send MCP requests |

## 🔍 Monitoring

### Health Response
```json
{
  "status": "healthy",
  "service": "frappe-assistant-core-sse-bridge", 
  "active_connections": 5,
  "pending_requests": 2
}
```

### Log Monitoring
```bash
# Development
tail -f logs/sse-bridge.log

# Production (systemd)
journalctl -u frappe-sse-bridge -f

# Production (supervisor)
tail -f /var/log/frappe/sse-bridge.log
```

## 📁 File Locations

```
frappe_assistant_core/
├── services/
│   ├── __init__.py
│   ├── __main__.py
│   └── sse_bridge.py          # Main SSE bridge service
├── pyproject.toml             # Dependencies: [sse-bridge]
└── docs/
    ├── SSE_BRIDGE_INTEGRATION.md    # Complete guide
    └── SSE_BRIDGE_QUICK_REFERENCE.md # This file
```

## 🔗 Related Documentation

- **[Complete SSE Bridge Guide](SSE_BRIDGE_INTEGRATION.md)** - Full documentation
- **[Technical Documentation](TECHNICAL_DOCUMENTATION.md)** - Architecture details
- **[API Reference](API_REFERENCE.md)** - Frappe Assistant Core APIs

---

**Need help?** See the [complete documentation](SSE_BRIDGE_INTEGRATION.md) or contact [jypaulclinton@gmail.com](mailto:jypaulclinton@gmail.com)