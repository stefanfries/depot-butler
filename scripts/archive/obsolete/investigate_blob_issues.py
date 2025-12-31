"""
Investigate blob storage issues:
1. Find duplicate files (% vs -Prozent)
2. Check blob_path format in MongoDB
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
    print("INVESTIGATING BLOB STORAGE ISSUES")
    print("=" * 80)

    # Check MongoDB blob_path format
    print("\n1. CHECKING MONGODB blob_path FORMAT")
    print("-" * 80)
    db = await get_mongodb_service()

    # Get sample editions
    sample_editions = await db.db["processed_editions"].find().limit(5).to_list(5)

    for ed in sample_editions:
        print(f"\nEdition: {ed['edition_key']}")
        print(f"  blob_path: {ed.get('blob_path', 'N/A')}")
        print(f"  Length: {len(ed.get('blob_path', ''))}")

    # Check for duplicates with % vs -Prozent
    print("\n\n2. SCANNING FOR DUPLICATE FILES (% vs -Prozent)")
    print("-" * 80)

    blob_service = BlobStorageService()
    blob_list = blob_service.container_client.list_blobs()

    # Group by potential duplicate key (remove % and -Prozent to find matches)
    from collections import defaultdict

    blob_groups = defaultdict(list)

    for blob in blob_list:
        # Create a normalized key by removing both patterns
        normalized = blob.name.replace("Die-800%-Strategie", "STRATEGIE").replace(
            "Die-800-Prozent-Strategie", "STRATEGIE"
        )
        if "STRATEGIE" in normalized:
            blob_groups[normalized].append(blob.name)

    # Find duplicates
    duplicates = {k: v for k, v in blob_groups.items() if len(v) > 1}

    print(f"\nFound {len(duplicates)} sets of duplicate files:")
    for i, (key, paths) in enumerate(list(duplicates.items())[:10], 1):
        print(f"\n{i}. Duplicate set:")
        for path in paths:
            print(f"     {path}")

    if len(duplicates) > 10:
        print(f"\n... and {len(duplicates) - 10} more duplicate sets")

    # Count total duplicates
    total_duplicate_files = sum(len(v) for v in duplicates.values())
    files_to_remove = len(duplicates)  # One from each set (the % version)

    print(f"\nTotal files involved in duplicates: {total_duplicate_files}")
    print(f"Files to remove (% versions): {files_to_remove}")

    # Check what MongoDB expects
    print("\n\n3. CHECKING MONGODB vs ACTUAL BLOBS")
    print("-" * 80)

    # Get a few editions and check if their blob_path matches actual blobs
    test_editions = (
        await db.db["processed_editions"]
        .find({"edition_key": {"$regex": "2023_.*_megatrend-folger"}})
        .limit(3)
        .to_list(3)
    )

    for ed in test_editions:
        print(f"\nEdition: {ed['edition_key']}")
        blob_path = ed.get("blob_path", "")
        print(f"  MongoDB blob_path: {blob_path}")

        # Check if this is a full URL or relative path
        if blob_path.startswith("https://"):
            print("  ❌ ISSUE: blob_path is full URL (should be relative)")
            # Extract relative path
            if "/editions/" in blob_path:
                relative = blob_path.split("/editions/")[1]
                print(f"  Should be: {relative}")
        else:
            print("  ✅ blob_path is relative")

        # Check if file exists
        # Remove URL prefix if present
        check_path = blob_path
        if blob_path.startswith("https://"):
            check_path = (
                blob_path.split("/editions/")[1]
                if "/editions/" in blob_path
                else blob_path
            )

        blob_client = blob_service.container_client.get_blob_client(check_path)
        try:
            blob_client.get_blob_properties()
            print(f"  ✅ Blob exists at: {check_path}")
        except Exception as e:
            print(f"  ❌ Blob NOT found at: {check_path}")
            print(f"     Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
