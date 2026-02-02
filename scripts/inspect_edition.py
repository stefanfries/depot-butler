"""
Inspect metadata for a specific edition.

Usage:
    uv run python scripts/inspect_edition.py [edition_key]

If no edition_key provided, shows the most recent edition.
"""

import asyncio
import json
import sys
from datetime import datetime

from depotbutler.db.mongodb import MongoDBService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


def json_serial(obj: object) -> str:
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


async def inspect_edition() -> None:
    """Inspect metadata for a specific edition."""
    # Get edition_key from command line or use most recent
    if len(sys.argv) > 1:
        edition_key = sys.argv[1]
    else:
        # Find most recent edition
        async with MongoDBService() as db:
            assert db.edition_repo is not None
            recent = (
                await db.edition_repo.collection.find()
                .sort("processed_at", -1)
                .limit(1)
                .to_list(1)
            )
            if not recent:
                print("❌ No editions found in database")
                return
            edition_key = recent[0]["edition_key"]
            print(f"📌 Using most recent edition: {edition_key}\n")

    async with MongoDBService() as db:
        assert db.edition_repo is not None
        result = await db.edition_repo.collection.find_one(
            {"edition_key": edition_key}, {"_id": 0}
        )

        if result:
            print(f"\n📄 Edition Metadata for: {edition_key}\n")
            print(json.dumps(result, indent=2, default=json_serial))
            print("\n" + "=" * 60)

            # Analyze what might need updating
            print("\n🔍 Analysis:\n")

            if "source" not in result:
                print(
                    "⚠️  Missing 'source' field (should be: scheduled_job, web_historical, or onedrive_import)"
                )
            else:
                print(f"✓ source: {result['source']}")

            if "file_path" in result and result["file_path"]:
                print(f"✓ file_path: {result['file_path']}")
            else:
                print(
                    "⚠️  file_path is empty (expected for scheduled_job/web_historical, or missing OneDrive path)"
                )

            if "blob_url" in result:
                print(f"✓ blob_url: {result['blob_url']}")
            else:
                print("⚠️  Missing blob_url (not archived to blob storage)")

            if "downloaded_at" in result:
                print(f"✓ downloaded_at: {result['downloaded_at']}")
            else:
                print("⚠️  Missing downloaded_at timestamp")

        else:
            print(f"\n❌ Edition not found: {edition_key}")


if __name__ == "__main__":
    asyncio.run(inspect_edition())
