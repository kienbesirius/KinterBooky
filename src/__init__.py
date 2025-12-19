import sys
from pathlib import Path

_path = Path(__file__).resolve()

for x in range(3):
    _path = _path.parent
    if _path.name == "src":
        sys.path.insert(0, _path)
