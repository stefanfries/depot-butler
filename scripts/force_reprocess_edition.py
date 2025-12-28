"""Force reprocess a specific edition for testing."""

import asyncio
from datetime import date

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.models import Edition
from depotbutler.services.edition_tracking_service import EditionTrackingService


async def main() -> None:
    """Force reprocess Megatrend Folger 51/2025."""
    # Connect to MongoDB
    mongodb = await get_mongodb_service()
    await mongodb.connect()

    # Get the edition tracker
    tracker = EditionTrackingService(mongodb=mongodb)

    # Edition to force reprocess
    edition = Edition(
        title="Megatrend Folger",
        issue="51/2025",
        date=date(2025, 12, 18),
        publication_id="megatrend-folger",
        filename="2025-12-18_Megatrend-Folger_51-2025.pdf",
        file_path="data/tmp/2025-12-18_Megatrend-Folger_51-2025.pdf",
        download_url="https://example.com/pdf",
    )

    # Force reprocess
    await tracker.force_reprocess(edition)
    print("✓ Forced reprocessing of Megatrend Folger 51/2025")

    # Close
    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
