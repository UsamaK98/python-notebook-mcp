#!/bin/bash

# Basic setup script for Python Notebook MCP on macOS/Linux

# Check for uv
if ! command -v uv &> /dev/null
then
    echo "Error: 'uv' command not found. Please install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Make sure uv is added to your PATH (e.g., in ~/.zshrc or ~/.bashrc)"
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment (.venv)..."
uv venv
if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment."
    exit 1
fi

# Install dependencies into the virtual environment
echo "Installing dependencies from requirements.txt into .venv..."
# We use the python from the venv explicitly to be sure
./.venv/bin/python -m pip install -r requirements.txt
# Alternative using uv directly (should also work if uv detects .venv):
# uv pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies."
    exit 1
fi

PYTHON_PATH="$(pwd)/.venv/bin/python"
SERVER_PATH="$(pwd)/server.py"

echo ""
echo "Setup successful!"
echo ""
echo "To configure your MCP client (e.g., Cursor's .cursor/mcp.json), use the following paths:"
echo "  Python Executable ('command'): $PYTHON_PATH"
echo "  Server Script ('args'):        $SERVER_PATH"
echo ""
echo "Example mcp.json entry:"
echo "{
  \"mcpServers\": {
    \"jupyter\": {
      \"command\": \"$PYTHON_PATH\",
      \"args\": [\"$SERVER_PATH\"]
    }
  }
}" 