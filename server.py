import os
import json
import base64
import nbformat
import sys
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from mcp.server.fastmcp import FastMCP, Context

# Set default workspace to current directory
WORKSPACE_DIR = os.getcwd()
print(f"Default workspace directory: {WORKSPACE_DIR}")

# Create an MCP server
mcp = FastMCP("Jupyter Notebook MCP")

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
        # Create an empty notebook if it doesn't exist
        directory = os.path.dirname(resolved_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        nb = new_notebook()
        nb.cells.append(new_markdown_cell("# New Notebook"))
        nb.cells.append(new_code_cell("# Your code here"))
        
        with open(resolved_path, 'w', encoding='utf-8') as f:
            nbformat.write(nb, f)
        print(f"Created new notebook at: {resolved_path}")
    
    with open(resolved_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    return nb

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
def set_workspace(directory: str) -> str:
    """
    Set the workspace directory for resolving relative paths.
    
    Args:
        directory: The directory to set as the workspace
        
    Returns:
        Confirmation message
    """
    global WORKSPACE_DIR
    
    # Check if directory exists
    if not os.path.exists(directory):
        raise ValueError(f"Directory does not exist: {directory}")
    
    # Check if it's a directory
    if not os.path.isdir(directory):
        raise ValueError(f"Not a directory: {directory}")
    
    # Set the workspace directory
    WORKSPACE_DIR = directory
    print(f"Workspace directory set to: {WORKSPACE_DIR}")
    return f"Workspace directory set to: {WORKSPACE_DIR}"

@mcp.tool()
def get_workspace() -> str:
    """
    Get the current workspace directory.
    
    Returns:
        The current workspace directory
    """
    return WORKSPACE_DIR

@mcp.tool()
def list_notebooks(directory: str = ".") -> List[str]:
    """List all notebook files in the specified directory."""
    resolved_directory = resolve_path(directory)
    notebook_files = []
    
    for path in Path(resolved_directory).rglob('*.ipynb'):
        notebook_files.append(str(path))
    
    return notebook_files

@mcp.tool()
def read_notebook(filepath: str) -> Dict:
    """
    Read the contents of a notebook.
    
    Args:
        filepath: Path to the notebook file
    
    Returns:
        The notebook content
    """
    nb = get_notebook_content(filepath)
    return notebook_to_dict(nb)

@mcp.tool()
def read_cell(filepath: str, cell_index: int) -> Dict:
    """
    Read a specific cell from a notebook.
    
    Args:
        filepath: Path to the notebook file
        cell_index: Index of the cell to read
    
    Returns:
        The cell content
    """
    nb = get_notebook_content(filepath)
    
    if cell_index < 0 or cell_index >= len(nb.cells):
        raise IndexError(f"Cell index out of range: {cell_index}, notebook has {len(nb.cells)} cells")
    
    cell = nb.cells[cell_index]
    return cell_to_dict(cell)

@mcp.tool()
def edit_cell(filepath: str, cell_index: int, content: str) -> str:
    """
    Edit a specific cell in a notebook.
    
    Args:
        filepath: Path to the notebook file
        cell_index: Index of the cell to edit
        content: New content for the cell
    
    Returns:
        Confirmation message
    """
    nb = get_notebook_content(filepath)
    
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
    
    Args:
        filepath: Path to the notebook file
    
    Returns:
        List of all cell outputs
    """
    nb = get_notebook_content(filepath)
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
    
    Args:
        filepath: Path to the notebook file
        cell_index: Index of the cell
    
    Returns:
        The cell's output
    """
    nb = get_notebook_content(filepath)
    
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
    
    Args:
        filepath: Path to the notebook file
        content: Content for the new cell
        cell_type: Type of cell ('code' or 'markdown')
        index: Position to insert the cell (None for append)
    
    Returns:
        Confirmation message
    """
    nb = get_notebook_content(filepath)
    
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
async def main():
    """Start the MCP server."""
    print("Starting Notebook MCP Server...")
    print(f"Working directory: {os.getcwd()}")
    
    try:
        await mcp.serve()
    except Exception as e:
        print(f"Error starting server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 