"""Delete incomplete web_historical editions from MongoDB.

These editions are missing the publication_id field and need to be recreated.
"""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    # Count editions to delete
    count = await mongodb.db["processed_editions"].count_documents(
        {"source": "web_historical"}
    )

    print(f"Found {count} web_historical editions to delete")
    print(
        "These will be recreated with complete metadata by re-running the collection script."
    )

    response = input("\nProceed with deletion? (yes/no): ")

    if response.lower() == "yes":
        result = await mongodb.db["processed_editions"].delete_many(
            {"source": "web_historical"}
        )
        print(f"✓ Deleted {result.deleted_count} editions")
    else:
        print("Cancelled")

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
