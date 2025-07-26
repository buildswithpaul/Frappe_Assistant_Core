# SSE MCP Bridge Usage Guide

## Quick Start

1. **Setup and Start Server**:
   ```bash
   ./setup.sh
   ```

2. **Start the Server**:
   ```bash
   ./start_server.sh
   ```

3. **Test the Server**:
   ```bash
   python test_bridge.py
   ```

## Manual Setup

If you prefer to set up manually:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn sse_mcp_bridge:app --host 0.0.0.0 --port 8000
```

## Configuration

Edit `.env` file to configure:

```bash
HOST=0.0.0.0        # Server host
PORT=8000           # Server port  
DEBUG=false         # Debug mode
```

## Using with Claude API

```javascript
const response = await anthropic.beta.messages.create({
  model: "claude-sonnet-4-20250514",
  messages: [{ role: "user", content: "Get my sales data" }],
  mcp_servers: [{
    type: "url",
    url: "https://your-bridge.com/mcp/sse?server_url=https://your-frappe.com",
    name: "frappe-erp",
    authorization_token: "YOUR_FRAPPE_OAUTH_TOKEN"
  }],
  betas: ["mcp-client-2025-04-04"]
});
```

## Testing Endpoints

**Health Check**:
```bash
curl http://localhost:8000/health
```

**MCP Request**:
```bash
curl -X POST "http://localhost:8000/mcp/request?server_url=https://your-frappe.com" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1}'
```

**SSE Stream**:
```bash
curl "http://localhost:8000/mcp/sse?server_url=https://your-frappe.com" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Deployment

For production deployment:

1. **Use a production WSGI server**:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker sse_mcp_bridge:app
   ```

2. **Set up reverse proxy** (nginx, Apache, etc.)

3. **Enable HTTPS** (required for Claude API)

4. **Set environment variables**:
   ```bash
   export HOST=0.0.0.0
   export PORT=8000
   export DEBUG=false
   ```

## Troubleshooting

**Port already in use**:
```bash
# Change port in .env file or:
PORT=8001 ./start_server.sh
```

**Virtual environment issues**:
```bash
# Delete and recreate:
rm -rf venv
./setup.sh
```

**Connection issues**:
- Check firewall settings
- Ensure Frappe server is accessible
- Verify OAuth tokens are valid

## Development

**Enable debug mode**:
```bash
echo "DEBUG=true" >> .env
./start_server.sh
```

**Install additional dependencies**:
```bash
source venv/bin/activate
pip install your-package
pip freeze > requirements.txt
```
