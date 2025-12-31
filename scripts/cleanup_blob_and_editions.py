"""
Cleanup script to reset blob storage and processed_editions collection.

Use this when changing blob path structure to start fresh.
Deletes:
- All blobs from Azure Blob Storage 'editions' container
- All documents from MongoDB 'processed_editions' collection

CAUTION: This is destructive and cannot be undone!
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def get_blob_count(blob_service: BlobStorageService) -> int:
    """Get count of blobs in container."""
    try:
        blobs = blob_service.container_client.list_blobs()
        return sum(1 for _ in blobs)
    except Exception as e:
        logger.error(f"Failed to count blobs: {e}")
        return 0


async def delete_all_blobs(blob_service: BlobStorageService) -> tuple[int, int]:
    """
    Delete all blobs from container.

    Returns:
        Tuple of (deleted_count, failed_count)
    """
    deleted = 0
    failed = 0

    try:
        blobs = blob_service.container_client.list_blobs()

        for blob in blobs:
            try:
                blob_client = blob_service.container_client.get_blob_client(blob.name)
                blob_client.delete_blob()
                deleted += 1
                if deleted % 10 == 0:
                    logger.info(f"Deleted {deleted} blobs...")
            except Exception as e:
                logger.error(f"Failed to delete blob {blob.name}: {e}")
                failed += 1

        return deleted, failed
    except Exception as e:
        logger.error(f"Failed to list blobs: {e}")
        return deleted, failed


async def cleanup_all() -> None:
    """Main cleanup function."""
    logger.info("=" * 80)
    logger.info("BLOB STORAGE & MONGODB CLEANUP")
    logger.info("=" * 80)
    logger.info("")
    logger.info("⚠️  WARNING: This will permanently delete:")
    logger.info("   - All blobs from Azure Blob Storage 'editions' container")
    logger.info("   - All documents from MongoDB 'processed_editions' collection")
    logger.info("")
    logger.info("This action CANNOT be undone!")
    logger.info("")

    # Initialize services
    logger.info("Connecting to services...")
    mongodb = await get_mongodb_service()
    await mongodb.connect()

    blob_service = BlobStorageService()

    # Get current counts
    logger.info("")
    logger.info("Current state:")
    blob_count = await get_blob_count(blob_service)
    edition_count = (
        await mongodb.edition_repo.get_processed_editions_count()
        if mongodb.edition_repo
        else 0
    )

    logger.info(f"  📦 Blobs in Azure Storage: {blob_count}")
    logger.info(f"  📝 Documents in MongoDB: {edition_count}")
    logger.info("")

    if blob_count == 0 and edition_count == 0:
        logger.info("✅ Nothing to clean - both are already empty!")
        return

    # Confirm deletion
    logger.info("Type 'DELETE' (in uppercase) to proceed with cleanup:")
    confirmation = input("> ").strip()

    if confirmation != "DELETE":
        logger.info("❌ Cleanup cancelled (did not receive 'DELETE' confirmation)")
        return

    logger.info("")
    logger.info("🗑️  Starting cleanup...")
    logger.info("")

    # Delete blobs
    if blob_count > 0:
        logger.info(f"Deleting {blob_count} blobs from Azure Storage...")
        deleted, failed = await delete_all_blobs(blob_service)
        logger.info(f"  ✅ Deleted: {deleted}")
        if failed > 0:
            logger.info(f"  ⚠️  Failed: {failed}")
    else:
        logger.info("No blobs to delete")

    # Delete MongoDB documents
    if edition_count > 0:
        logger.info(f"Deleting {edition_count} documents from MongoDB...")
        result = await mongodb.db["processed_editions"].delete_many({})
        logger.info(f"  ✅ Deleted: {result.deleted_count} documents")
    else:
        logger.info("No MongoDB documents to delete")

    # Verify cleanup
    logger.info("")
    logger.info("Verifying cleanup...")
    final_blob_count = await get_blob_count(blob_service)
    final_edition_count = (
        await mongodb.edition_repo.get_processed_editions_count()
        if mongodb.edition_repo
        else 0
    )

    logger.info(f"  📦 Blobs remaining: {final_blob_count}")
    logger.info(f"  📝 Documents remaining: {final_edition_count}")
    logger.info("")

    if final_blob_count == 0 and final_edition_count == 0:
        logger.info("✅ Cleanup completed successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info(
            "  1. Run the daily job to archive new editions with new path structure"
        )
        logger.info("  2. Run import_from_onedrive.py to re-import historical editions")
    else:
        logger.info("⚠️  Cleanup completed but some items remain")
        if final_blob_count > 0:
            logger.info(f"    - {final_blob_count} blobs could not be deleted")
        if final_edition_count > 0:
            logger.info(f"    - {final_edition_count} documents could not be deleted")

    await mongodb.close()


if __name__ == "__main__":
    try:
        asyncio.run(cleanup_all())
    except KeyboardInterrupt:
        logger.info("\n❌ Cleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)
