# Basic setup script for Python Notebook MCP on Windows (PowerShell)

# Check for uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Error: 'uv' command not found. Please install uv first:"
    Write-Host "  powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""
    Write-Host "Make sure uv is added to your system PATH environment variable."
    exit 1
}

# Create virtual environment
Write-Host "Creating virtual environment (.venv)..."
uv venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to create virtual environment."
    exit 1
}

# Install dependencies into the virtual environment
Write-Host "Installing dependencies from requirements.txt into .venv..."
# We use the python from the venv explicitly to be sure
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Alternative using uv directly (should also work if uv detects .venv):
# uv pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to install dependencies."
    exit 1
}

$PythonPath = Join-Path $pwd.Path ".venv\Scripts\python.exe"
$ServerPath = Join-Path $pwd.Path "server.py"

Write-Host ""
Write-Host "Setup successful!"
Write-Host ""
Write-Host "To configure your MCP client (e.g., Cursor's .cursor/mcp.json), use the following paths:"
Write-Host "  Python Executable ('command'): $PythonPath"
Write-Host "  Server Script ('args'):        $ServerPath"
Write-Host ""
Write-Host "Example mcp.json entry (remember to escape backslashes):"
Write-Host "{
  `"mcpServers`": {
    `"jupyter`": {
      `"command`": `"$($PythonPath -replace '\\', '\\')`",
      `"args`": [`"$($ServerPath -replace '\\', '\\')`"]
    }
  }
}" 