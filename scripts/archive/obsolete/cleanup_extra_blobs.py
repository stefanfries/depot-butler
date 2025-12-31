"""
Cleanup script to remove extra blobs that don't match MongoDB records.

Will DELETE:
- Category 1: Historical files without "Die-" prefix (web collection duplicates)
- Category 3: Wrong date file (2022-06-22 vs correct 2022-06-23)
- Category 4a: Test publication file
- Category 4b: DER AKTIONÄR E-Paper file

Will KEEP:
- Category 2: Untracked 2024 files (need OneDrive import)
- Category 4c: Aktien-Report file
"""

import asyncio
import sys
from collections import defaultdict
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService


async def main():
    execute = "--execute" in sys.argv

    mode = "EXECUTE" if execute else "DRY-RUN"
    print("=" * 80)
    print(f"CLEANUP EXTRA BLOBS - {mode}")
    print("=" * 80)
    print("Will DELETE:")
    print("  1. Historical files without 'Die-' prefix (web duplicates)")
    print("  3. Wrong date file (2022-06-22)")
    print("  4a. Test publication")
    print("  4b. DER AKTIONÄR E-Paper")
    print()
    print("Will KEEP:")
    print("  2. Untracked 2024 files (need OneDrive import)")
    print("  4c. Aktien-Report")
    print("=" * 80)

    db = await get_mongodb_service()
    blob_service = BlobStorageService()

    # Get all blobs and MongoDB entries
    print("\n1. SCANNING STORAGE...")
    blob_list = blob_service.container_client.list_blobs()

    all_blobs = set()
    for blob in blob_list:
        all_blobs.add(blob.name)

    print(f"   Total blobs in Azure: {len(all_blobs)}")

    # Get tracked blobs
    editions = (
        await db.db["processed_editions"].find({}, {"blob_path": 1}).to_list(None)
    )
    tracked_blobs = set(ed["blob_path"] for ed in editions)

    print(f"   Total tracked in MongoDB: {len(tracked_blobs)}")

    # Find extras
    extra_blobs = all_blobs - tracked_blobs

    # Categorize extras
    print("\n2. CATEGORIZING EXTRA BLOBS...")

    to_delete = []  # Files to delete
    to_keep = []  # Files to keep (for info only)

    for blob_path in extra_blobs:
        # Category 1: Historical files without "Die-" prefix - DELETE
        if "800-Prozent-Strategie_" in blob_path and "Die-800" not in blob_path:
            to_delete.append(("Cat 1: Web duplicate", blob_path))

        # Category 3: Wrong date 2022-06-22 - DELETE
        elif "2022-06-22_Die-800-Prozent-Strategie_25-2022.pdf" in blob_path:
            to_delete.append(("Cat 3: Wrong date", blob_path))

        # Category 4a: Test publication - DELETE
        elif "test-publication" in blob_path:
            to_delete.append(("Cat 4a: Test publication", blob_path))

        # Category 4b: DER AKTIONÄR E-Paper - DELETE
        elif "der-aktionaer-epaper" in blob_path:
            to_delete.append(("Cat 4b: DER AKTIONÄR", blob_path))

        # Category 2: Untracked 2024 files (issues 04-16) - KEEP
        elif "2024" in blob_path and "Die-800-Prozent-Strategie" in blob_path:
            import re

            match = re.search(r"_(\d{2})-2024\.pdf$", blob_path)
            if match:
                issue = int(match.group(1))
                if 4 <= issue <= 16:
                    to_keep.append(("Cat 2: 2024 needs import", blob_path))

        # Category 4c: Aktien-Report - KEEP
        elif "Aktien-Report" in blob_path:
            to_keep.append(("Cat 4c: Aktien-Report", blob_path))

    print(f"\nFiles to DELETE: {len(to_delete)}")
    print(f"Files to KEEP: {len(to_keep)}")

    # Group by category for display
    delete_by_category = defaultdict(list)
    keep_by_category = defaultdict(list)

    for category, path in to_delete:
        delete_by_category[category].append(path)

    for category, path in to_keep:
        keep_by_category[category].append(path)

    print("\nDeletion breakdown:")
    for category, paths in sorted(delete_by_category.items()):
        print(f"  {category}: {len(paths)} files")

    if keep_by_category:
        print("\nFiles to keep (NOT deleted):")
        for category, paths in sorted(keep_by_category.items()):
            print(f"  {category}: {len(paths)} files")

    # Preview
    if not execute:
        print("\n3. PREVIEW")
        print("-" * 80)

        print("\nFILES TO DELETE:")
        for category in sorted(delete_by_category.keys()):
            paths = delete_by_category[category]
            print(f"\n{category}: {len(paths)} files")
            if len(paths) <= 5:
                for f in paths:
                    print(f"  ❌ {f}")
            else:
                for f in paths[:3]:
                    print(f"  ❌ {f}")
                print(f"     ... and {len(paths) - 3} more")

        if keep_by_category:
            print("\n" + "-" * 80)
            print("FILES TO KEEP (NOT deleted):")
            for category in sorted(keep_by_category.keys()):
                paths = keep_by_category[category]
                print(f"\n{category}: {len(paths)} files")
                for f in paths:
                    print(f"  ✅ {f}")

    # Delete
    if execute:
        print("\n3. DELETING BLOBS...")
        print("-" * 80)

        paths_to_delete = [path for _, path in to_delete]

        success_count = 0
        error_count = 0

        for i, blob_path in enumerate(paths_to_delete, 1):
            try:
                blob_client = blob_service.container_client.get_blob_client(blob_path)
                blob_client.delete_blob()
                success_count += 1

                if i % 10 == 0 or i == len(paths_to_delete):
                    print(f"  ✓ Deleted [{i}/{len(paths_to_delete)}]")
            except Exception as e:
                error_count += 1
                print(f"  ✗ Error deleting {blob_path}: {e}")

        print("\n✅ Cleanup complete:")
        print(f"   Success: {success_count}")
        print(f"   Errors: {error_count}")

        # Final verification
        print("\n4. FINAL VERIFICATION")
        print("-" * 80)

        # Re-scan
        blob_list = blob_service.container_client.list_blobs()
        remaining_blobs = sum(1 for _ in blob_list)

        print(f"Blobs remaining in Azure: {remaining_blobs}")
        print(f"Editions in MongoDB: {len(tracked_blobs)}")
        print(f"Expected extras (kept): {len(to_keep)}")
        expected_total = len(tracked_blobs) + len(to_keep)

        if remaining_blobs == expected_total:
            print(
                f"✅ Perfect - {remaining_blobs} blobs = {len(tracked_blobs)} tracked + {len(to_keep)} kept"
            )
        else:
            diff = remaining_blobs - expected_total
            print(f"⚠️  Difference: {diff} blobs")

    print("\n" + "=" * 80)
    if not execute:
        print("DRY-RUN complete. Run with --execute to perform cleanup.")
    else:
        print("CLEANUP complete.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
