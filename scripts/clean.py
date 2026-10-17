"""Remove only disposable caches in this project."""

import shutil

from app.config import ROOT


def main():
    """Never remove data, Docker volumes, models, or secret files."""
    for directory in (ROOT / "app", ROOT / "scripts", ROOT / "tests"):
        for path in directory.rglob("__pycache__"):
            shutil.rmtree(path)
    print("Python caches removed; datasets and volumes preserved")


if __name__ == "__main__":
    main()
