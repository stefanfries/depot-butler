import asyncio
import sys

from depotbutler.main import main

if __name__ == "__main__":
    # Parse command line arguments
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    exit_code = asyncio.run(main(dry_run=dry_run))
    sys.exit(exit_code)
