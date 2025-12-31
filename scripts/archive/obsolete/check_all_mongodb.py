"""Check MongoDB for ALL editions across all sources."""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    # Count ALL editions
    total_all = await mongodb.db["processed_editions"].count_documents({})
    print(f"Total editions (all sources, all publications): {total_all}")

    # Count by source
    sources = await mongodb.db["processed_editions"].distinct("source")
    print(f"\nSources found: {sources}")

    for source in sources:
        count = await mongodb.db["processed_editions"].count_documents(
            {"source": source}
        )
        print(f"  {source}: {count}")

    # Count by publication
    pubs = await mongodb.db["processed_editions"].distinct("publication_id")
    print(f"\nPublications found: {pubs}")

    # Sample ANY recent entry
    print("\nMost recent 3 entries (any publication/source):")
    cursor = mongodb.db["processed_editions"].find({}).sort("processed_at", -1).limit(3)

    async for doc in cursor:
        print(
            f"  - {doc.get('edition_key', 'N/A')}: "
            f"pub={doc.get('publication_id', 'N/A')}, "
            f"source={doc.get('source', 'N/A')}, "
            f"date={doc.get('publication_date', 'N/A')}"
        )

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
