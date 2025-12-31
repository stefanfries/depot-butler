"""Delete the last processed edition for testing."""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main() -> None:
    """Delete the most recent processed edition."""
    # Connect to MongoDB
    mongodb = await get_mongodb_service()
    await mongodb.connect()

    if not mongodb.edition_repo:
        print("❌ Edition repository not available")
        return

    # Get the most recent edition
    db = mongodb.client[mongodb.db_name]
    collection = db["processed_editions"]

    # Find the most recent edition (sorted by processed_at descending)
    most_recent = await collection.find_one(sort=[("processed_at", -1)])

    if not most_recent:
        print("ℹ️ No processed editions found")
        await mongodb.close()
        return

    # Display edition details
    print("Most recent edition:")
    print(f"  Edition key: {most_recent.get('edition_key')}")
    print(f"  Title: {most_recent.get('title')}")
    print(f"  Date: {most_recent.get('publication_date')}")
    print(f"  Processed at: {most_recent.get('processed_at')}")
    if most_recent.get("blob_url"):
        print(f"  Blob URL: {most_recent.get('blob_url')}")

    # Ask for confirmation
    response = input("\n⚠️ Delete this edition? (y/N): ")

    if response.lower() == "y":
        result = await collection.delete_one({"_id": most_recent["_id"]})
        if result.deleted_count > 0:
            print("✅ Deleted successfully")
        else:
            print("❌ Failed to delete")
    else:
        print("❌ Cancelled")

    # Close
    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
