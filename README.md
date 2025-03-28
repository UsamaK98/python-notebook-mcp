# Python Notebook MCP

An MCP server for interacting with Jupyter notebooks from Claude and other MCP clients. This tool allows you to create, read, edit, and manage Jupyter notebooks directly through AI assistants using the Model Context Protocol.

## Features

- Create new Jupyter notebooks
- Read notebook contents and individual cells
- Edit existing cells 
- Add new cells (code or markdown)
- View cell outputs including text, data, and images
- Set custom workspace directory

## Prerequisites

- Python 3.8+
- `fastmcp` Python package
- `nbformat` Python package

## Installation

1. Clone this repository:
```bash
git clone https://github.com/usamakhatab/python-notebook-mcp.git
cd python-notebook-mcp
```

2. Install dependencies:

Using pip:
```bash
pip install -r requirements.txt
```

Using uv (recommended for faster dependency resolution):
```bash
# Install uv if you don't have it
# Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# MacOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -r requirements.txt
```

## Running the Server

### Standard Mode

```bash
python server.py
```

### Development Mode (with FastMCP dev server)

For debugging and development:

```bash
# Using fastmcp directly
fastmcp dev server.py

# Using Python module
python -m fastmcp dev server.py

# Using uv with fastmcp
uv run fastmcp dev server.py
```

Development mode provides more verbose logging and automatic reloading on file changes.

## Usage

### Important: Setting the Workspace

When using this MCP server, **always start by initializing the workspace** with the `initialize_workspace` tool:

```
initialize_workspace("C:\\path\\to\\your\\project")
```

- You **must** provide the full absolute path to your project directory
- Relative paths like "." or "./" are not accepted
- This ensures all notebook operations use the correct location

### Core Operations

All operations below require calling `initialize_workspace` first:

**Create a new notebook:**
```
create_notebook("my_notebook.ipynb", "My Notebook Title")
```

**Read a notebook:**
```
read_notebook("my_notebook.ipynb")
```

**Add a new cell:**
```
add_cell("my_notebook.ipynb", "print('Hello, world!')", "code")
```

**Read a specific cell:**
```
read_cell("my_notebook.ipynb", 0)  # Read the first cell
```

**Edit a cell:**
```
edit_cell("my_notebook.ipynb", 0, "# This is an updated cell")
```

**View cell outputs:**
```
read_cell_output("my_notebook.ipynb", 1)  # Get outputs for the second cell
```

## Integration with AI Tools

### Claude Desktop

To configure this server for Claude Desktop:

1. Open Claude Desktop settings
2. Navigate to Developer options and edit the configuration file
3. Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "python",
      "args": ["C:\\full\\path\\to\\server.py"],
      "disabled": false,
      "autoApprove": ["initialize_workspace", "list_notebooks"]
    }
  }
}
```

### Cursor IDE

For Cursor IDE, create or edit `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "uv",
      "args": ["run", "--with", "fastmcp", "fastmcp", "run", "C:\\full\\path\\to\\server.py"]
    }
  }
}
```

If you don't have `uv` installed, you can use this simpler configuration:

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "python",
      "args": ["C:\\full\\path\\to\\server.py"]
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `initialize_workspace` | **MUST BE CALLED FIRST!** Set the workspace directory using a full absolute path |
| `list_notebooks` | List all notebook files in a directory |
| `create_notebook` | Create a new Jupyter notebook |
| `read_notebook` | Read the contents of a notebook |
| `read_cell` | Read a specific cell from a notebook |
| `edit_cell` | Edit a specific cell in a notebook |
| `read_notebook_outputs` | Read all outputs from a notebook |
| `read_cell_output` | Read output from a specific cell |
| `add_cell` | Add a new cell to a notebook |

## Development

### Creating a Virtual Environment

For development, it's recommended to use a virtual environment:

Using venv:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# MacOS/Linux
source venv/bin/activate
```

Using uv:
```bash
uv venv
# Windows
.venv\Scripts\activate
# MacOS/Linux
source .venv/bin/activate
```

### Debugging

1. Enable verbose logging by adding this at the top of `server.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. Run the server in development mode:
```bash
fastmcp dev server.py
```

3. Check the stdout for detailed logs about:
   - Tool registrations
   - Tool calls
   - Error messages
   - Connection status

## Troubleshooting

If you encounter issues:

1. **Wrong directory for notebooks:** Always use `initialize_workspace()` first with the full absolute path
2. **Server not connecting:** Check paths in your configuration file and ensure they are absolute
3. **"Already running asyncio in this thread" error:** Restart your terminal and try again
4. **Permissions issues:** Ensure the directory is writable
5. **Module not found errors:** Make sure all dependencies are installed correctly
6. **Connection issues:** Try running the server in development mode to see detailed logs

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 