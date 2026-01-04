"""
Cleanup script to remove onedrive_import entries from blob storage and MongoDB.

Use this to clean up test OneDrive imports before production import.
Deletes ONLY entries with source="onedrive_import":
- Matching blobs from Azure Blob Storage 'editions' container
- Matching documents from MongoDB 'processed_editions' collection

CAUTION: This is destructive and cannot be undone!
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from typing import Any

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def get_onedrive_import_editions(mongodb: Any) -> list[dict[str, Any]]:
    """Get all editions with source='onedrive_import'."""
    try:
        cursor = mongodb.db["processed_editions"].find({"source": "onedrive_import"})
        editions: list[dict[str, Any]] = await cursor.to_list(length=None)
        return editions
    except Exception as e:
        logger.error(f"Failed to query editions: {e}")
        return []


async def delete_onedrive_import_blobs(
    blob_service: BlobStorageService, editions: list[dict], dry_run: bool = False
) -> tuple[int, int]:
    """
    Delete blobs matching onedrive_import editions.

    Args:
        blob_service: Azure Blob Storage service
        editions: List of edition documents with blob_path
        dry_run: If True, only simulate deletion

    Returns:
        Tuple of (deleted_count, failed_count)
    """
    deleted = 0
    failed = 0

    try:
        # Extract blob paths from editions
        blob_paths = [ed.get("blob_path") for ed in editions if ed.get("blob_path")]

        if not blob_paths:
            logger.info("  No blob paths found in editions")
            return 0, 0

        for blob_path in blob_paths:
            try:
                if dry_run:
                    logger.info(f"  [DRY-RUN] Would delete blob: {blob_path}")
                    deleted += 1
                else:
                    blob_client = blob_service.container_client.get_blob_client(
                        blob_path
                    )
                    blob_client.delete_blob()
                    deleted += 1
                    if deleted % 10 == 0:
                        logger.info(f"  Deleted {deleted} blobs...")
            except Exception as e:
                logger.error(f"  Failed to delete blob {blob_path}: {e}")
                failed += 1

        return deleted, failed
    except Exception as e:
        logger.error(f"Failed to process blobs: {e}")
        return deleted, failed


async def cleanup_onedrive_imports(dry_run: bool = False) -> None:
    """
    Main cleanup function for onedrive_import source entries.

    Args:
        dry_run: If True, only simulate cleanup without actual deletion
    """
    mode = "DRY-RUN" if dry_run else "CLEANUP"
    logger.info("=" * 80)
    logger.info(f"ONEDRIVE_IMPORT {mode}")
    logger.info("=" * 80)
    logger.info("")
    if dry_run:
        logger.info("🔍 DRY-RUN MODE: No actual deletions will occur")
    else:
        logger.info("⚠️  WARNING: This will permanently delete:")
        logger.info(
            "   - Blobs matching onedrive_import editions from Azure Blob Storage"
        )
        logger.info(
            "   - All documents with source='onedrive_import' from MongoDB 'processed_editions'"
        )
        logger.info("")
        logger.info("This action CANNOT be undone!")
    logger.info("")

    # Initialize services
    logger.info("Connecting to services...")
    mongodb = await get_mongodb_service()
    await mongodb.connect()

    blob_service = BlobStorageService()

    # Get onedrive_import editions
    logger.info("")
    logger.info("Querying onedrive_import editions...")
    onedrive_editions = await get_onedrive_import_editions(mongodb)

    logger.info("")
    logger.info("Current state:")
    logger.info(
        f"  📝 Editions with source='onedrive_import': {len(onedrive_editions)}"
    )

    if len(onedrive_editions) == 0:
        logger.info("")
        logger.info("✅ Nothing to clean - no onedrive_import entries found!")
        await mongodb.close()
        return

    # Show sample entries
    logger.info("")
    logger.info("Sample entries to be deleted:")
    for i, ed in enumerate(onedrive_editions[:5], 1):
        edition_key = ed.get("edition_key", "unknown")
        blob_path = ed.get("blob_path", "no blob")
        logger.info(f"  {i}. {edition_key}")
        logger.info(f"     Blob: {blob_path}")

    if len(onedrive_editions) > 5:
        logger.info(f"  ... and {len(onedrive_editions) - 5} more")

    logger.info("")

    # Confirm deletion (skip for dry-run)
    if not dry_run:
        logger.info("Type 'DELETE' (in uppercase) to proceed with cleanup:")
        confirmation = input("> ").strip()

        if confirmation != "DELETE":
            logger.info("❌ Cleanup cancelled (did not receive 'DELETE' confirmation)")
            await mongodb.close()
            return

    logger.info("")
    mode_label = "🔍 DRY-RUN" if dry_run else "🗑️  Starting cleanup"
    logger.info(f"{mode_label}...")
    logger.info("")

    # Delete blobs
    logger.info(f"Processing {len(onedrive_editions)} blobs from Azure Storage...")
    deleted, failed = await delete_onedrive_import_blobs(
        blob_service, onedrive_editions, dry_run
    )
    if dry_run:
        logger.info(f"  🔍 Would delete: {deleted}")
    else:
        logger.info(f"  ✅ Deleted: {deleted}")
    if failed > 0:
        logger.info(f"  ⚠️  Failed: {failed}")

    # Delete MongoDB documents
    logger.info("")
    logger.info(f"Processing {len(onedrive_editions)} documents from MongoDB...")
    if dry_run:
        logger.info(f"  🔍 Would delete: {len(onedrive_editions)} documents")
    else:
        result = await mongodb.db["processed_editions"].delete_many(
            {"source": "onedrive_import"}
        )
        logger.info(f"  ✅ Deleted: {result.deleted_count} documents")

    # Verify cleanup
    logger.info("")
    if not dry_run:
        logger.info("Verifying cleanup...")
        final_onedrive_editions = await get_onedrive_import_editions(mongodb)
        logger.info(
            f"  📝 onedrive_import documents remaining: {len(final_onedrive_editions)}"
        )
        logger.info("")

        if len(final_onedrive_editions) == 0:
            logger.info("✅ Cleanup completed successfully!")
            logger.info("")
            logger.info("Next steps:")
            logger.info("  1. Run import_from_onedrive.py for production import")
            logger.info("  2. Run enrich_download_urls.py to add website URLs")
        else:
            logger.info("⚠️  Cleanup completed but some items remain")
            logger.info(
                f"    - {len(final_onedrive_editions)} onedrive_import documents could not be deleted"
            )
    else:
        logger.info("✅ Dry-run completed!")
        logger.info("")
        logger.info("To execute actual cleanup, run without --dry-run flag:")
        logger.info("  uv run python scripts/cleanup_blob_and_editions.py")

    await mongodb.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cleanup onedrive_import entries from blob storage and MongoDB"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview cleanup without actual deletion",
    )

    args = parser.parse_args()

    try:
        asyncio.run(cleanup_onedrive_imports(dry_run=args.dry_run))
    except KeyboardInterrupt:
        logger.info("\n❌ Cleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)
