"""
Main entry point for DepotButler application.
"""

import asyncio
import sys

from depotbutler.utils.logger import get_logger
from depotbutler.workflow import DepotButlerWorkflow

logger = get_logger(__name__)


async def async_main(dry_run: bool = False) -> int:
    """
    Main async entry point for DepotButler.

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


def main() -> int:
    """
    Synchronous entry point that wraps the async main function.

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    # Parse command line arguments
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    return asyncio.run(async_main(dry_run=dry_run))


if __name__ == "__main__":
    sys.exit(main())
