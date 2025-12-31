import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def check_issue_18():
    db = await get_mongodb_service()

    # Look for issue #18/2019
    edition = await db.db["processed_editions"].find_one(
        {"edition_key": "2019_18_megatrend-folger"}
    )

    if edition:
        print("✅ Found issue #18/2019!")
        print(f"   Edition key: {edition['edition_key']}")
        print(f"   Title: {edition['title']}")
        print(f"   Publication date: {edition['publication_date']}")
        print(f"   Source: {edition['source']}")
    else:
        print("❌ Issue #18/2019 NOT found")


asyncio.run(check_issue_18())
