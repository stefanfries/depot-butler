import asyncio
from collections import defaultdict

from depotbutler.db.mongodb import get_mongodb_service


async def analyze_editions():
    db = await get_mongodb_service()

    # Get all editions
    editions = await db.db["processed_editions"].find().to_list(None)

    print(f"Total editions: {len(editions)}\n")

    # Group by publication
    by_pub = defaultdict(list)
    for edition in editions:
        pub_id = edition["publication_id"]
        by_pub[pub_id].append(edition)

    print("By publication:")
    for pub_id, eds in by_pub.items():
        print(f"  {pub_id}: {len(eds)} editions")

    # Sample edition keys
    print("\nSample edition keys:")
    for edition in editions[:5]:
        print(f"  - {edition['edition_key']}: {edition['title']}")


asyncio.run(analyze_editions())
