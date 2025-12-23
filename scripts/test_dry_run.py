"""
Dry-run test script for DepotButler workflow.
Simulates the full workflow without actually sending emails or uploading files.
"""

import asyncio
import sys
from pathlib import Path

from depotbutler.main import async_main

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if __name__ == "__main__":
    # Run workflow in dry-run mode
    print("🧪 Starting DepotButler in DRY-RUN mode")
    print("=" * 60)
    print("This will:")
    print("  ✓ Connect to MongoDB and fetch real data")
    print("  ✓ Login to boersenmedien.com")
    print("  ✓ Download the latest edition")
    print("  ✓ Show which recipients would receive emails/uploads")
    print("  ✗ NOT send any actual emails")
    print("  ✗ NOT upload any files to OneDrive")
    print("=" * 60)
    print()

    exit_code = asyncio.run(async_main(dry_run=True))

    print()
    print("=" * 60)
    print("🧪 Dry-run completed!")
    print("=" * 60)

    sys.exit(exit_code)
