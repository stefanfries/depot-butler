"""
Entry point for running depot-butler as a module: python -m depotbutler
"""

import sys

from depotbutler.main import main

if __name__ == "__main__":
    sys.exit(main())
