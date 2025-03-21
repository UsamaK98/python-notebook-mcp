"""
Notebook manager for MCP server.
Handles all core operations on Jupyter notebooks.
"""

import os
import json
import tempfile
import shutil
import logging
import nbformat
from nbclient import NotebookClient
from typing import Dict, Any, List, Optional, Tuple, Union
import uuid
import time
import fcntl

logger = logging.getLogger("notebook_manager")

# Output processors
OUTPUT_PROCESSORS = {
    "stream": lambda o: o.text,
    "execute_result": lambda o: o.data.get("text/plain", ""),
    "display_data": lambda o: o.data.get("text/plain", ""),
    "error": lambda o: f"{o.ename}: {o.evalue}"
}

class NotebookManager:
    def __init__(self, history_size=10):
        self.history = {}  # Dict to store operation history for each notebook
        self.history_size = history_size
        self.kernels = {}  # Dict to store active kernel sessions
    
    def _acquire_lock(self, notebook_path: str, timeout: int = 10) -> bool:
        """Acquire a lock on the notebook file to prevent concurrent modifications"""
        lock_path = f"{notebook_path}.lock"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                lock_file = open(lock_path, 'w')
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (IOError, OSError):
                # Someone else has the lock, wait and retry
                time.sleep(0.1)
        
        return False
    
    def _release_lock(self, notebook_path: str) -> None:
        """Release the lock on the notebook file"""
        lock_path = f"{notebook_path}.lock"
        try:
            if os.path.exists(lock_path):
                with open(lock_path, 'r') as lock_file:
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
                os.remove(lock_path)
        except Exception as e:
            logger.error(f"Error releasing lock: {str(e)}")
    
    def load_notebook(self, notebook_path: str) -> nbformat.NotebookNode:
        """Load a notebook from disk"""
        if not os.path.exists(notebook_path):
            raise FileNotFoundError(f"Notebook {notebook_path} not found")
        
        try:
            return nbformat.read(notebook_path, as_version=4)
        except Exception as e:
            logger.error(f"Error loading notebook {notebook_path}: {str(e)}")
            raise ValueError(f"Failed to load notebook: {str(e)}")
    
    def save_notebook(self, notebook: nbformat.NotebookNode, notebook_path: str) -> None:
        """Save a notebook to disk with atomic write"""
        # Create a temporary file
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(notebook_path))
        os.close(fd)
        
        try:
            # Write to the temporary file
            nbformat.write(notebook, temp_path)
            
            # Atomically replace the original file
            shutil.move(temp_path, notebook_path)
            
            # Add to history
            self._add_to_history(notebook_path, notebook)
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Error saving notebook {notebook_path}: {str(e)}")
            raise ValueError(f"Failed to save notebook: {str(e)}")
    
    def _add_to_history(self, notebook_path: str, notebook: nbformat.NotebookNode) -> None:
        """Add a notebook state to the history for undo operations"""
        if notebook_path not in self.history:
            self.history[notebook_path] = []
        
        # Create a deep copy of the notebook
        notebook_copy = nbformat.from_dict(nbformat.to_dict(notebook))
        
        # Add to history, maintaining max size
        self.history[notebook_path].append(notebook_copy)
        if len(self.history[notebook_path]) > self.history_size:
            self.history[notebook_path].pop(0)
    
    def create_notebook(self, notebook_path: str, kernel_name: str = "python3") -> nbformat.NotebookNode:
        """Create a new Jupyter notebook"""
        if os.path.exists(notebook_path):
            raise FileExistsError(f"Notebook {notebook_path} already exists")
        
        # Create the notebook directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(notebook_path)), exist_ok=True)
        
        # Create a new notebook with the specified kernel
        notebook = nbformat.v4.new_notebook()
        notebook.metadata.kernelspec = {
            "display_name": "Python 3",
            "language": "python",
            "name": kernel_name
        }
        
        # Save the new notebook
        self.save_notebook(notebook, notebook_path)
        return notebook
    
    def get_kernel_for_notebook(self, notebook_path: str) -> NotebookClient:
        """Get or create a kernel client for a notebook"""
        if notebook_path not in self.kernels:
            notebook = self.load_notebook(notebook_path)
            
            # Initialize new client
            client = NotebookClient(
                notebook, 
                timeout=600,
                kernel_name=notebook.metadata.get('kernelspec', {}).get('name', 'python3')
            )
            
            self.kernels[notebook_path] = client
        
        return self.kernels[notebook_path]
    
    def execute_notebook(self, notebook_path: str, timeout: int = 60) -> nbformat.NotebookNode:
        """Execute all cells in the notebook"""
        if not self._acquire_lock(notebook_path):
            raise RuntimeError(f"Could not acquire lock on {notebook_path}")
        
        try:
            notebook = self.load_notebook(notebook_path)
            client = self.get_kernel_for_notebook(notebook_path)
            
            # Set timeout
            client.timeout = timeout
            
            # Execute the notebook
            notebook = client.execute()
            
            # Save the executed notebook
            self.save_notebook(notebook, notebook_path)
            
            return notebook
        finally:
            self._release_lock(notebook_path)
    
    def execute_cell(self, notebook_path: str, cell_id: str, timeout: int = 60) -> Dict[str, Any]:
        """Execute a single cell and return its outputs"""
        if not self._acquire_lock(notebook_path):
            raise RuntimeError(f"Could not acquire lock on {notebook_path}")
        
        try:
            notebook = self.load_notebook(notebook_path)
            client = self.get_kernel_for_notebook(notebook_path)
            
            # Set timeout
            client.timeout = timeout
            
            # Find the cell index
            cell_idx = self.get_cell_index_by_id(notebook, cell_id)
            
            # Execute the cell
            client.execute_cell(notebook.cells[cell_idx])
            
            # Process outputs
            outputs = self._process_outputs(notebook.cells[cell_idx].outputs)
            
            # Save the notebook with updated outputs
            self.save_notebook(notebook, notebook_path)
            
            return {
                "cell_id": cell_id,
                "outputs": outputs
            }
        finally:
            self._release_lock(notebook_path)
    
    def _process_outputs(self, outputs: List) -> List[str]:
        """Process and format cell outputs"""
        result = []
        for output in outputs:
            output_type = output.output_type
            if output_type in OUTPUT_PROCESSORS:
                result.append(OUTPUT_PROCESSORS[output_type](output))
        
        return result
    
    def get_cell_index_by_id(self, notebook: nbformat.NotebookNode, cell_id: str) -> int:
        """Find cell index by ID"""
        for idx, cell in enumerate(notebook.cells):
            if cell.id == cell_id:
                return idx
        
        raise ValueError(f"Cell with ID {cell_id} not found")
    
    def add_cell(self, notebook_path: str, content: str, cell_type: str = "code", 
                 position: int = -1) -> Tuple[nbformat.NotebookNode, str]:
        """Add a new cell to the notebook and return the updated notebook and cell ID"""
        if not self._acquire_lock(notebook_path):
            raise RuntimeError(f"Could not acquire lock on {notebook_path}")
        
        try:
            notebook = self.load_notebook(notebook_path)
            
            # Create a new cell
            cell = nbformat.v4.new_cell(cell_type=cell_type, source=content)
            
            # Ensure cell has a unique ID
            if not hasattr(cell, 'id') or not cell.id:
                cell.id = str(uuid.uuid4())
            
            # Handle negative positions
            if position < 0:
                position = len(notebook.cells) + position + 1
            
            # Clamp position
            position = max(0, min(position, len(notebook.cells)))
            
            # Insert the cell
            notebook.cells.insert(position, cell)
            
            # Save the updated notebook
            self.save_notebook(notebook, notebook_path)
            
            return notebook, cell.id
        finally:
            self._release_lock(notebook_path)
    
    def edit_cell(self, notebook_path: str, cell_id: str, new_content: str) -> nbformat.NotebookNode:
        """Edit the content of a cell"""
        if not self._acquire_lock(notebook_path):
            raise RuntimeError(f"Could not acquire lock on {notebook_path}")
        
        try:
            notebook = self.load_notebook(notebook_path)
            
            # Find the cell index
            idx = self.get_cell_index_by_id(notebook, cell_id)
            
            # Update cell content
            notebook.cells[idx].source = new_content
            
            # Save the updated notebook
            self.save_notebook(notebook, notebook_path)
            
            return notebook
        finally:
            self._release_lock(notebook_path)
    
    def delete_cell(self, notebook_path: str, cell_id: str) -> nbformat.NotebookNode:
        """Delete a cell from the notebook"""
        if not self._acquire_lock(notebook_path):
            raise RuntimeError(f"Could not acquire lock on {notebook_path}")
        
        try:
            notebook = self.load_notebook(notebook_path)
            
            # Find the cell index
            idx = self.get_cell_index_by_id(notebook, cell_id)
            
            # Remove the cell
            notebook.cells.pop(idx)
            
            # Save the updated notebook
            self.save_notebook(notebook, notebook_path)
            
            return notebook
        finally:
            self._release_lock(notebook_path)
    
    def get_outputs(self, notebook_path: str, cell_id: str) -> List[str]:
        """Get the outputs from a specific cell"""
        notebook = self.load_notebook(notebook_path)
        
        # Find the cell index
        idx = self.get_cell_index_by_id(notebook, cell_id)
        
        # Ensure this is a code cell
        if notebook.cells[idx].cell_type != 'code':
            return []
        
        # Process and return outputs
        return self._process_outputs(notebook.cells[idx].outputs)
    
    def undo_last_operation(self, notebook_path: str) -> Dict[str, Any]:
        """Undo the last operation on a notebook"""
        if not self._acquire_lock(notebook_path):
            raise RuntimeError(f"Could not acquire lock on {notebook_path}")
        
        try:
            if notebook_path not in self.history or len(self.history[notebook_path]) < 2:
                raise ValueError("No operations to undo")
            
            # Remove the current state
            self.history[notebook_path].pop()
            
            # Get the previous state
            previous_state = self.history[notebook_path][-1]
            
            # Save the previous state
            nbformat.write(previous_state, notebook_path)
            
            return {
                "success": True,
                "message": "Last operation undone successfully"
            }
        finally:
            self._release_lock(notebook_path)
    
    def compare_notebooks(self, notebook_path_a: str, notebook_path_b: str, 
                          include_outputs: bool = False) -> Dict[str, Any]:
        """Compare two notebooks and return their differences"""
        notebook_a = self.load_notebook(notebook_path_a)
        notebook_b = self.load_notebook(notebook_path_b)
        
        # Compare cells count
        cell_count_a = len(notebook_a.cells)
        cell_count_b = len(notebook_b.cells)
        
        # Compare cell contents
        cell_diffs = []
        
        # Find the maximum number of cells to compare
        max_cells = max(cell_count_a, cell_count_b)
        
        for i in range(max_cells):
            if i < cell_count_a and i < cell_count_b:
                # Both notebooks have this cell
                cell_a = notebook_a.cells[i]
                cell_b = notebook_b.cells[i]
                
                # Compare cell types
                if cell_a.cell_type != cell_b.cell_type:
                    cell_diffs.append({
                        "index": i,
                        "diff_type": "cell_type",
                        "a_type": cell_a.cell_type,
                        "b_type": cell_b.cell_type
                    })
                
                # Compare cell contents
                if cell_a.source != cell_b.source:
                    cell_diffs.append({
                        "index": i,
                        "diff_type": "content",
                        "a_id": cell_a.id,
                        "b_id": cell_b.id
                    })
                
                # Compare outputs if requested and both are code cells
                if include_outputs and cell_a.cell_type == "code" and cell_b.cell_type == "code":
                    outputs_a = self._process_outputs(cell_a.outputs)
                    outputs_b = self._process_outputs(cell_b.outputs)
                    
                    if outputs_a != outputs_b:
                        cell_diffs.append({
                            "index": i,
                            "diff_type": "outputs",
                            "a_id": cell_a.id,
                            "b_id": cell_b.id
                        })
            else:
                # One notebook has more cells than the other
                cell_diffs.append({
                    "index": i,
                    "diff_type": "missing_cell",
                    "in_a": i < cell_count_a,
                    "in_b": i < cell_count_b
                })
        
        return {
            "cell_count_diff": cell_count_a - cell_count_b,
            "differences": cell_diffs,
            "metadata_diff": notebook_a.metadata != notebook_b.metadata
        }
    
    def close_kernel(self, notebook_path: str) -> None:
        """Close the kernel associated with a notebook"""
        if notebook_path in self.kernels:
            try:
                # Stop the kernel
                client = self.kernels[notebook_path]
                client.km.shutdown_kernel()
                del self.kernels[notebook_path]
            except Exception as e:
                logger.error(f"Error closing kernel for {notebook_path}: {str(e)}")
    
    def close_all_kernels(self) -> None:
        """Close all active kernel sessions"""
        for notebook_path in list(self.kernels.keys()):
            self.close_kernel(notebook_path) 