"""Check what fields exist in web_historical editions."""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    # Get one sample web_historical edition
    doc = await mongodb.db["processed_editions"].find_one({"source": "web_historical"})

    if doc:
        print("Sample web_historical edition fields:")
        for key, value in doc.items():
            val_str = str(value)[:100] if len(str(value)) > 100 else str(value)
            print(f"  {key}: {val_str}")
    else:
        print("No web_historical editions found")

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
