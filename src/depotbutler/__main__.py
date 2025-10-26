import asyncio
import sys

from depotbutler.main import main

if __name__ == "__main__":
    # Parse command line arguments
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    exit_code = asyncio.run(main(mode))
    sys.exit(exit_code)
