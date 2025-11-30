"""Quick script to check cookie expiration in MongoDB"""

import asyncio
import json

from depotbutler.db.mongodb import get_mongodb_service


async def check():
    mongodb = await get_mongodb_service()
    result = await mongodb.db.config.find_one({"_id": "auth_cookie"})
    print("MongoDB auth_cookie document:")
    print(json.dumps(result, indent=2, default=str))


asyncio.run(check())
