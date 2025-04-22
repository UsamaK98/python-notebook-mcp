"""
MIT License

Copyright (c) 2024 Usama Khatab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
\
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import os
import json
import base64
import nbformat
import sys
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from mcp.server.fastmcp import FastMCP, Context

# Set default workspace to current directory but don't consider it initialized
WORKSPACE_DIR = os.getcwd()
print(f"Default workspace directory (uninitialized): {WORKSPACE_DIR}")

# Flag to track if workspace has been explicitly set
WORKSPACE_INITIALIZED = False

# Create an MCP server
mcp = FastMCP("Jupyter Notebook MCP")


# Helper functions for converting Unix paths to Windows paths
def convert_unix_path(path: str) -> str:
    """Convert Unix-style paths like /d/Projects to Windows-style paths (only on Windows)."""
    # Only perform conversion on Windows
    if sys.platform != 'win32':
        return path
        
    import re
    # Match pattern like /d/Projects/... or /c/Users/...
    match = re.match(r'^/([a-zA-Z])(/.*)?$', path)
    if match:
        drive_letter = match.group(1)
        remaining_path = match.group(2) or ''
        # Convert to Windows path (D:\\Projects\\...)
        windows_path = remaining_path.replace('/', '\\')
        return f"{drive_letter.upper()}:{windows_path}"
    return path

def resolve_path(path: str) -> str:
    """Resolve relative paths against the workspace directory."""
    # Handle Unix-style paths like /d/Projects/...
    path = convert_unix_path(path)
    
    if os.path.isabs(path):
        return path
    
    # Try to resolve against the workspace directory
    resolved_path = os.path.join(WORKSPACE_DIR, path)
    return resolved_path

# Helper functions
def resolve_path(path: str) -> str:
    """Resolve relative paths against the workspace directory."""
    if os.path.isabs(path):
        return path
    
    # Try to resolve against the workspace directory
    resolved_path = os.path.join(WORKSPACE_DIR, path)
    return resolved_path

def get_notebook_content(filepath: str) -> dict:
    """Read a notebook file and return its content."""
    resolved_path = resolve_path(filepath)
    
    if not os.path.exists(resolved_path):
        raise FileNotFoundError(f"Notebook file not found: {resolved_path}")
    
    with open(resolved_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    return nb

def create_new_notebook(filepath: str, title: str = "New Notebook") -> dict:
    """Create a new notebook file if it doesn't exist."""
    resolved_path = resolve_path(filepath)
    
    # Create directory if it doesn't exist
    directory = os.path.dirname(resolved_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    # Create a new notebook
    nb = new_notebook()
    nb.cells.append(new_markdown_cell(f"# {title}"))
    nb.cells.append(new_code_cell("# Your code here"))
    
    # Write the notebook to file
    with open(resolved_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)
    
    print(f"Created new notebook at: {resolved_path}")
    return nb

def ensure_notebook_exists(filepath: str, title: str = "New Notebook") -> dict:
    """Ensure a notebook exists, creating it if necessary."""
    resolved_path = resolve_path(filepath)
    
    if not os.path.exists(resolved_path):
        return create_new_notebook(resolved_path, title)
    
    return get_notebook_content(resolved_path)

def notebook_to_dict(nb) -> Dict:
    """Convert notebook object to a safe dictionary representation."""
    result = {
        "cells": [],
        "metadata": dict(nb.metadata),
        "nbformat": nb.nbformat,
        "nbformat_minor": nb.nbformat_minor
    }
    
    for cell in nb.cells:
        cell_dict = {
            "cell_type": cell.cell_type,
            "source": cell.source,
            "metadata": dict(cell.metadata)
        }
        
        if cell.cell_type == 'code':
            cell_dict["execution_count"] = cell.execution_count
            cell_dict["outputs"] = []
            
            if hasattr(cell, 'outputs'):
                for output in cell.outputs:
                    output_dict = {"output_type": output.output_type}
                    
                    if output.output_type == 'stream':
                        output_dict["name"] = output.name
                        output_dict["text"] = output.text
                    elif output.output_type in ('execute_result', 'display_data'):
                        output_dict["data"] = {}
                        if hasattr(output, 'data'):
                            for key, value in output.data.items():
                                if key == 'image/png':
                                    output_dict["data"][key] = f"[Base64 encoded image: {len(value)} bytes]"
                                else:
                                    output_dict["data"][key] = value
                        if hasattr(output, 'metadata'):
                            output_dict["metadata"] = dict(output.metadata)
                        if hasattr(output, 'execution_count') and output.output_type == 'execute_result':
                            output_dict["execution_count"] = output.execution_count
                    elif output.output_type == 'error':
                        output_dict["ename"] = output.ename
                        output_dict["evalue"] = output.evalue
                        output_dict["traceback"] = output.traceback
                    
                    cell_dict["outputs"].append(output_dict)
        
        result["cells"].append(cell_dict)
    
    return result

def cell_to_dict(cell) -> Dict:
    """Convert cell object to a safe dictionary representation."""
    cell_dict = {
        "cell_type": cell.cell_type,
        "source": cell.source,
        "metadata": dict(cell.metadata)
    }
    
    if cell.cell_type == 'code':
        cell_dict["execution_count"] = cell.execution_count
        cell_dict["outputs"] = []
        
        if hasattr(cell, 'outputs'):
            for output in cell.outputs:
                output_dict = {"output_type": output.output_type}
                
                if output.output_type == 'stream':
                    output_dict["name"] = output.name
                    output_dict["text"] = output.text
                elif output.output_type in ('execute_result', 'display_data'):
                    output_dict["data"] = {}
                    if hasattr(output, 'data'):
                        for key, value in output.data.items():
                            if key == 'image/png':
                                output_dict["data"][key] = f"[Base64 encoded image: {len(value)} bytes]"
                            else:
                                output_dict["data"][key] = value
                    if hasattr(output, 'metadata'):
                        output_dict["metadata"] = dict(output.metadata)
                    if hasattr(output, 'execution_count') and output.output_type == 'execute_result':
                        output_dict["execution_count"] = output.execution_count
                elif output.output_type == 'error':
                    output_dict["ename"] = output.ename
                    output_dict["evalue"] = output.evalue
                    output_dict["traceback"] = output.traceback
                
                cell_dict["outputs"].append(output_dict)
    
    return cell_dict

def process_cell_output(output: Any) -> Dict:
    """Process a cell output and convert to a readable format."""
    if output.output_type == 'stream':
        return {
            'type': 'stream',
            'name': output.name,
            'text': output.text
        }
    elif output.output_type == 'execute_result':
        result = {
            'type': 'execute_result',
            'execution_count': output.execution_count,
            'data': {}
        }
        
        # Handle text/plain
        if 'text/plain' in output.data:
            result['data']['text/plain'] = output.data['text/plain']
        
        # Handle images
        if 'image/png' in output.data:
            image_data = output.data['image/png']
            result['data']['image/png'] = f"[Base64 encoded image: {len(image_data)} bytes]"
        
        return result
    elif output.output_type == 'display_data':
        result = {
            'type': 'display_data',
            'data': {}
        }
        
        # Handle text/plain
        if 'text/plain' in output.data:
            result['data']['text/plain'] = output.data['text/plain']
        
        # Handle images
        if 'image/png' in output.data:
            image_data = output.data['image/png']
            result['data']['image/png'] = f"[Base64 encoded image: {len(image_data)} bytes]"
        
        return result
    elif output.output_type == 'error':
        return {
            'type': 'error',
            'ename': output.ename,
            'evalue': output.evalue,
            'traceback': output.traceback
        }
    else:
        return {'type': output.output_type, 'data': str(output)}

# Tool implementations
@mcp.tool()
def initialize_workspace(directory: str) -> str:
    """
    IMPORTANT: Call this first! Initialize the workspace directory for this session.
    
    This must be called before using any other tools to ensure notebooks are created
    in the correct location. You must provide a FULL ABSOLUTE PATH to your project folder
    where notebooks should be stored. Do not use relative paths.
    
    Args:
        directory: The FULL ABSOLUTE PATH to set as the workspace (required)
        
    Returns:
        Confirmation message with list of any notebooks found
    
    Raises:
        ValueError: If directory is not provided, doesn't exist, is not a directory, or is a relative path
    """
    global WORKSPACE_DIR, WORKSPACE_INITIALIZED
    
    if not directory or not directory.strip():
        raise ValueError("ERROR: You must provide a directory path. Please provide the FULL ABSOLUTE PATH to your project directory where notebook files are located.")
    
    # Convert Unix-style paths to Windows format
    directory = convert_unix_path(directory)
    
    # Check for relative paths
    if directory in [".", "./"] or directory.startswith("./") or directory.startswith("../"):
        raise ValueError("ERROR: Relative paths like '.' or './' are not allowed. Please provide the FULL ABSOLUTE PATH to your project directory.")
    
    # Check if directory exists
    if not os.path.exists(directory):
        raise ValueError(f"ERROR: Directory does not exist: {directory}")
    
    # Check if it's a directory
    if not os.path.isdir(directory):
        raise ValueError(f"ERROR: Not a directory: {directory}")
    
    # Set the workspace directory
    WORKSPACE_DIR = directory
    WORKSPACE_INITIALIZED = True
    print(f"Workspace initialized at: {WORKSPACE_DIR}")
    
    # List the notebooks in the workspace to confirm
    notebooks = []
    for path in Path(WORKSPACE_DIR).rglob('*.ipynb'):
        notebooks.append(os.path.relpath(path, WORKSPACE_DIR))
    
    if notebooks:
        notebook_list = "\n- " + "\n- ".join(notebooks)
        return f"Workspace initialized at: {WORKSPACE_DIR}\nNotebooks found:{notebook_list}"
    else:
        return f"Workspace initialized at: {WORKSPACE_DIR}\nNo notebooks found."

def check_workspace_initialized() -> None:
    """Check if workspace is initialized and raise error if not."""
    if not WORKSPACE_INITIALIZED:
        raise ValueError("ERROR: Workspace not initialized. Please call initialize_workspace() first with the FULL ABSOLUTE PATH to the directory where your notebook files are located.")

@mcp.tool()
def list_notebooks(directory: str = ".") -> List[str]:
    """
    List all notebook files in the specified directory.
    
    Note: You must call initialize_workspace() first.
    """
    check_workspace_initialized()
    
    resolved_directory = resolve_path(directory)
    notebook_files = []
    
    for path in Path(resolved_directory).rglob('*.ipynb'):
        notebook_files.append(str(path))
    
    return notebook_files

@mcp.tool()
def create_notebook(filepath: str, title: str = "New Notebook") -> str:
    """
    Create a new Jupyter notebook.
    
    Note: You must call initialize_workspace() first with your project directory.
    
    Args:
        filepath: Path where the notebook should be created
        title: Title for the notebook (used in the first markdown cell)
    
    Returns:
        Path to the created notebook
    """
    check_workspace_initialized()
    
    resolved_path = resolve_path(filepath)
    
    if os.path.exists(resolved_path):
        return f"Notebook already exists at {resolved_path}"
    
    create_new_notebook(filepath, title)
    return f"Created notebook at {resolved_path}"

@mcp.tool()
def read_notebook(filepath: str) -> Dict:
    """
    Read the contents of a notebook.
    
    Note: You must call initialize_workspace() first with your project directory.
    
    Args:
        filepath: Path to the notebook file
    
    Returns:
        The notebook content
    """
    check_workspace_initialized()
    
    try:
        nb = get_notebook_content(filepath)
    except FileNotFoundError:
        nb = create_new_notebook(filepath)
    
    return notebook_to_dict(nb)

@mcp.tool()
def read_cell(filepath: str, cell_index: int) -> Dict:
    """
    Read a specific cell from a notebook.
    
    Note: You must call initialize_workspace() first with your project directory.
    
    Args:
        filepath: Path to the notebook file
        cell_index: Index of the cell to read
    
    Returns:
        The cell content
    """
    check_workspace_initialized()
    
    try:
        nb = get_notebook_content(filepath)
    except FileNotFoundError:
        nb = create_new_notebook(filepath)
    
    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(f"Cell index out of range: {cell_index}, notebook has {len(nb.cells)} cells")
    
    cell = nb.cells[cell_index]
    return cell_to_dict(cell)

@mcp.tool()
def edit_cell(filepath: str, cell_index: int, content: str) -> str:
    """
    Edit a specific cell in a notebook.
    
    Note: You must call initialize_workspace() first with your project directory.
    
    Args:
        filepath: Path to the notebook file
        cell_index: Index of the cell to edit
        content: New content for the cell
    
    Returns:
        Confirmation message
    """
    check_workspace_initialized()
    
    try:
        nb = get_notebook_content(filepath)
    except FileNotFoundError:
        nb = create_new_notebook(filepath)
    
    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(f"Cell index out of range: {cell_index}, notebook has {len(nb.cells)} cells")
    
    cell = nb.cells[cell_index]
    cell['source'] = content
    
    try:
        resolved_path = resolve_path(filepath)
        with open(resolved_path, 'w', encoding='utf-8') as f:
            nbformat.write(nb, f)
        return f"Updated cell {cell_index} in {resolved_path}"
    except Exception as e:
        raise Exception(f"Failed to update notebook: {str(e)}")

@mcp.tool()
def read_notebook_outputs(filepath: str) -> List[Dict]:
    """
    Read all outputs from a notebook.
    
    Note: You must call initialize_workspace() first with your project directory.
    
    Args:
        filepath: Path to the notebook file
    
    Returns:
        List of all cell outputs
    """
    check_workspace_initialized()
    
    try:
        nb = get_notebook_content(filepath)
    except FileNotFoundError:
        nb = create_new_notebook(filepath)
        return []  # New notebook has no outputs
    
    outputs = []
    
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == 'code' and hasattr(cell, 'outputs') and cell.outputs:
            cell_outputs = []
            for output in cell.outputs:
                cell_outputs.append(process_cell_output(output))
            
            outputs.append({
                'cell_index': i,
                'outputs': cell_outputs
            })
    
    return outputs

@mcp.tool()
def read_cell_output(filepath: str, cell_index: int) -> List[Dict]:
    """
    Read output from a specific cell.
    
    Note: You must call initialize_workspace() first with your project directory.
    
    Args:
        filepath: Path to the notebook file
        cell_index: Index of the cell
    
    Returns:
        The cell's output
    """
    check_workspace_initialized()
    
    try:
        nb = get_notebook_content(filepath)
    except FileNotFoundError:
        nb = create_new_notebook(filepath)
        return []  # New notebook has no outputs
    
    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(f"Cell index out of range: {cell_index}, notebook has {len(nb.cells)} cells")
    
    cell = nb.cells[cell_index]
    
    if cell.cell_type != 'code' or not hasattr(cell, 'outputs') or not cell.outputs:
        return []
    
    outputs = []
    for output in cell.outputs:
        outputs.append(process_cell_output(output))
    
    return outputs

@mcp.tool()
def add_cell(filepath: str, content: str, cell_type: str = "code", index: Optional[int] = None) -> str:
    """
    Add a new cell to a notebook.
    
    Note: You must call initialize_workspace() first with your project directory.
    
    Args:
        filepath: Path to the notebook file
        content: Content for the new cell
        cell_type: Type of cell ('code' or 'markdown')
        index: Position to insert the cell (None for append)
    
    Returns:
        Confirmation message
    """
    check_workspace_initialized()
    
    try:
        nb = get_notebook_content(filepath)
    except FileNotFoundError:
        nb = create_new_notebook(filepath)
    
    if cell_type.lower() == 'code':
        new_cell = new_code_cell(content)
    elif cell_type.lower() == 'markdown':
        new_cell = new_markdown_cell(content)
    else:
        raise ValueError(f"Invalid cell type: {cell_type}. Must be 'code' or 'markdown'")
    
    if index is None:
        nb.cells.append(new_cell)
        position = len(nb.cells) - 1
    else:
        if index < 0 or index > len(nb.cells):
            raise IndexError(f"Cell index out of range: {index}, notebook has {len(nb.cells)} cells")
        nb.cells.insert(index, new_cell)
        position = index
    
    try:
        resolved_path = resolve_path(filepath)
        with open(resolved_path, 'w', encoding='utf-8') as f:
            nbformat.write(nb, f)
        return f"Added {cell_type} cell at position {position} in {resolved_path}"
    except Exception as e:
        raise Exception(f"Failed to update notebook: {str(e)}")

# Main entry point
def main():
    """Start the MCP server."""
    print("Starting Notebook MCP Server...")
    print(f"Working directory: {os.getcwd()}")
    
    try:
        mcp.run()
    except AttributeError:
        # Fallback for different MCP versions
        try:
            mcp.start()
        except AttributeError:
            try:
                mcp.serve()
            except Exception as e:
                print(f"Error starting server with various methods: {str(e)}")
                sys.exit(1)
    except Exception as e:
        print(f"Error starting server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 