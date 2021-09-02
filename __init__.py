import sys
from pathlib import Path

module_path = str(Path(__file__).parent.absolute())
while module_path in sys.path:
    # In case we couldn't remove it last time we do a cleanup
    sys.path.remove(module_path)
sys.path.append(module_path)

from plugin import Plugin

__all__ = ['Plugin']
