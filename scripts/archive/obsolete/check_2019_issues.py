import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def check_2019_issues():
    db = await get_mongodb_service()

    # Look for all 2019 Megatrend Folger issues
    editions = (
        await db.db["processed_editions"]
        .find({"edition_key": {"$regex": "^2019_.*_megatrend-folger$"}})
        .sort("edition_key", 1)
        .to_list(None)
    )

    print(f"Found {len(editions)} Megatrend Folger issues in 2019:\n")
    for edition in editions:
        print(
            f"  {edition['edition_key']}: {edition['title']} - {edition['publication_date']}"
        )


asyncio.run(check_2019_issues())
