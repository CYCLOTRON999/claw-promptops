"""CLAW PROMPTOPS - Streamlit Community Cloud Root Entrypoint."""

import runpy
import sys
from pathlib import Path

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Execute the primary operations dashboard
dashboard_path = ROOT_DIR / "ui" / "dashboard.py"
runpy.run_path(str(dashboard_path), run_name="__main__")
