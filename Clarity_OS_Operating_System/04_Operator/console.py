# console.py — Pure Cyan Operator Console v3

import os
import sys

# Add OS root to import path so kernel.py can see OS_Modules, Kernel, etc.
CURRENT_DIR = os.path.dirname(__file__)
OS_ROOT = os.path.dirname(CURRENT_DIR)
if OS_ROOT not in sys.path:
    sys.path.insert(0, OS_ROOT)

from console_router import main

if __name__ == "__main__":
    main()
