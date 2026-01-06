"""Show publication delivery statistics."""

import asyncio

from depotbutler.db.mongodb import close_mongodb_connection, get_mongodb_service


async def show_stats() -> None:
    """Display current publication statistics."""
    mongodb = await get_mongodb_service()

    print("📊 Current Publication Statistics:\n")
    pubs = await mongodb.db.publications.find({}).to_list(None)

    for pub in pubs:
        name = pub.get("name")
        pub_id = pub.get("publication_id")
        delivery_count = pub.get("delivery_count", 0)
        last_delivered = pub.get("last_delivered_at")

        print(f"{name} ({pub_id})")
        print(f"  Deliveries: {delivery_count}")
        print(f"  Last delivered: {last_delivered}")
        print()

    await close_mongodb_connection()


if __name__ == "__main__":
    asyncio.run(show_stats())
