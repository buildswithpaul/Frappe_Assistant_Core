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
    uvicorn sse_mcp_bridge:app --host $HOST --port 8080 --log-level info
fi
