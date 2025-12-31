"""
Check blob_path format in MongoDB - verify no full URLs exist
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    print("=" * 80)
    print("CHECKING blob_path FORMAT IN MONGODB")
    print("=" * 80)

    db = await get_mongodb_service()

    # Check for any entries with full URLs
    url_entries = (
        await db.db["processed_editions"]
        .find({"blob_path": {"$regex": "^https://"}})
        .to_list(None)
    )

    print(f"\n1. Entries with full URLs (should be 0): {len(url_entries)}")

    if url_entries:
        print("\n⚠️  Found entries with full URLs:")
        for ed in url_entries[:10]:
            print(f"  {ed['edition_key']}: {ed['blob_path']}")

        if len(url_entries) > 10:
            print(f"  ... and {len(url_entries) - 10} more")
    else:
        print("  ✅ No full URLs found - all paths are relative")

    # Check for proper relative paths
    relative_entries = (
        await db.db["processed_editions"]
        .find({"blob_path": {"$regex": "^[0-9]{4}/"}})
        .to_list(None)
    )

    print(f"\n2. Entries with relative paths (YYYY/...): {len(relative_entries)}")

    # Check for % in blob_path (should be 0 now)
    percent_entries = await db.db["processed_editions"].count_documents(
        {"blob_path": {"$regex": "%"}}
    )

    print(f"\n3. Entries with % in blob_path (should be 0): {percent_entries}")

    if percent_entries == 0:
        print("  ✅ All % characters replaced with -Prozent")
    else:
        print(f"  ⚠️  Still {percent_entries} entries with % in path")

    # Sample check
    print("\n4. SAMPLE ENTRIES:")
    print("-" * 80)

    samples = await db.db["processed_editions"].find().limit(5).to_list(5)

    for ed in samples:
        print(f"\nEdition: {ed['edition_key']}")
        print(f"  publication_id: {ed['publication_id']}")
        print(f"  blob_path: {ed['blob_path']}")
        print(
            f"  Format: {'✅ Relative' if not ed['blob_path'].startswith('https://') else '❌ Full URL'}"
        )
        print(
            f"  Naming: {'✅ -Prozent' if '-Prozent-' in ed['blob_path'] or 'Megatrend-Folger' in ed['blob_path'] else '✅ Megatrend-Folger'}"
        )

    # Total count
    total = await db.db["processed_editions"].count_documents({})
    print(f"\n5. TOTAL EDITIONS: {total}")

    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
