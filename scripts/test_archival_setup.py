"""Setup for testing blob archival by deactivating recipients and clearing last edition."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service


async def main() -> None:
    """Deactivate all recipients except stefan.fries.burgdorf@gmx.de."""
    mongodb = await get_mongodb_service()
    await mongodb.connect()

    recipients_collection = mongodb.db["recipients"]

    # Deactivate all recipients except yourself
    result_deactivate = await recipients_collection.update_many(
        {"email": {"$ne": "stefan.fries.burgdorf@gmx.de"}},
        {"$set": {"active": False}},
    )

    # Ensure you're active
    result_activate = await recipients_collection.update_one(
        {"email": "stefan.fries.burgdorf@gmx.de"}, {"$set": {"active": True}}
    )

    print(f"✓ Deactivated {result_deactivate.modified_count} recipients")
    print(
        f"✓ Ensured stefan.fries.burgdorf@gmx.de is active ({result_activate.modified_count} updated)"
    )

    # Get the last processed edition
    processed_collection = mongodb.db["processed_editions"]
    last_edition = await processed_collection.find_one(sort=[("processed_at", -1)])

    if last_edition:
        print("\n📄 Last processed edition:")
        print(f"   Key: {last_edition.get('edition_key')}")
        print(f"   Title: {last_edition.get('title')}")
        print(f"   Issue: {last_edition.get('issue')}")
        print(f"   Date: {last_edition.get('date')}")
        print(f"   Processed at: {last_edition.get('processed_at')}")

        # Ask for confirmation before deleting
        print("\nDo you want to delete this edition? (yes/no)")
        confirm = input().strip().lower()

        if confirm == "yes":
            result_delete = await processed_collection.delete_one(
                {"_id": last_edition["_id"]}
            )
            print(f"✓ Deleted edition (deleted_count={result_delete.deleted_count})")
        else:
            print("❌ Deletion cancelled")
    else:
        print("❌ No processed editions found")

    await mongodb.close()
    print("\n✅ Setup complete! Run: uv run python -m depotbutler")


if __name__ == "__main__":
    asyncio.run(main())
