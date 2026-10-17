"""Execute the demonstration with this project's interpreter rather than a global Jupyter command."""

import sys

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient

from app.config import ROOT


def main():
    """Persist notebook outputs only after every cell has executed successfully."""
    path = ROOT / "demo.ipynb"
    notebook = nbformat.read(path, as_version=4)
    manager = KernelManager(kernel_name="python3")
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    client = NotebookClient(notebook, km=manager, timeout=180, resources={"metadata": {"path": str(ROOT)}})
    client.execute(cleanup_kc=True)
    nbformat.write(notebook, path)
    count = sum(cell.cell_type == "code" for cell in notebook.cells)
    print(f"Executed all {count} code cells with the project interpreter; notebook saved")


if __name__ == "__main__":
    main()
