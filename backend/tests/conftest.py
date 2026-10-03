import sys
from pathlib import Path

# Make `app` importable whether pytest is started from the repository root or backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
