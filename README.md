<div align="center">
  <h1>Python Notebook MCP</h1>
  <p>MCP server enabling AI assistants to interact with Jupyter notebooks through the Model Context Protocol.</p>
  <p>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"/></a>
    <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+"/>
    <img src="https://img.shields.io/badge/MCP-Compatible-orange.svg" alt="MCP Compatible"/>
  </p>
</div>

This server allows compatible AI assistants (like Cursor or Claude Desktop) to interact with Jupyter Notebook files (.ipynb) on your local machine.

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python:** Version 3.10 or higher.
2.  **`uv`:** The fast Python package installer and virtual environment manager from Astral. If you don't have it, install it:
    ```bash
    # On macOS / Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # On Windows (PowerShell)
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

    # IMPORTANT: Add uv to your PATH if prompted by the installer
    # For macOS/Linux (bash/zsh), add to your ~/.zshrc or ~/.bashrc:
    # export PATH="$HOME/.local/bin:$PATH"
    # Then restart your shell or run `source ~/.zshrc` (or equivalent)
    ```
3.  **`fastmcp` CLI (Optional, for Claude Desktop `fastmcp install`):** If you plan to use the `fastmcp install` method for Claude Desktop, you need the `fastmcp` command available.
    ```bash
    # Using uv
    uv pip install fastmcp

    # Or using pipx (recommended for CLI tools)
    pipx install fastmcp
    ```

## 🔧 Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/UsamaK98/python-notebook-mcp.git # Or your fork/local path
    cd python-notebook-mcp
    ```

2.  **Choose Setup Method:**

    *   **Option A: Automated Setup (Recommended)**
        Run the appropriate script for your OS from the project's root directory (where you just `cd`-ed into).
        *   **macOS / Linux:**
            ```bash
            # Make script executable (if needed)
            chmod +x ./install_unix.sh
            # Run the script
            bash ./install_unix.sh
            ```
        *   **Windows (PowerShell):**
            ```powershell
            # You might need to adjust PowerShell execution policy first
            # Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
            .\install_windows.ps1
            ```
        These scripts will create the `.venv`, install dependencies, and output the exact paths needed for your MCP client configuration.

    *   **Option B: Manual Setup**
        Follow these steps if you prefer manual control or encounter issues with the scripts.
        1.  **Create & Activate Virtual Environment:**
            ```bash
            # Create the environment (e.g., named .venv)
            uv venv

            # Activate the environment
            # On macOS/Linux (bash/zsh):
            source .venv/bin/activate
            # On Windows (Command Prompt):
            # .venv\Scripts\activate.bat
            # On Windows (PowerShell):
            # .venv\Scripts\Activate.ps1
            ```
            *(You should see `(.venv)` or similar at the start of your shell prompt)*
        2.  **Install Dependencies:**
            ```bash
            # Make sure your venv is active
            uv pip install -r requirements.txt
            ```

## ▶️ Running the Server

Make sure your virtual environment (`.venv`) is activated if you used manual setup.

### Method 1: Direct Execution (Recommended for Cursor, General Use)

This method uses `uv run` to execute the server script directly using your current Python environment (which should now have the dependencies installed).

1.  **Run the Server:**
    ```bash
    # From the python-notebook-mcp directory
    uv run python server.py
    ```
    The server will start and print status messages, including the (uninitialized) workspace directory.

2.  **Client Configuration (`mcp.json`):** Configure your MCP client (e.g., Cursor) to connect. Create or edit the client's MCP configuration file (e.g., `.cursor/mcp.json` in your workspace).

    **Template (Recommended):**
    ```json
    {
      "mcpServers": {
        "jupyter": {
          // Use the absolute path to the Python executable inside your .venv
          "command": "/full/absolute/path/to/python-notebook-mcp/.venv/bin/python", // macOS/Linux
          // "command": "C:\\full\\absolute\\path\\to\\python-notebook-mcp\\.venv\\Scripts\\python.exe", // Windows
          "args": [
              // Absolute path to the server script
              "/full/absolute/path/to/python-notebook-mcp/server.py"
            ],
          "autoApprove": ["initialize_workspace"] // Optional: Auto-approve certain safe tools
        }
      }
    }
    ```
    > **❓ Why the full path to Python?** GUI applications like Cursor might not inherit the same `PATH` environment as your terminal. Specifying the exact path to the Python interpreter inside your `.venv` ensures the server runs with the correct environment and dependencies.
    > **⚠️ IMPORTANT:** Replace the placeholder paths with the actual **absolute paths** on your system.

### Method 2: Claude Desktop Integration (`fastmcp install`)

This method uses the `fastmcp` tool to create a dedicated, isolated environment for the server and register it with Claude Desktop. You generally don't need to activate the `.venv` manually for this method, as `fastmcp install` handles environment creation.

1.  **Install the Server for Claude:**
    ```bash
    # From the python-notebook-mcp directory
    fastmcp install server.py --name "Jupyter Notebook MCP"
    ```
    *   `fastmcp install` uses `uv` behind the scenes to create the environment and install dependencies from `requirements.txt`.
    *   The server will now appear in the Claude Desktop developer settings and can be enabled there. You generally *don't* need to manually edit `claude_desktop_config.json` when using `fastmcp install`.

## 📘 Usage

### Key Concept: Workspace Initialization

Regardless of how you run the server, the **first action** you *must* take from your AI assistant is to initialize the workspace. This tells the server where your project files and notebooks are located.

```python
# Example tool call from the client (syntax may vary)
initialize_workspace(directory="/full/absolute/path/to/your/project_folder")
```

> ⚠️ You **must** provide the full **absolute path** to the directory containing your notebooks. Relative paths or paths like `.` are not accepted. The server will confirm the path and list any existing notebooks found.

### Core Operations

Once the workspace is initialized, you can use the available tools:

```python
# List notebooks
list_notebooks()

