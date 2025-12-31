"""Check early year entries in MongoDB."""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    db = await get_mongodb_service()

    # Check 2014-2017 entries
    for year in ["2014", "2015", "2016", "2017"]:
        count = await db.db["processed_editions"].count_documents(
            {"edition_key": {"$regex": f"^{year}_"}}
        )

        sample = (
            await db.db["processed_editions"]
            .find(
                {"edition_key": {"$regex": f"^{year}_"}},
                {"_id": 0, "edition_key": 1, "blob_path": 1, "blob_url": 1},
            )
            .limit(2)
            .to_list(2)
        )

        print(f"\n{year}: {count} entries")
        for entry in sample:
            has_path = "blob_path" in entry and entry["blob_path"]
            has_url = "blob_url" in entry and entry["blob_url"]
            print(f"  {entry['edition_key']}")
            print(
                f"    blob_path: {entry.get('blob_path', 'MISSING')[:80] if has_path else 'MISSING'}"
            )
            print(f"    blob_url: {'✓' if has_url else 'MISSING'}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
