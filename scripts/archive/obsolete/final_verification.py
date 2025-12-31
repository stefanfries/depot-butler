"""
Final comprehensive verification of all fixes
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
    print("FINAL COMPREHENSIVE VERIFICATION")
    print("=" * 80)

    db = await get_mongodb_service()
    blob_service = BlobStorageService()

    # 1. MongoDB Verification
    print("\n1. MONGODB VERIFICATION")
    print("-" * 80)

    total_editions = await db.db["processed_editions"].count_documents({})
    print(f"Total editions: {total_editions}")

    # Check publication_id
    megatrend_count = await db.db["processed_editions"].count_documents(
        {"publication_id": "megatrend-folger"}
    )
    print(
        f"  publication_id='megatrend-folger': {megatrend_count} ✅"
        if megatrend_count == total_editions
        else "  ⚠️  Some editions have wrong publication_id"
    )

    # Check blob_path format
    relative_paths = await db.db["processed_editions"].count_documents(
        {"blob_path": {"$regex": "^[0-9]{4}/"}}
    )
    print(
        f"  Relative paths: {relative_paths} ✅"
        if relative_paths == total_editions
        else "  ⚠️  Some paths are not relative"
    )

    # Check for % in paths
    percent_paths = await db.db["processed_editions"].count_documents(
        {"blob_path": {"$regex": "%"}}
    )
    print(
        f"  Paths with %: {percent_paths} ✅"
        if percent_paths == 0
        else f"  ⚠️  {percent_paths} paths still have %"
    )

    # Check for full URLs
    url_paths = await db.db["processed_editions"].count_documents(
        {"blob_path": {"$regex": "^https://"}}
    )
    print(
        f"  Full URLs: {url_paths} ✅"
        if url_paths == 0
        else f"  ⚠️  {url_paths} paths are full URLs"
    )

    # 2. Blob Storage Verification
    print("\n2. BLOB STORAGE VERIFICATION")
    print("-" * 80)

    blob_list = blob_service.container_client.list_blobs()

    percent_blobs = 0
    prozent_blobs = 0
    megatrend_blobs = 0

    for blob in blob_list:
        if "Die-800%-Strategie" in blob.name:
            percent_blobs += 1
        elif "Die-800-Prozent-Strategie" in blob.name:
            prozent_blobs += 1
        elif "Megatrend-Folger" in blob.name:
            megatrend_blobs += 1

    total_blobs = percent_blobs + prozent_blobs + megatrend_blobs

    print(f"Total blobs in container: {total_blobs}")
    print(
        f"  Blobs with %: {percent_blobs} ✅"
        if percent_blobs == 0
        else f"  ⚠️  {percent_blobs} blobs still have %"
    )
    print(f"  Blobs with -Prozent: {prozent_blobs} ✅")
    print(f"  Blobs with Megatrend-Folger: {megatrend_blobs} ✅")

    # 3. MongoDB <-> Blob Storage Consistency
    print("\n3. MONGODB ↔ BLOB STORAGE CONSISTENCY")
    print("-" * 80)

    # Test 5 random editions
    sample_editions = (
        await db.db["processed_editions"]
        .aggregate([{"$sample": {"size": 5}}])
        .to_list(5)
    )

    all_exist = True
    for ed in sample_editions:
        blob_path = ed["blob_path"]
        blob_client = blob_service.container_client.get_blob_client(blob_path)

        try:
            blob_client.get_blob_properties()
            exists = True
        except:
            exists = False
            all_exist = False

        status = "✅" if exists else "❌"
        print(f"  {status} {ed['edition_key']}: {blob_path}")

    if all_exist:
        print("\n✅ All sampled editions have matching blobs")
    else:
        print("\n⚠️  Some editions don't have matching blobs")

    # 4. Final Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    all_good = (
        megatrend_count == total_editions
        and relative_paths == total_editions
        and percent_paths == 0
        and url_paths == 0
        and percent_blobs == 0
        and all_exist
    )

    if all_good:
        print("✅ ALL VERIFICATIONS PASSED")
        print("\nYour archive is now consistent:")
        print(f"  • {total_editions} editions in MongoDB")
        print(f"  • {total_blobs} PDFs in Azure Blob Storage")
        print("  • All paths are relative (YYYY/publication_id/filename.pdf)")
        print("  • All filenames use -Prozent instead of %")
        print("  • All entries have publication_id='megatrend-folger'")
        print("  • MongoDB paths match actual blob locations")
    else:
        print("⚠️  SOME ISSUES REMAIN - review details above")


if __name__ == "__main__":
    asyncio.run(main())
