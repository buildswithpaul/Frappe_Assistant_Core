#!/bin/bash

# SSE MCP Bridge Setup and Start Script
# This script sets up a virtual environment, installs dependencies, and starts the server

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="sse-mcp-bridge"
VENV_NAME="venv"
PYTHON_VERSION="python3"
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="8000"

echo -e "${BLUE}🚀 SSE MCP Bridge Setup Script${NC}"
echo "=================================="

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Python is installed and get version
if ! command -v $PYTHON_VERSION &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.8+ and try again."
    exit 1
fi

PYTHON_VERSION_FULL=$($PYTHON_VERSION --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION_FULL | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION_FULL | cut -d'.' -f2)

print_status "Python found: Python $PYTHON_VERSION_FULL"

# Check Python version compatibility
if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 13 ]; then
    print_warning "Python 3.13+ detected. Some packages may have compatibility issues."
    print_info "If you encounter build errors, consider using Python 3.11 or 3.12"
    print_info "You can install Python 3.12 with: brew install python@3.12 (on macOS)"
    echo ""
fi

# Create project directory
if [ ! -d "$PROJECT_NAME" ]; then
    print_info "Creating project directory: $PROJECT_NAME"
    mkdir "$PROJECT_NAME"
fi

cd "$PROJECT_NAME"

# Create virtual environment
if [ ! -d "$VENV_NAME" ]; then
    print_info "Creating virtual environment..."
    $PYTHON_VERSION -m venv $VENV_NAME
    print_status "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source $VENV_NAME/bin/activate

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip

# Create requirements.txt if it doesn't exist
if [ ! -f "requirements.txt" ]; then
    print_info "Creating requirements.txt..."
    cat > requirements.txt << EOF
# FastAPI and server dependencies
fastapi==0.115.6
uvicorn[standard]==0.32.1
python-multipart==0.0.12

# HTTP client for Frappe API calls
httpx==0.28.1

# Type hints and validation (Python 3.13 compatible)
pydantic==2.10.4
typing-extensions==4.12.2

# Environment and configuration
python-dotenv==1.0.1

# Optional: Production server
# gunicorn==23.0.0

# Optional: Development tools  
# pytest==8.3.4
# pytest-asyncio==0.24.0
EOF
    print_status "requirements.txt created"
fi

# Create minimal requirements as fallback
if [ ! -f "requirements-minimal.txt" ]; then
    print_info "Creating requirements-minimal.txt (fallback)..."
    cat > requirements-minimal.txt << EOF
# Minimal requirements for Python 3.13 compatibility
fastapi>=0.100.0
uvicorn>=0.20.0
httpx>=0.25.0
python-dotenv>=1.0.0
EOF
    print_status "requirements-minimal.txt created"
fi

# Install dependencies
print_info "Installing dependencies from requirements.txt..."
if pip install -r requirements.txt; then
    print_status "Dependencies installed successfully"
else
    print_warning "Main requirements installation failed. Trying minimal installation..."
    if pip install -r requirements-minimal.txt; then
        print_status "Minimal dependencies installed successfully"
        print_warning "Note: Some optional features may not be available"
    else
        print_error "Failed to install dependencies"
        print_info "Manual installation options for Python 3.13:"
        echo ""
        echo "Option 1 - Use Python 3.12:"
        echo "  brew install python@3.12  # macOS"
        echo "  python3.12 -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install fastapi uvicorn httpx python-dotenv"
        echo ""
        echo "Option 2 - Install without pydantic:"
        echo "  pip install fastapi uvicorn httpx python-dotenv"
        echo "  # Then modify the bridge code to not use pydantic models"
        echo ""
        echo "Option 3 - Try installing without building wheels:"
        echo "  pip install --only-binary=:all: fastapi uvicorn httpx python-dotenv"
        exit 1
    fi
fi

# Create the SSE bridge file if it doesn't exist
if [ ! -f "sse_mcp_bridge.py" ]; then
    print_warning "sse_mcp_bridge.py not found. Please add the SSE bridge code to this file."
    print_info "You can copy the code from the artifact and save it as sse_mcp_bridge.py"
    
    # Create a placeholder file with import check
    cat > sse_mcp_bridge.py << 'EOF'
"""
SSE MCP Bridge for Frappe
Please replace this file with the actual SSE bridge code from the artifact.
"""

def main():
    print("Please add the SSE bridge code to this file (sse_mcp_bridge.py)")
    print("You can find the code in the provided artifact.")
    exit(1)

if __name__ == "__main__":
    main()
EOF
fi

# Create .env file for configuration
if [ ! -f ".env" ]; then
    print_info "Creating .env configuration file..."
    cat > .env << EOF
