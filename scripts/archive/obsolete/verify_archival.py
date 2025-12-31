"""Verify that blob archival worked correctly."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service


async def main() -> None:
    """Check the last processed edition for blob metadata."""
    mongodb = await get_mongodb_service()
    await mongodb.connect()

    # Get the last processed edition
    processed_collection = mongodb.db["processed_editions"]
    last_edition = await processed_collection.find_one(sort=[("processed_at", -1)])

    if not last_edition:
        print("❌ No processed editions found")
        await mongodb.close()
        return

    print("📄 Last Processed Edition:")
    print(f"   Key: {last_edition.get('edition_key')}")
    print(f"   Title: {last_edition.get('title')}")
    print(f"   Issue: {last_edition.get('issue')}")
    print(f"   Date: {last_edition.get('date')}")

    print("\n⏰ Timestamps:")
    print(f"   Processed at:  {last_edition.get('processed_at')}")
    print(f"   Downloaded at: {last_edition.get('downloaded_at')}")
    print(f"   Email sent at: {last_edition.get('email_sent_at')}")
    print(f"   OneDrive uploaded at: {last_edition.get('onedrive_uploaded_at')}")
    print(f"   Archived at:   {last_edition.get('archived_at')}")

    print("\n☁️  Blob Metadata:")
    blob_url = last_edition.get("blob_url")
    blob_path = last_edition.get("blob_path")
    blob_container = last_edition.get("blob_container")
    file_size = last_edition.get("file_size_bytes")

    if blob_url:
        print(f"   ✓ Blob URL: {blob_url}")
        print(f"   ✓ Blob Path: {blob_path}")
        print(f"   ✓ Container: {blob_container}")
        print(f"   ✓ File Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        print("\n   ✅ BLOB ARCHIVAL VERIFIED: All metadata present in MongoDB")
    else:
        print("   ❌ No blob metadata found")
        print("   This edition was not archived to blob storage")

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
