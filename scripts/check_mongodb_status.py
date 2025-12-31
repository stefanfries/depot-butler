"""Quick script to check MongoDB processed_editions status."""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    # Count web_historical editions
    web_count = await mongodb.db["processed_editions"].count_documents(
        {"publication_id": "megatrend-folger", "source": "web_historical"}
    )
    print(f"MongoDB web_historical count: {web_count}")

    # Count total megatrend-folger editions
    total = await mongodb.db["processed_editions"].count_documents(
        {"publication_id": "megatrend-folger"}
    )
    print(f"MongoDB total megatrend-folger: {total}")

    # Sample a few recent entries
    print("\nRecent 5 entries:")
    cursor = (
        mongodb.db["processed_editions"]
        .find({"publication_id": "megatrend-folger"})
        .sort("archived_at", -1)
        .limit(5)
    )

    async for doc in cursor:
        print(
            f"  - {doc['edition_key']}: source={doc.get('source', 'N/A')}, "
            f"blob_url={'✓' if doc.get('blob_url') else '✗'}, "
            f"download_url={'✓' if doc.get('download_url') else '✗'}"
        )

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
