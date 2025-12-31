"""
Fix publication_id mistake: All editions are "megatrend-folger", not two separate publications.

The filename changed from "Die-800%-Strategie" to "Megatrend-Folger" ~1.5 years ago,
but they're the SAME publication. We incorrectly treated them as two publications.

This script:
1. Updates MongoDB: Changes all "die-800-prozent-strategie" to "megatrend-folger"
2. Updates edition_keys: Changes suffix in edition keys
3. Updates blob paths: Changes folder structure in blob_path field
4. Moves blobs: Moves files in Azure Blob Storage to correct folders

Usage:
    python scripts/fix_publication_id.py              # Dry-run (preview only)
    python scripts/fix_publication_id.py --execute    # Actually fix data
"""

import asyncio
import sys

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def analyze_wrong_editions():
    """Analyze editions with wrong publication_id."""
    db = await get_mongodb_service()

    # Find all editions with wrong publication_id
    wrong_editions = (
        await db.db["processed_editions"]
        .find({"publication_id": "die-800-prozent-strategie"})
        .to_list(None)
    )

    logger.info("Found %d editions with wrong publication_id", len(wrong_editions))

    # Group by year
    from collections import defaultdict

    by_year = defaultdict(int)
    for ed in wrong_editions:
        year = ed["edition_key"].split("_")[0]
        by_year[year] += 1

    logger.info("\nBreakdown by year:")
    for year in sorted(by_year.keys()):
        logger.info("  %s: %d editions", year, by_year[year])

    return wrong_editions


async def fix_mongodb(wrong_editions, execute: bool):
    """Fix MongoDB: Update publication_id and edition_keys."""
    db = await get_mongodb_service()

    logger.info("\n" + "=" * 70)
    logger.info("MONGODB FIX")
    logger.info("=" * 70)

    updates = []
    for ed in wrong_editions:
        old_key = ed["edition_key"]
        new_key = old_key.replace("_die-800-prozent-strategie", "_megatrend-folger")

        old_blob_path = ed.get("blob_path", "")
        new_blob_path = old_blob_path.replace(
            "/die-800-prozent-strategie/", "/megatrend-folger/"
        )

        updates.append(
            {
                "_id": ed["_id"],
                "old_key": old_key,
                "new_key": new_key,
                "old_blob_path": old_blob_path,
                "new_blob_path": new_blob_path,
            }
        )

    # Show preview
    logger.info("\nFirst 5 updates preview:")
    for update in updates[:5]:
        logger.info("  Edition key: %s → %s", update["old_key"], update["new_key"])
        logger.info("  Blob path:   %s", update["old_blob_path"])
        logger.info("               → %s", update["new_blob_path"])
        logger.info("")

    if not execute:
        logger.info("DRY-RUN: Would update %d MongoDB documents", len(updates))
        return updates

    # Execute updates
    logger.info("Executing MongoDB updates...")
    success_count = 0
    error_count = 0

    for update in updates:
        try:
            result = await db.db["processed_editions"].update_one(
                {"_id": update["_id"]},
                {
                    "$set": {
                        "publication_id": "megatrend-folger",
                        "edition_key": update["new_key"],
                        "blob_path": update["new_blob_path"],
                    }
                },
            )
            if result.modified_count > 0:
                success_count += 1
                if success_count <= 5 or success_count % 100 == 0:
                    logger.info(
                        "  ✓ Updated [%d/%d]: %s",
                        success_count,
                        len(updates),
                        update["new_key"],
                    )
            else:
                error_count += 1
                logger.error("  ❌ Failed to update: %s", update["old_key"])
        except Exception as e:
            error_count += 1
            logger.error("  ❌ Error updating %s: %s", update["old_key"], e)

    logger.info("\n✅ MongoDB updates complete:")
    logger.info("  Success: %d", success_count)
    if error_count > 0:
        logger.error("  Errors: %d", error_count)

    return updates


