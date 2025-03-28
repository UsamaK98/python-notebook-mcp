# Python Notebook MCP

An MCP server for interacting with Jupyter notebooks from Claude and other MCP clients.

## Features

- Read notebook contents and individual cells
- Edit cells
- View cell outputs including images
- Add new cells
- Set custom workspace directory

## How It Works

This MCP server uses a workspace-based approach to resolve relative paths. When the server starts, it defaults to the current working directory. To ensure notebooks are created in the right location, use the `set_workspace` tool first to point to your project directory.

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python server.py
```

## Configuration & Usage

### Setting the Workspace

When using this MCP server, always start by setting the workspace to your project directory:

```
set_workspace("/path/to/your/project")
```

This will ensure all subsequent operations use the correct paths and create notebooks in your project directory rather than in the client's directory.

### Claude Desktop Configuration

To configure this MCP server for Claude Desktop:

1. Open Claude Desktop
2. Go to Settings → Tools → Add Tool → Local Tool
3. Fill in the form:
   - Name: Jupyter Notebook
   - Description: Work with Jupyter notebooks
   - Command: `python`
   - Arguments: `path/to/server.py`
   - Working Directory: Path to where server.py is located

For the configuration file in Claude Desktop (usually located at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "python",
      "args": ["path/to/server.py"],
      "disabled": false,
      "autoApprove": ["set_workspace", "get_workspace", "list_notebooks"]
    }
  }
}
```

The `autoApprove` field allows specified tools to run without user confirmation, which is helpful for workspace setup.

### Cursor IDE Configuration

For Cursor IDE, add this to your configuration file (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "python",
      "args": ["path/to/server.py"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

When using Cursor, you should still call `set_workspace` with your project path, as Cursor might run the MCP server from its installation directory.

### Windsurf IDE Configuration

For Windsurf IDE, add this to your configuration:

```json
{
  "tools": [
    {
      "name": "Python Notebook MCP",
      "type": "mcp",
      "command": "python path/to/server.py",
      "workingDir": "${workspaceFolder}"
    }
  ]
}
```

## Available Tools

- `set_workspace`: Set the workspace directory for resolving relative paths
- `get_workspace`: Get the current workspace directory
- `list_notebooks`: List all notebook files in a directory
- `read_notebook`: Read the contents of a notebook
- `read_cell`: Read a specific cell from a notebook
- `edit_cell`: Edit a specific cell in a notebook
- `read_notebook_outputs`: Read all outputs from a notebook
- `read_cell_output`: Read output from a specific cell
- `add_cell`: Add a new cell to a notebook

## Usage Examples

Set workspace:
```
set_workspace("/path/to/your/project")
```

Create or open a notebook:
```
# The notebook will be created if it doesn't exist
read_notebook("my_notebook.ipynb")
```

Add a new cell:
```
add_cell("my_notebook.ipynb", "print('Hello, world!')", "code")
```

Read a cell:
```
read_cell("my_notebook.ipynb", 0)
```

Edit a cell:
```
edit_cell("my_notebook.ipynb", 0, "# This is an updated cell")
```

## Troubleshooting

If notebooks are being created in the wrong directory:

1. Check where the server is running by using `get_workspace()`
2. Use `set_workspace()` to explicitly set the correct directory
3. Use absolute paths when creating notebooks if needed
4. Restart the server if necessary 