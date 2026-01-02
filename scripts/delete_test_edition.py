"""Delete a test edition from MongoDB to verify dry-run behavior."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service


async def delete_edition() -> None:
    """Delete the DER AKTIONÄR edition to test dry-run."""
    mongodb = await get_mongodb_service()

    try:
        edition_key = "2025-12-30_der-aktionaer_02-26"

        if mongodb.edition_repo and mongodb.edition_repo.collection is not None:
            result = await mongodb.edition_repo.collection.delete_one(
                {"edition_key": edition_key}
            )

            if result.deleted_count > 0:
                print(f"✓ Deleted edition: {edition_key}")
            else:
                print(f"⚠ Edition not found: {edition_key}")
        else:
            print("✗ MongoDB edition repository not available")

    finally:
        await mongodb.close()


if __name__ == "__main__":
    asyncio.run(delete_edition())
