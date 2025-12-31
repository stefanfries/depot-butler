import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def check():
    db = await get_mongodb_service()
    count = await db.db["processed_editions"].count_documents({})
    print(f"Total editions in MongoDB: {count}")

    # Show a few samples
    if count > 0:
        samples = await db.db["processed_editions"].find().limit(5).to_list(5)
        print("\nSample editions:")
        for edition in samples:
            print(
                f"  - {edition['edition_key']}: {edition['title']} ({edition.get('publication_date')})"
            )


asyncio.run(check())
