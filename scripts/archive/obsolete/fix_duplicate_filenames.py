"""
Fix duplicate blob files:
1. Remove files with % in filename (keep -Prozent versions)
2. Update MongoDB blob_path to reference -Prozent versions
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService


async def main():
    execute = "--execute" in sys.argv

    mode = "EXECUTE" if execute else "DRY-RUN"
    print("=" * 80)
    print(f"FIX DUPLICATE BLOB FILES - {mode}")
    print("=" * 80)
    print("Strategy:")
    print("  1. RENAME files with % to -Prozent (when no -Prozent version exists)")
    print("  2. DELETE files with % (when -Prozent version already exists)")
    print("  3. Update MongoDB blob_path to use -Prozent versions")
    print("=" * 80)

    db = await get_mongodb_service()
    blob_service = BlobStorageService()

    # Step 1: Analyze which files need what action
    print("\n1. ANALYZING FILES")
    print("-" * 80)

    blob_list = blob_service.container_client.list_blobs()

    # Create lookup dictionaries
    percent_files = {}  # key: normalized path -> full path
    prozent_files = {}  # key: normalized path -> full path

    for blob in blob_list:
        if "Die-800%-Strategie" in blob.name:
            normalized = blob.name.replace("Die-800%-Strategie", "NORMALIZED")
            percent_files[normalized] = blob.name
        elif "Die-800-Prozent-Strategie" in blob.name:
            normalized = blob.name.replace("Die-800-Prozent-Strategie", "NORMALIZED")
            prozent_files[normalized] = blob.name

    # Determine actions
    both_versions = set(percent_files.keys()) & set(prozent_files.keys())
    only_percent = set(percent_files.keys()) - set(prozent_files.keys())

    files_to_delete = [percent_files[k] for k in both_versions]
    files_to_rename = [percent_files[k] for k in only_percent]

    print(f"Files to DELETE (% version, -Prozent exists): {len(files_to_delete)}")
    print(f"Files to RENAME (% to -Prozent, no duplicate): {len(files_to_rename)}")
    print(f"Total operations needed: {len(files_to_delete) + len(files_to_rename)}")

    # Preview
    if not execute:
        print("\nFirst 5 files to DELETE:")
        for f in files_to_delete[:5]:
            print(f"  ❌ {f}")

        print("\nFirst 5 files to RENAME:")
        for f in files_to_rename[:5]:
            new_name = f.replace("Die-800%-Strategie", "Die-800-Prozent-Strategie")
            print(f"  🔄 {f}")
            print(f"     → {new_name}")

    # Step 2: DELETE duplicate % files
    print(
        f"\n2. DELETING % VERSIONS THAT HAVE -Prozent DUPLICATES ({len(files_to_delete)} files)"
    )
    print("-" * 80)

    delete_success = 0
    delete_errors = 0

    if execute:
        for i, blob_path in enumerate(files_to_delete, 1):
            try:
                blob_client = blob_service.container_client.get_blob_client(blob_path)
                blob_client.delete_blob()
                delete_success += 1

                if i % 10 == 0 or i == len(files_to_delete):
                    print(f"  ✓ Deleted [{i}/{len(files_to_delete)}]")
            except Exception as e:
                delete_errors += 1
                print(f"  ✗ Error deleting {blob_path}: {e}")

        print(
            f"\n✅ Deletions complete: Success: {delete_success}, Errors: {delete_errors}"
        )
    else:
        print(f"DRY-RUN: Would delete {len(files_to_delete)} files")

    # Step 3: RENAME % files to -Prozent (where no duplicate exists)
    print(f"\n3. RENAMING % FILES TO -Prozent ({len(files_to_rename)} files)")
    print("-" * 80)

    rename_success = 0
    rename_errors = 0

    if execute:
        for i, old_path in enumerate(files_to_rename, 1):
            try:
                new_path = old_path.replace(
                    "Die-800%-Strategie", "Die-800-Prozent-Strategie"
                )

                # Copy to new name with metadata
                source_client = blob_service.container_client.get_blob_client(old_path)
                dest_client = blob_service.container_client.get_blob_client(new_path)

                properties = source_client.get_blob_properties()
                metadata = properties.metadata or {}

                dest_client.start_copy_from_url(source_client.url)

                # Wait for copy to complete
                import time

                max_wait = 10
                waited = 0
                while waited < max_wait:
                    copy_props = dest_client.get_blob_properties()
                    if copy_props.copy.status == "success":
                        break
                    time.sleep(0.5)
                    waited += 0.5

                dest_client.set_blob_metadata(metadata)
                source_client.delete_blob()

                rename_success += 1

                if i % 10 == 0 or i == len(files_to_rename):
                    print(f"  ✓ Renamed [{i}/{len(files_to_rename)}]")
            except Exception as e:
                rename_errors += 1
                print(f"  ✗ Error renaming {old_path}: {e}")

        print(
            f"\n✅ Renames complete: Success: {rename_success}, Errors: {rename_errors}"
        )
    else:
        print(f"DRY-RUN: Would rename {len(files_to_rename)} files")

    # Step 4: Update MongoDB blob_path fields
    print("\n4. UPDATING MONGODB blob_path FIELDS")
    print("-" * 80)

    # Find all MongoDB entries with % in blob_path
    mongo_updates = (
        await db.db["processed_editions"]
        .find({"blob_path": {"$regex": "Die-800%-Strategie"}})
        .to_list(None)
    )

    print(f"MongoDB entries with % in blob_path: {len(mongo_updates)}")

    if not execute:
        print("\nFirst 5 MongoDB updates:")
        for ed in mongo_updates[:5]:
            old_path = ed["blob_path"]
            new_path = old_path.replace(
                "Die-800%-Strategie", "Die-800-Prozent-Strategie"
            )
            print(f"  Edition: {ed['edition_key']}")
            print(f"    Old: {old_path}")
            print(f"    New: {new_path}")

    mongo_success = 0
    mongo_errors = 0

    if execute:
        for ed in mongo_updates:
            try:
                old_path = ed["blob_path"]
                new_path = old_path.replace(
                    "Die-800%-Strategie", "Die-800-Prozent-Strategie"
                )

                await db.db["processed_editions"].update_one(
                    {"_id": ed["_id"]}, {"$set": {"blob_path": new_path}}
                )
                mongo_success += 1

                if mongo_success % 10 == 0 or mongo_success == len(mongo_updates):
                    print(f"  ✓ Updated [{mongo_success}/{len(mongo_updates)}]")
            except Exception as e:
                mongo_errors += 1
                print(f"  ✗ Error updating {ed['edition_key']}: {e}")

        print("\n✅ MongoDB updates complete:")
        print(f"   Success: {mongo_success}")
        print(f"   Errors: {mongo_errors}")
    else:
        print(f"\nDRY-RUN: Would update {len(mongo_updates)} MongoDB entries")

    # Step 4: Verification
    if execute:
        print("\n4. VERIFICATION")
        print("-" * 80)

        # Check if any % files remain
        remaining_percent = await db.db["processed_editions"].count_documents(
            {"blob_path": {"$regex": "Die-800%-Strategie"}}
        )

        print(f"MongoDB entries with % remaining: {remaining_percent}")

        if remaining_percent == 0:
            print("✅ All MongoDB entries updated successfully!")
        else:
            print(f"⚠️  {remaining_percent} entries still need fixing")

        # Sample check
        sample = await db.db["processed_editions"].find_one(
            {"edition_key": "2023_01_megatrend-folger"}
        )

        if sample:
            print(f"\nSample edition: {sample['edition_key']}")
            print(f"  blob_path: {sample['blob_path']}")

            # Check if blob exists
            blob_client = blob_service.container_client.get_blob_client(
                sample["blob_path"]
            )
            try:
                blob_client.get_blob_properties()
                print("  ✅ Blob exists at this path")
            except:
                print("  ❌ Blob NOT found at this path")

    print("\n" + "=" * 80)
    if not execute:
        print("DRY-RUN complete. Run with --execute to apply changes.")
    else:
        print("EXECUTION complete.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
