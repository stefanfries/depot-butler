"""Check final results of historical PDF collection."""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    # Count total editions
    total = await mongodb.db["processed_editions"].count_documents({})
    print(f"Total editions in MongoDB: {total}")

    # Count by source
    web_hist = await mongodb.db["processed_editions"].count_documents(
        {"source": "web_historical"}
    )
    print(f"Web historical editions: {web_hist}")

    # Count with publication_id
    with_pub_id = await mongodb.db["processed_editions"].count_documents(
        {"source": "web_historical", "publication_id": {"$exists": True, "$ne": ""}}
    )
    print(f"Web historical with publication_id: {with_pub_id}")

    # Count Megatrend Folger editions
    megatrend = await mongodb.db["processed_editions"].count_documents(
        {"publication_id": "megatrend-folger"}
    )
    print(f"Megatrend Folger editions: {megatrend}")

    # Sample one edition to check fields
    sample = await mongodb.db["processed_editions"].find_one(
        {"publication_id": "megatrend-folger"}
    )

    if sample:
        print("\nSample edition fields:")
        for key in sorted(sample.keys()):
            if key != "_id":
                value = (
                    str(sample[key])[:50]
                    if isinstance(sample[key], str)
                    else sample[key]
                )
                print(f"  {key}: {value}")

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