# SSE MCP Bridge Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Optional: Set log level
# LOG_LEVEL=info
EOF
    print_status ".env file created"
fi

# Create a start script
print_info "Creating start script..."
cat > start_server.sh << 'EOF'
#!/bin/bash

# Start SSE MCP Bridge Server
# Make sure virtual environment is activated

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if we're in virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    print_info "Activating virtual environment..."
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        echo "Virtual environment not found. Run setup.sh first."
        exit 1
    fi
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Get configuration
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8080}
DEBUG=${DEBUG:-false}

print_status "Starting SSE MCP Bridge..."
print_info "Host: $HOST"
print_info "Port: $PORT"
print_info "Debug: $DEBUG"
print_info "Access the server at: http://$HOST:$PORT"
print_info "Health check: http://$HOST:$PORT/health"
echo ""
print_info "Press Ctrl+C to stop the server"
echo ""

# Start the server
if [ "$DEBUG" = "true" ]; then
    uvicorn sse_mcp_bridge:app --host $HOST --port $PORT --reload --log-level debug
else
    uvicorn sse_mcp_bridge:app --host $HOST --port $PORT --log-level info
fi
EOF

chmod +x start_server.sh

# Create a test script
print_info "Creating test script..."
cat > test_bridge.py << 'EOF'
#!/usr/bin/env python3
"""
Test script for SSE MCP Bridge
"""

import asyncio
import httpx
import json
import os
from typing import Optional

async def test_health_check(base_url: str):
    """Test the health check endpoint"""
    print("🔍 Testing health check...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("✅ Health check passed")
                print(f"   Response: {response.json()}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

async def test_mcp_request(base_url: str, server_url: str, token: Optional[str] = None):
    """Test an MCP request"""
    print("🔍 Testing MCP request...")
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    request_data = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/mcp/request",
                params={"server_url": server_url},
                headers=headers,
                json=request_data,
                timeout=10.0
            )
            
            if response.status_code == 200:
                print("✅ MCP request test passed")
                result = response.json()
                print(f"   Response: {json.dumps(result, indent=2)}")
                return True
            else:
                print(f"❌ MCP request failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ MCP request error: {e}")
            return False

async def test_sse_stream(base_url: str, server_url: str, token: Optional[str] = None):
    """Test SSE stream (basic connection)"""
    print("🔍 Testing SSE stream connection...")
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "GET",
                f"{base_url}/mcp/sse",
                params={"server_url": server_url},
                headers=headers,
                timeout=5.0
            ) as response:
                
                if response.status_code == 200:
                    print("✅ SSE connection established")
                    
                    # Read first few lines
                    lines_read = 0
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            print(f"   Received: {line}")
                            lines_read += 1
                            if lines_read >= 2:  # Read a couple of messages
                                break
                    
                    return True
                else:
                    print(f"❌ SSE connection failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ SSE connection error: {e}")
            return False

async def main():
    """Run all tests"""
    print("🧪 SSE MCP Bridge Test Suite")
    print("=" * 40)
    
    # Configuration
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    server_url = os.environ.get("FRAPPE_SERVER_URL", "https://erptest.promantia.in")
    token = os.environ.get("OAUTH_TOKEN")  # Optional for testing
    
    print(f"Base URL: {base_url}")
    print(f"Frappe Server URL: {server_url}")
    print(f"OAuth Token: {'Provided' if token else 'Not provided (some tests may fail)'}")
    print()
    
    # Run tests
    tests = [
        test_health_check(base_url),
        test_mcp_request(base_url, server_url, token),
        test_sse_stream(base_url, server_url, token),
    ]
    
    results = await asyncio.gather(*tests, return_exceptions=True)
    
    # Summary
    print("\n📊 Test Summary")
    print("-" * 20)
    passed = sum(1 for r in results if r is True)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the output above.")
        
    return passed == total

if __name__ == "__main__":
    # Example usage:
    # python test_bridge.py
    # 
    # With custom configuration:
    # BASE_URL=http://localhost:8000 FRAPPE_SERVER_URL=https://your-frappe.com OAUTH_TOKEN=your_token python test_bridge.py
    
    asyncio.run(main())
EOF

chmod +x test_bridge.py

# Create a usage guide
print_info "Creating usage guide..."
cat > USAGE.md << 'EOF'
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
EOF

print_status "Setup completed successfully!"
echo ""
print_info "Next Steps:"
echo "1. Add your SSE bridge code to: sse_mcp_bridge.py"
echo "2. Run: ./start_server.sh"
echo "3. Test: python test_bridge.py"
echo "4. Read: USAGE.md for detailed instructions"
echo ""
print_info "Server will be available at: http://localhost:8000"
print_info "Health check: http://localhost:8000/health"