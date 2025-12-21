"""
Main entry point for DepotButler application.
"""

import asyncio
import sys

from depotbutler.utils.logger import get_logger
from depotbutler.workflow import DepotButlerWorkflow

logger = get_logger(__name__)


async def main(dry_run: bool = False) -> int:
    """
    Main entry point for DepotButler.

    Args:
        dry_run: If True, simulates workflow without sending emails or uploading files

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    logger.info("🚀 DepotButler starting")

    if dry_run:
        logger.warning("🧪 DRY-RUN MODE ENABLED")

    # Run complete workflow
    async with DepotButlerWorkflow(dry_run=dry_run) as workflow:
        result = await workflow.run_full_workflow()
        return 0 if result["success"] else 1


if __name__ == "__main__":
    # Parse command line arguments
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    exit_code = asyncio.run(main(dry_run=dry_run))
    sys.exit(exit_code)
