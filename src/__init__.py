import sys
from pathlib import Path

# Ensure src/ and config/ are on sys.path for cross-package imports.
# src/ — so `from silver.xxx` works inside source files
# config/ — so `from entity_registry` and `from prompt_loader` work
_src = str(Path(__file__).parent)
_config = str(Path(__file__).parent.parent / "config")

if _src not in sys.path:
    sys.path.insert(0, _src)
if _config not in sys.path:
    sys.path.insert(0, _config)