# Create a new notebook
create_notebook(filepath="analysis/new_analysis.ipynb", title="My New Analysis")

# Add a code cell to the notebook
add_cell(filepath="analysis/new_analysis.ipynb", content="import pandas as pd\ndf = pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]})\ndf.head()", cell_type="code")

# Read the first cell (index 0)
read_cell(filepath="analysis/new_analysis.ipynb", cell_index=0)

# Edit the second cell (index 1)
edit_cell(filepath="analysis/new_analysis.ipynb", cell_index=1, content="# This is updated markdown")

# Read the output of the second cell (index 1) after execution (if any)
read_cell_output(filepath="analysis/new_analysis.ipynb", cell_index=1)

# Read the entire notebook structure
read_notebook(filepath="analysis/new_analysis.ipynb")
```

## 🛠️ Available Tools

| Tool                     | Description                                                        |
| :----------------------- | :----------------------------------------------------------------- |
| `initialize_workspace`   | **REQUIRED FIRST STEP.** Sets the absolute path for the workspace. |
| `list_notebooks`         | Lists all `.ipynb` files found within the workspace directory.     |
| `create_notebook`        | Creates a new, empty Jupyter notebook if it doesn't exist.       |
| `read_notebook`          | Reads the entire structure and content of a notebook.              |
| `read_cell`              | Reads the content and metadata of a specific cell by index.        |
| `edit_cell`              | Modifies the source content of an existing cell by index.          |
| `add_cell`               | Adds a new code or markdown cell at a specific index or the end. |
| `read_notebook_outputs`  | Reads all outputs from all code cells in a notebook.               |
| `read_cell_output`       | Reads the output(s) of a specific code cell by index.              |

## 🧪 Development & Debugging

If you need to debug the server itself:

*   **Run Directly:** Use `uv run python server.py` and observe the terminal output for errors or print statements.
*   **FastMCP Dev Mode:** For interactive testing with the MCP Inspector:
    ```bash
    # Make sure fastmcp is installed in your environment
    # uv pip install fastmcp
    uv run fastmcp dev server.py
    ```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 