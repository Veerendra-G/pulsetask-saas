import sys
from pathlib import Path

# Add backend_python directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend_python"
sys.path.insert(0, str(backend_dir))

from main import app
