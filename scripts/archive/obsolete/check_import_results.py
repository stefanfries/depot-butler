"""Quick script to check import results."""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    db = await get_mongodb_service()

    # Count total editions
    count = await db.db["processed_editions"].count_documents({})
    print(f"\n📊 MongoDB editions: {count}")

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

    print("\n📁 By source:")
    for source in sources:
        print(f"  {source['_id']}: {source['count']}")

    # Count by year (extract from edition_key since publication_date might be string)
    all_editions = (
        await db.db["processed_editions"].find({}, {"edition_key": 1}).to_list(None)
    )

    from collections import Counter

    years = Counter()
    for ed in all_editions:
        year = ed["edition_key"].split("_")[0]  # Format: YYYY_II_publication
        years[year] += 1

    print("\n📅 By year:")
    for year in sorted(years.keys()):
        print(f"  {year}: {years[year]}")

    # Latest 3 entries
    latest = (
        await db.db["processed_editions"]
        .find(
            {},
            {
                "_id": 0,
                "edition_key": 1,
                "publication_id": 1,
                "source": 1,
                "blob_path": 1,
                "publication_date": 1,
            },
        )
        .sort("publication_date", -1)
        .limit(3)
        .to_list(3)
    )

    print("\n📰 Latest 3 editions:")
    for entry in latest:
        print(
            f"  {entry['publication_date'].strftime('%Y-%m-%d')} | {entry['edition_key']} | {entry['blob_path'][:60]}..."
        )

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
