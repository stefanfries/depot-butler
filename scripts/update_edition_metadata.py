"""
Update metadata for an existing edition without reprocessing.

Usage:
    uv run python scripts/update_edition_metadata.py

This script allows you to modify fields in MongoDB for an edition that's
already been processed, without triggering the full workflow (downloads,
emails, uploads). Useful for correcting metadata after the fact.
"""

import asyncio

from depotbutler.db.mongodb import MongoDBService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def update_edition_metadata() -> None:
    """Update metadata for a specific edition."""
    # Edition to update
    edition_key = "2025-12-17_DER AKTIONÄR 52/25 + 01/26"

    # Fields to update
    updates = {
        "source": "scheduled_job",  # This edition was processed by the daily job
    }

    logger.info("Updating edition metadata [key=%s]", edition_key)
    logger.info("Updates: %s", updates)

    async with MongoDBService() as db:
        # Check if edition exists
        assert db.edition_repo is not None
        is_tracked = await db.is_edition_processed(edition_key)
        if not is_tracked:
            logger.error("Edition not found in tracking database")
            return

        # Update metadata
        success = await db.edition_repo.update_edition_metadata(
            edition_key=edition_key, updates=updates
        )

        if success:
            logger.info("✅ Successfully updated edition metadata")
        else:
            logger.error("❌ Failed to update edition metadata")


if __name__ == "__main__":
    asyncio.run(update_edition_metadata())
