"""
Find the 15 extra blobs that exist in Azure Storage but not in MongoDB
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService


async def main():
    print("=" * 80)
    print("FINDING EXTRA BLOBS NOT TRACKED IN MONGODB")
    print("=" * 80)

    db = await get_mongodb_service()
    blob_service = BlobStorageService()

    # Get all blob paths from Azure Storage
    print("\n1. Scanning Azure Blob Storage...")
    blob_list = blob_service.container_client.list_blobs()

    all_blobs = set()
    for blob in blob_list:
        all_blobs.add(blob.name)

    print(f"   Total blobs in Azure: {len(all_blobs)}")

    # Get all blob_path values from MongoDB
    print("\n2. Getting tracked blobs from MongoDB...")
    editions = (
        await db.db["processed_editions"].find({}, {"blob_path": 1}).to_list(None)
    )

    tracked_blobs = set()
    for ed in editions:
        tracked_blobs.add(ed["blob_path"])

    print(f"   Total tracked in MongoDB: {len(tracked_blobs)}")

    # Find the difference
    extra_blobs = all_blobs - tracked_blobs

    print(f"\n3. EXTRA BLOBS (in Azure but not in MongoDB): {len(extra_blobs)}")
    print("=" * 80)

    if extra_blobs:
        # Sort and display
        sorted_extras = sorted(extra_blobs)

        for i, blob_path in enumerate(sorted_extras, 1):
            print(f"\n{i}. {blob_path}")

            # Try to extract year/issue from path
            parts = blob_path.split("/")
            if len(parts) >= 3:
                year = parts[0]
                publication = parts[1]
                filename = parts[2]

                print(f"   Year: {year}")
                print(f"   Publication folder: {publication}")
                print(f"   Filename: {filename}")

                # Check if similar edition exists in MongoDB
                if "-" in filename and "_" in filename:
                    # Try to extract issue number
                    import re

                    match = re.search(r"_(\d{2})-\d{4}\.pdf$", filename)
                    if match:
                        issue = match.group(1)
                        potential_key = f"{year}_{issue}_megatrend-folger"

                        exists = await db.db["processed_editions"].find_one(
                            {"edition_key": potential_key}
                        )

                        if exists:
                            print(
                                f"   ⚠️  Edition {potential_key} EXISTS in MongoDB with different filename!"
                            )
                            print(f"      MongoDB has: {exists['blob_path']}")
                        else:
                            print(f"   ℹ️  No edition found for key: {potential_key}")
    else:
        print("\n✅ No extra blobs found - perfect match!")

    # Check reverse - MongoDB entries without blobs
    print("\n\n4. CHECKING REVERSE: MongoDB entries without actual blobs")
    print("=" * 80)

    missing_blobs = tracked_blobs - all_blobs

    if missing_blobs:
        print(
            f"⚠️  Found {len(missing_blobs)} MongoDB entries pointing to non-existent blobs:"
        )
        for blob_path in sorted(missing_blobs)[:10]:
            print(f"   • {blob_path}")

        if len(missing_blobs) > 10:
            print(f"   ... and {len(missing_blobs) - 10} more")
    else:
        print("✅ All MongoDB entries have corresponding blobs")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
