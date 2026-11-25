import sys
from pathlib import Path

# Add parent directory to sys.path so it can find main, database, models
parent_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(parent_dir))

from main import app
