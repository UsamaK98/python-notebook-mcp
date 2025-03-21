"""
Tool handlers for the Jupyter Notebook MCP server.
This file implements the functions for each tool defined in tool_definitions.py.
"""

import logging
import os
import nbformat
from typing import Dict, Any, List, Optional, Union
from notebook_manager import NotebookManager

# Initialize the notebook manager
notebook_manager = NotebookManager()
logger = logging.getLogger("tool_handlers")

def read_notebook(notebook_path: str, include_outputs: bool = True) -> Dict[str, Any]:
    """Read the contents of a Jupyter notebook"""
    try:
        notebook = notebook_manager.load_notebook(notebook_path)
        
        # Process cells
        cells = []
        for cell in notebook.cells:
            cell_data = {
                "id": cell.id,
                "type": cell.cell_type,
                "content": cell.source
            }
            
            # Include outputs if requested and this is a code cell
            if include_outputs and cell.cell_type == "code":
                outputs = []
                for output in cell.outputs:
                    if output.output_type == "stream":
                        outputs.append({"type": "stream", "text": output.text})
                    elif output.output_type == "execute_result":
                        if hasattr(output, "data") and "text/plain" in output.data:
                            outputs.append({"type": "result", "text": output.data["text/plain"]})
                    elif output.output_type == "display_data":
                        if hasattr(output, "data") and "text/plain" in output.data:
                            outputs.append({"type": "display", "text": output.data["text/plain"]})
                    elif output.output_type == "error":
                        outputs.append({"type": "error", "ename": output.ename, "evalue": output.evalue})
                
                cell_data["outputs"] = outputs
            
            cells.append(cell_data)
        
        # Extract metadata
        metadata = {}
        if hasattr(notebook, "metadata"):
            metadata = {
                "kernelspec": notebook.metadata.get("kernelspec", {}),
                "language_info": notebook.metadata.get("language_info", {})
            }
        
        return {
            "notebook_path": notebook_path,
            "cells": cells,
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Error reading notebook: {str(e)}")
        raise ValueError(f"Error reading notebook: {str(e)}")

def write_notebook(notebook_path: str, content: Dict[str, Any]) -> Dict[str, Any]:
    """Write content to a Jupyter notebook, replacing existing content"""
    try:
        # Create a new notebook object
        notebook = nbformat.v4.new_notebook()
        
        # Set metadata if provided
        if "metadata" in content:
            notebook.metadata.update(content["metadata"])
        
        # Add cells
        if "cells" in content:
            for cell_data in content["cells"]:
                cell_type = cell_data.get("type", "code")
                cell_content = cell_data.get("content", "")
                
                cell = nbformat.v4.new_cell(cell_type=cell_type, source=cell_content)
                
                # Set cell ID if provided
                if "id" in cell_data:
                    cell.id = cell_data["id"]
                
                notebook.cells.append(cell)
        
        # Save the notebook
        notebook_manager.save_notebook(notebook, notebook_path)
        
        return {
            "success": True,
            "message": f"Notebook saved to {notebook_path}",
            "notebook_path": notebook_path
        }
    except Exception as e:
        logger.error(f"Error writing notebook: {str(e)}")
        raise ValueError(f"Error writing notebook: {str(e)}")

def create_notebook(notebook_path: str, kernel_name: str = "python3") -> Dict[str, Any]:
    """Create a new Jupyter notebook"""
    try:
        notebook = notebook_manager.create_notebook(notebook_path, kernel_name)
        
        return {
            "success": True,
            "message": f"Created new notebook at {notebook_path}",
            "notebook_path": notebook_path,
            "kernel_name": kernel_name
        }
    except Exception as e:
        logger.error(f"Error creating notebook: {str(e)}")
        raise ValueError(f"Error creating notebook: {str(e)}")

def add_cell(notebook_path: str, cell_content: str, 
             cell_type: str = "code", position: int = -1) -> Dict[str, Any]:
    """Add a new cell to the notebook"""
    try:
        _, cell_id = notebook_manager.add_cell(notebook_path, cell_content, cell_type, position)
        
        return {
            "success": True,
            "message": f"Added {cell_type} cell at position {position if position >= 0 else 'end'}",
            "cell_id": cell_id,
            "notebook_path": notebook_path
        }
    except Exception as e:
        logger.error(f"Error adding cell: {str(e)}")
        raise ValueError(f"Error adding cell: {str(e)}")

def edit_cell(notebook_path: str, cell_id: str, new_content: str) -> Dict[str, Any]:
    """Edit the content of an existing cell"""
    try:
        notebook_manager.edit_cell(notebook_path, cell_id, new_content)
        
        return {
            "success": True,
            "message": f"Updated cell {cell_id}",
            "cell_id": cell_id,
            "notebook_path": notebook_path
        }
    except Exception as e:
        logger.error(f"Error editing cell: {str(e)}")
        raise ValueError(f"Error editing cell: {str(e)}")

def delete_cell(notebook_path: str, cell_id: str) -> Dict[str, Any]:
    """Delete a cell from the notebook"""
    try:
        notebook_manager.delete_cell(notebook_path, cell_id)
        
        return {
            "success": True,
            "message": f"Deleted cell {cell_id}",
            "notebook_path": notebook_path
        }
    except Exception as e:
        logger.error(f"Error deleting cell: {str(e)}")
        raise ValueError(f"Error deleting cell: {str(e)}")

def execute_cell(notebook_path: str, cell_id: str, timeout: int = 60) -> Dict[str, Any]:
    """Execute a specific cell and return its output"""
    try:
        result = notebook_manager.execute_cell(notebook_path, cell_id, timeout)
        
        return {
            "success": True,
            "cell_id": cell_id,
            "notebook_path": notebook_path,
            "outputs": result["outputs"]
        }
    except Exception as e:
        logger.error(f"Error executing cell: {str(e)}")
        raise ValueError(f"Error executing cell: {str(e)}")

def get_outputs(notebook_path: str, cell_id: str) -> Dict[str, Any]:
    """Get outputs from a specific cell"""
    try:
        outputs = notebook_manager.get_outputs(notebook_path, cell_id)
        
        return {
            "success": True,
            "cell_id": cell_id,
            "notebook_path": notebook_path,
            "outputs": outputs
        }
    except Exception as e:
        logger.error(f"Error getting outputs: {str(e)}")
        raise ValueError(f"Error getting outputs: {str(e)}")

def run_all_cells(notebook_path: str, timeout: int = 60) -> Dict[str, Any]:
    """Execute all cells in the notebook in sequence"""
    try:
        notebook = notebook_manager.execute_notebook(notebook_path, timeout)
        
        # Count successful and failed cells
        success_count = 0
        error_count = 0
        
        for cell in notebook.cells:
            if cell.cell_type != "code":
                continue
                
            has_error = False
            for output in cell.outputs:
                if output.output_type == "error":
                    has_error = True
                    error_count += 1
                    break
            
            if not has_error:
                success_count += 1
        
        return {
            "success": True,
            "notebook_path": notebook_path,
            "cells_executed": success_count + error_count,
            "successful_cells": success_count,
            "failed_cells": error_count
        }
    except Exception as e:
        logger.error(f"Error running all cells: {str(e)}")
        raise ValueError(f"Error running all cells: {str(e)}")

def undo_last_operation(notebook_path: str) -> Dict[str, Any]:
    """Undo the last operation on the notebook"""
    try:
        result = notebook_manager.undo_last_operation(notebook_path)
        
        return {
            "success": True,
            "message": "Last operation undone successfully",
            "notebook_path": notebook_path
        }
    except Exception as e:
        logger.error(f"Error undoing operation: {str(e)}")
        raise ValueError(f"Error undoing operation: {str(e)}")

def notebook_diff(notebook_path_a: str, notebook_path_b: str, 
                 include_outputs: bool = False) -> Dict[str, Any]:
    """Compare two notebooks and return their differences"""
    try:
        diff_result = notebook_manager.compare_notebooks(
            notebook_path_a, notebook_path_b, include_outputs
        )
        
        return {
            "success": True,
            "notebook_a": notebook_path_a,
            "notebook_b": notebook_path_b,
            "cell_count_diff": diff_result["cell_count_diff"],
            "differences": diff_result["differences"],
            "metadata_diff": diff_result["metadata_diff"],
            "total_differences": len(diff_result["differences"])
        }
    except Exception as e:
        logger.error(f"Error comparing notebooks: {str(e)}")
        raise ValueError(f"Error comparing notebooks: {str(e)}") 