#!/bin/bash

# ngrok Setup and Usage Guide for SSE MCP Bridge
# This script helps you expose your localhost SSE bridge to the internet

echo "🌐 ngrok Setup Guide for SSE MCP Bridge"
echo "======================================"

# Check if ngrok is installed
if command -v ngrok &> /dev/null; then
    echo "✅ ngrok is already installed"
    ngrok version
else
    echo "📦 Installing ngrok..."
    
    # Detect OS and install accordingly
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            echo "Installing via Homebrew..."
            brew install ngrok/ngrok/ngrok
        else
            echo "Please install Homebrew first or download ngrok manually from https://ngrok.com/download"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        echo "Installing for Linux..."
        curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
        echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
        sudo apt update && sudo apt install ngrok
    else
        echo "Please download ngrok manually from https://ngrok.com/download"
        exit 1
    fi
fi

echo ""
echo "🔑 ngrok Authentication Setup"
echo "1. Go to https://dashboard.ngrok.com/signup"
echo "2. Sign up for a free account"
echo "3. Go to https://dashboard.ngrok.com/get-started/your-authtoken"
echo "4. Copy your authtoken"
echo "5. Run: ngrok config add-authtoken YOUR_AUTHTOKEN"
echo ""

read -p "Have you set up your ngrok authtoken? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please set up your authtoken first, then run this script again."
    exit 1
fi

echo "✅ Great! Now let's expose your SSE bridge..."
echo ""

# Function to start ngrok tunnel
start_tunnel() {
    local port=${1:-8080}
    echo "🚀 Starting ngrok tunnel for port $port..."
    echo "Press Ctrl+C to stop the tunnel"
    echo ""
    
    # Start ngrok tunnel
    ngrok http $port --log=stdout
}

# Check if SSE bridge is running
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ SSE bridge is running on localhost:8080"
    echo ""
    echo "Starting ngrok tunnel..."
    start_tunnel 8080
else
    echo "❌ SSE bridge is not running on localhost:8080"
    echo ""
    echo "Please start your SSE bridge first:"
    echo "  cd sse-mcp-bridge"
    echo "  ./start_server.sh"
    echo ""
    echo "Then run this script again."
fi