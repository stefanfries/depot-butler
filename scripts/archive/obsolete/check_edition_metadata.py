"""Check MongoDB for edition blob metadata."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service


async def check_edition_metadata() -> None:
    """Check blob metadata for Megatrend Folger edition."""
    mongodb = await get_mongodb_service()
    await mongodb.connect()
    db = mongodb.db

    edition = await db["processed_editions"].find_one(
        {"edition_key": "2025-12-18_megatrend-folger"}
    )

    if edition:
        print("✓ Found edition: 2025-12-18_megatrend-folger")
        print(f"  downloaded_at: {edition.get('downloaded_at')}")
        print(f"  email_sent_at: {edition.get('email_sent_at')}")
        print(f"  onedrive_uploaded_at: {edition.get('onedrive_uploaded_at')}")
        print(f"  archived_at: {edition.get('archived_at')}")
        print(f"  blob_url: {edition.get('blob_url')}")
        print(f"  blob_path: {edition.get('blob_path')}")
        print(f"  blob_container: {edition.get('blob_container')}")
        print(f"  file_size_bytes: {edition.get('file_size_bytes')}")
    else:
        print("✗ Edition not found in MongoDB")

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(check_edition_metadata())