async def fix_blob_storage(updates, execute: bool):
    """Fix Azure Blob Storage: Move files to correct folders and update metadata."""
    blob_service = BlobStorageService()

    logger.info("\n" + "=" * 70)
    logger.info("BLOB STORAGE FIX")
    logger.info("=" * 70)

    # Group by year to organize moves
    from collections import defaultdict

    by_year = defaultdict(list)
    for update in updates:
        year = update["new_key"].split("_")[0]
        by_year[year].append(update)

    logger.info("\nBlob moves needed:")
    for year in sorted(by_year.keys()):
        logger.info("  %s: %d files", year, len(by_year[year]))

    if not execute:
        logger.info("\nDRY-RUN: Would perform these fixes for %d blobs:", len(updates))
        logger.info("  1. Move: {year}/die-800-prozent-strategie/{filename}")
        logger.info("          → {year}/megatrend-folger/{filename}")
        logger.info("  2. Update metadata: publication_id → megatrend-folger")
        return

    # Execute blob moves and metadata updates
    logger.info("\nExecuting blob moves and metadata updates...")
    success_count = 0
    error_count = 0

    for update in updates:
        old_blob_path = update["old_blob_path"]
        new_blob_path = update["new_blob_path"]

        if not old_blob_path or old_blob_path == new_blob_path:
            continue

        try:
            # Step 1: Get existing metadata from old blob
            blob_client = blob_service.container_client.get_blob_client(old_blob_path)
            properties = blob_client.get_blob_properties()  # NOT async!
            metadata = properties.metadata or {}

            # Step 2: Update metadata (fix publication_id)
            if "publication_id" in metadata:
                metadata["publication_id"] = "megatrend-folger"

            # Step 3: Copy to new location WITH corrected metadata
            source_blob_client = blob_service.container_client.get_blob_client(
                old_blob_path
            )
            dest_blob_client = blob_service.container_client.get_blob_client(
                new_blob_path
            )

            # Start copy operation
            dest_blob_client.start_copy_from_url(source_blob_client.url)

            # Set corrected metadata on new blob
            dest_blob_client.set_blob_metadata(metadata)

            # Step 4: Delete old location
            blob_client.delete_blob()

            success_count += 1
            if success_count <= 5 or success_count % 50 == 0:
                logger.info(
                    "  ✓ Fixed [%d/%d]: %s", success_count, len(updates), new_blob_path
                )
        except Exception as e:
            error_count += 1
            logger.error("  ❌ Failed to fix %s: %s", old_blob_path, e)

    logger.info("\n✅ Blob fixes complete:")
    logger.info("  Success: %d (moved + metadata updated)", success_count)
    if error_count > 0:
        logger.error("  Errors: %d", error_count)


async def verify_fix():
    """Verify the fix: Check MongoDB state."""
    db = await get_mongodb_service()

    logger.info("\n" + "=" * 70)
    logger.info("VERIFICATION")
    logger.info("=" * 70)

    # Count by publication_id
    pipeline = [{"$group": {"_id": "$publication_id", "count": {"$sum": 1}}}]
    results = await db.db["processed_editions"].aggregate(pipeline).to_list(None)

    logger.info("\nPublications in MongoDB:")
    for result in results:
        logger.info("  %s: %d editions", result["_id"], result["count"])

    # Check for wrong publication_id
    wrong_count = await db.db["processed_editions"].count_documents(
        {"publication_id": "die-800-prozent-strategie"}
    )

    if wrong_count > 0:
        logger.error(
            "\n❌ Still have %d editions with wrong publication_id!", wrong_count
        )
    else:
        logger.info("\n✅ All editions now have correct publication_id!")


async def main():
    """Main entry point."""
    execute = "--execute" in sys.argv

    logger.info("=" * 70)
    logger.info("Fix Publication ID Mistake")
    logger.info("=" * 70)
    if execute:
        logger.info("MODE: EXECUTE (will modify data)")
    else:
        logger.info("MODE: DRY-RUN (preview only)")
    logger.info("")

    # Analyze wrong editions
    wrong_editions = await analyze_wrong_editions()

    if not wrong_editions:
        logger.info("\n✅ No wrong editions found! Already fixed?")
        await verify_fix()
        return

    # Fix MongoDB
    updates = await fix_mongodb(wrong_editions, execute)

    # Fix blob storage
    await fix_blob_storage(updates, execute)

    # Verify fix (only if executed)
    if execute:
        await verify_fix()
    else:
        logger.info("\n" + "=" * 70)
        logger.info("To execute the fix, run:")
        logger.info("  python scripts/fix_publication_id.py --execute")
        logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
