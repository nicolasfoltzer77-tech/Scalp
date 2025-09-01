# tests/conftest.py
# Injecte la racine du repo au sys.path pour que 'engine.*' soit importable
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
