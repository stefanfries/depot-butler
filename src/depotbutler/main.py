"""
Main entry point for DepotButler application.
Can run either the full workflow (with OneDrive) or just download.
"""

import asyncio
import sys

from depotbutler.utils.logger import get_logger
from depotbutler.workflow import DepotButlerWorkflow

logger = get_logger(__name__)


async def main(mode: str = "full") -> int:
    """
    Main entry point with different execution modes.

    Args:
        mode: Execution mode
            - "full": Complete workflow (download + OneDrive + email)
            - "download": Download only (for testing)

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    logger.info("🚀 DepotButler starting in '%s' mode", mode)

    if mode == "full":
        # Run complete workflow
        async with DepotButlerWorkflow() as workflow:
            result = await workflow.run_full_workflow()
            return 0 if result["success"] else 1

    elif mode == "download":
        # Legacy download-only mode for testing
        return await _download_only_mode()

    else:
        logger.error("Unknown mode: %s. Use 'full' or 'download'", mode)
        return 1


async def _download_only_mode() -> int:
    """Legacy download-only functionality for testing."""
    import pathlib

    from depotbutler.browser_client import BrowserBoersenmedienClient
    from depotbutler.publications import PUBLICATIONS
    from depotbutler.settings import Settings
    from depotbutler.utils.helpers import create_filename

    try:
        logger.info("Running in download-only mode")
        client = BrowserBoersenmedienClient()
        await client.login()

        # Discover subscriptions
        await client.discover_subscriptions()

        # Use first configured publication
        if not PUBLICATIONS:
            logger.error("No publications configured")
            return 1

        publication = PUBLICATIONS[0]
        edition = await client.get_latest_edition(publication)
        _ = await client.get_publication_date(edition)

        filename = create_filename(edition)

        # Use the same temporary directory as the workflow
        settings = Settings()
        tracking_file = pathlib.Path(settings.tracking.file_path)
        temp_dir = tracking_file.parent / "tmp"
        filepath = temp_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading '%s' to: %s", edition.title, filepath)
        await client.download_edition(edition, str(filepath))
        logger.info("Download successful")
        await client.close()

        return 0

    except Exception as e:
        logger.error("Download failed: %s", e, exc_info=True)
        return 1


# Entry point for different contexts
if __name__ == "__main__":
    # Parse command line arguments
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    exit_code = asyncio.run(main(mode))
    sys.exit(exit_code)
