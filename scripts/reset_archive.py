"""
Full Archive Reset Script

Safely wipes MongoDB processed_editions collection and Azure Blob Storage editions container
to prepare for clean OneDrive import.

**WARNING**: This is a DESTRUCTIVE operation. Only use when:
- OneDrive folder is complete and authoritative
- You want a clean slate from single source of truth
- Current data has mixed sources (web + OneDrive)

Usage:
    # Preview what will be deleted (dry-run)
    uv run python scripts/reset_archive.py --dry-run

    # Execute full reset (IRREVERSIBLE)
    uv run python scripts/reset_archive.py --execute

Safety Features:
    - Dry-run mode by default (must use --execute flag)
    - Confirmation prompt before deletion
    - Detailed statistics before and after
    - Creates backup metadata file before deletion

After Reset:
    Run: uv run python scripts/import_from_onedrive.py
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService


async def backup_metadata(db, blob_service):
    """Create backup of current state before deletion."""
    print("\n📦 Creating metadata backup...")

    # Get MongoDB edition count (exclude _id to avoid ObjectId serialization)
    editions = (
        await db.db["processed_editions"]
        .find(
            {},
            {
                "_id": 0,  # Exclude ObjectId
                "edition_key": 1,
                "publication_id": 1,
                "publication_date": 1,
                "title": 1,
                "blob_path": 1,
                "source": 1,
            },
        )
        .to_list(None)
    )

    # Get blob count
    blob_list = blob_service.container_client.list_blobs()
    blob_names = [blob.name for blob in blob_list]

    backup_data = {
        "backup_time": datetime.now(UTC).isoformat(),
        "mongodb_count": len(editions),
        "blob_count": len(blob_names),
        "editions_sample": editions[:10],  # First 10 for reference
        "blob_sample": blob_names[:10],
    }

    backup_file = Path(
        f"data/tmp/archive_backup_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
    )
    backup_file.parent.mkdir(parents=True, exist_ok=True)

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2)

    print(f"   ✓ Backup saved to: {backup_file}")
    return backup_data


async def main():
    execute = "--execute" in sys.argv

    print("=" * 80)
    print("FULL ARCHIVE RESET")
    print("=" * 80)
    print("⚠️  WARNING: This will DELETE:")
    print("   - All entries in MongoDB 'processed_editions' collection")
    print("   - All blobs in Azure 'editions' container")
    print()
    print("This operation is IRREVERSIBLE!")
    print("=" * 80)

    if not execute:
        print("\n🔍 DRY-RUN MODE: Showing what would be deleted")

    # Initialize services
    db = await get_mongodb_service()
    blob_service = BlobStorageService()

    # Current state
    print("\n1. CURRENT STATE")
    print("-" * 80)

    editions_count = await db.db["processed_editions"].count_documents({})
    print(f"MongoDB editions: {editions_count}")

    # Count by source
    sources = (
        await db.db["processed_editions"]
        .aggregate(
            [
                {"$group": {"_id": "$source", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
        )
        .to_list(None)
    )

    if sources:
        print("\nBy source:")
        for source in sources:
            print(f"  - {source['_id']}: {source['count']}")

    blob_list = blob_service.container_client.list_blobs()
    blobs_count = sum(1 for _ in blob_list)
    print(f"\nAzure blobs: {blobs_count}")

    if not execute:
        print("\n" + "=" * 80)
        print("DRY-RUN complete. Use --execute to perform reset.")
        print("=" * 80)
        return

    # Create backup
    backup_data = await backup_metadata(db, blob_service)

    # Final confirmation
    print("\n" + "=" * 80)
    print("⚠️  FINAL CONFIRMATION REQUIRED")
    print("=" * 80)
    print("You are about to DELETE:")
    print(f"  - {editions_count} MongoDB editions")
    print(f"  - {blobs_count} Azure blobs")
    print()
    response = input("Type 'DELETE ALL' to confirm: ")

    if response != "DELETE ALL":
        print("\n❌ Reset cancelled (confirmation not matched)")
        return

    print("\n2. DELETING DATA")
    print("-" * 80)

    # Delete MongoDB collection
    print("\n📄 Deleting MongoDB collection...")
    result = await db.db["processed_editions"].delete_many({})
    print(f"   ✓ Deleted {result.deleted_count} editions")

    # Delete all blobs
    print("\n☁️  Deleting Azure blobs...")
    blob_list = blob_service.container_client.list_blobs()
    blob_names = [blob.name for blob in blob_list]

    deleted_count = 0
    error_count = 0

    for i, blob_name in enumerate(blob_names, 1):
        try:
            blob_client = blob_service.container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            deleted_count += 1

            if i % 50 == 0 or i == len(blob_names):
                print(f"   ✓ Deleted [{i}/{len(blob_names)}]")
        except Exception as e:
            error_count += 1
            print(f"   ✗ Error deleting {blob_name}: {e}")

    print(f"\n   ✓ Deleted {deleted_count} blobs")
    if error_count > 0:
        print(f"   ⚠️  {error_count} errors")

    # Verify empty state
    print("\n3. VERIFICATION")
    print("-" * 80)

    remaining_editions = await db.db["processed_editions"].count_documents({})
    print(f"MongoDB editions remaining: {remaining_editions}")

    blob_list = blob_service.container_client.list_blobs()
    remaining_blobs = sum(1 for _ in blob_list)
    print(f"Azure blobs remaining: {remaining_blobs}")

    print("\n" + "=" * 80)
    if remaining_editions == 0 and remaining_blobs == 0:
        print("✅ RESET COMPLETE - Archive is empty")
        print("\nNext step: Run OneDrive import")
        print("  uv run python scripts/import_from_onedrive.py")
    else:
        print("⚠️  WARNING: Some data remains")
        print(f"  MongoDB: {remaining_editions} editions")
        print(f"  Blobs: {remaining_blobs} blobs")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
