"""
Fix blob storage only: Move files and update metadata.

MongoDB is already fixed. This script only fixes Azure Blob Storage.
"""

import asyncio
import sys

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def get_blob_fixes():
    """Get list of blobs that need fixing by scanning Azure Storage."""
    blob_service = BlobStorageService()

    logger.info("Scanning Azure Blob Storage...")

    fixes = []

    # List all blobs in container
    blob_list = blob_service.container_client.list_blobs()

    for blob in blob_list:
        blob_path = blob.name

        # Check if blob is in wrong folder
        if "/die-800-prozent-strategie/" in blob_path:
            new_blob_path = blob_path.replace(
                "/die-800-prozent-strategie/", "/megatrend-folger/"
            )

            # Extract edition_key from path (for MongoDB update)
            # Path format: YYYY/die-800-prozent-strategie/YYYY-MM-DD_Name_II-YYYY.pdf
            parts = blob_path.split("/")
            if len(parts) == 3:
                filename = parts[2]
                # Parse filename to get edition_key
                import re

                match = re.match(r"(\d{4})-\d{2}-\d{2}_.*_(\d{2})-\d{4}\.pdf", filename)
                if match:
                    year = match.group(1)
                    issue = match.group(2)
                    edition_key = f"{year}_{issue}_megatrend-folger"

                    fixes.append(
                        {
                            "edition_key": edition_key,
                            "old_blob_path": blob_path,
                            "new_blob_path": new_blob_path,
                        }
                    )

    logger.info("Found %d blobs to fix", len(fixes))
    return fixes


async def fix_blobs(fixes, execute: bool):
    """Fix blob storage: move files and update metadata."""
    blob_service = BlobStorageService()

    logger.info("\nBlobs to fix: %d", len(fixes))

    if not execute:
        logger.info("\nDRY-RUN: Would fix blobs")
        for fix in fixes[:5]:
            logger.info("  %s → %s", fix["old_blob_path"], fix["new_blob_path"])
        if len(fixes) > 5:
            logger.info("  ... and %d more", len(fixes) - 5)
        return

    logger.info("\nExecuting blob fixes...")
    success_count = 0
    error_count = 0

    for fix in fixes:
        try:
            old_path = fix["old_blob_path"]
            new_path = fix["new_blob_path"]

            # Get blob clients
            source_client = blob_service.container_client.get_blob_client(old_path)
            dest_client = blob_service.container_client.get_blob_client(new_path)

            # Get existing metadata
            properties = source_client.get_blob_properties()
            metadata = properties.metadata or {}

            # Update metadata
            if "publication_id" in metadata:
                metadata["publication_id"] = "megatrend-folger"

            # Copy to new location
            dest_client.start_copy_from_url(source_client.url)

            # Set corrected metadata
            dest_client.set_blob_metadata(metadata)

            # Delete old blob
            source_client.delete_blob()

            success_count += 1
            if success_count <= 5 or success_count % 50 == 0:
                logger.info("  ✓ Fixed [%d/%d]", success_count, len(fixes))
        except Exception as e:
            error_count += 1
            logger.error("  ❌ Failed: %s - %s", fix["old_blob_path"], e)

    logger.info("\n✅ Blob fixes complete:")
    logger.info("  Success: %d", success_count)
    if error_count > 0:
        logger.error("  Errors: %d", error_count)


async def update_mongodb(fixes, execute: bool):
    """Update MongoDB blob_path fields."""
    db = await get_mongodb_service()

    if not execute:
        logger.info("\nDRY-RUN: Would update %d MongoDB blob_path fields", len(fixes))
        return

    logger.info("\nUpdating MongoDB blob_path fields...")
    success_count = 0

    for fix in fixes:
        result = await db.db["processed_editions"].update_one(
            {"edition_key": fix["edition_key"]},
            {"$set": {"blob_path": fix["new_blob_path"]}},
        )
        if result.modified_count > 0:
            success_count += 1

    logger.info("✅ Updated %d MongoDB documents", success_count)


async def main():
    execute = "--execute" in sys.argv

    logger.info("=" * 70)
    logger.info("Fix Blob Storage")
    logger.info("=" * 70)
    if execute:
        logger.info("MODE: EXECUTE")
    else:
        logger.info("MODE: DRY-RUN")

    # Get list of fixes needed
    fixes = await get_blob_fixes()

    if not fixes:
        logger.info("\n✅ No blobs need fixing!")
        return

    # Fix blobs
    await fix_blobs(fixes, execute)

    # Update MongoDB
    await update_mongodb(fixes, execute)

    if not execute:
        logger.info("\nTo execute: python scripts/fix_blobs.py --execute")


if __name__ == "__main__":
    asyncio.run(main())
