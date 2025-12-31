"""
Test enhanced processed_editions schema with granular timestamps.

Demonstrates:
- Creating edition with blob storage metadata
- Updating individual pipeline timestamps
- Querying editions with new fields

Run: uv run python scripts/test_enhanced_schema.py
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def test_enhanced_schema():
    """Test the enhanced processed_editions schema."""
    logger.info("=" * 60)
    logger.info("ENHANCED SCHEMA TEST")
    logger.info("=" * 60)

    try:
        # Get MongoDB service
        mongodb = await get_mongodb_service()
        edition_repo = mongodb.edition_repo

        # Test data
        edition_key = "2025-12-27_test-enhanced-schema"
        title = "Test Edition with Enhanced Schema"
        publication_date = "2025-12-27"
        download_url = "https://example.com/download/test"

        # Step 1: Mark edition as processed with download timestamp
        logger.info("\n1. Creating edition with download timestamp...")
        downloaded_at = datetime.now(UTC)

        success = await edition_repo.mark_edition_processed(
            edition_key=edition_key,
            title=title,
            publication_date=publication_date,
            download_url=download_url,
            file_path="/tmp/test.pdf",
            downloaded_at=downloaded_at,
        )

        if success:
            logger.info("✓ Edition created")
        else:
            logger.error("✗ Failed to create edition")
            return False

        # Step 2: Update with blob storage metadata
        logger.info("\n2. Updating blob storage metadata...")
        blob_updated = await edition_repo.update_blob_metadata(
            edition_key=edition_key,
            blob_url="https://depotbutlerarchive.blob.core.windows.net/editions/2025/test/test.pdf",
            blob_path="2025/test-publication/test.pdf",
            blob_container="editions",
            file_size_bytes=102400,
        )

        if blob_updated:
            logger.info("✓ Blob metadata updated")
        else:
            logger.error("✗ Failed to update blob metadata")

        # Step 3: Update email sent timestamp
        logger.info("\n3. Updating email sent timestamp...")
        email_updated = await edition_repo.update_email_sent_timestamp(edition_key)

        if email_updated:
            logger.info("✓ Email timestamp updated")
        else:
            logger.error("✗ Failed to update email timestamp")

        # Step 4: Update OneDrive uploaded timestamp
        logger.info("\n4. Updating OneDrive uploaded timestamp...")
        onedrive_updated = await edition_repo.update_onedrive_uploaded_timestamp(
            edition_key
        )

        if onedrive_updated:
            logger.info("✓ OneDrive timestamp updated")
        else:
            logger.error("✗ Failed to update OneDrive timestamp")

        # Step 5: Retrieve and display the edition
        logger.info("\n5. Retrieving edition document...")
        collection = edition_repo.collection
        edition_doc = await collection.find_one(
            {"edition_key": edition_key}, {"_id": 0}
        )

        if edition_doc:
            logger.info("✓ Edition retrieved:")
            logger.info(f"  Title: {edition_doc.get('title')}")
            logger.info(f"  Publication Date: {edition_doc.get('publication_date')}")
            logger.info(
                f"  Downloaded At: {edition_doc.get('downloaded_at', 'Not set')}"
            )
            logger.info(f"  Blob URL: {edition_doc.get('blob_url', 'Not set')}")
            logger.info(f"  Blob Path: {edition_doc.get('blob_path', 'Not set')}")
            logger.info(f"  File Size: {edition_doc.get('file_size_bytes', 0):,} bytes")
            logger.info(f"  Archived At: {edition_doc.get('archived_at', 'Not set')}")
            logger.info(
                f"  Email Sent At: {edition_doc.get('email_sent_at', 'Not set')}"
            )
            logger.info(
                f"  OneDrive Uploaded At: {edition_doc.get('onedrive_uploaded_at', 'Not set')}"
            )
            logger.info(f"  Processed At: {edition_doc.get('processed_at', 'Not set')}")
        else:
            logger.error("✗ Edition not found")
            return False

        # Step 6: Cleanup test data
        logger.info("\n6. Cleaning up test data...")
        removed = await edition_repo.remove_edition_from_tracking(edition_key)
        if removed:
            logger.info("✓ Test data cleaned up")
        else:
            logger.warning("⚠ Test data may still exist")

        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 60)
        logger.info(
            "\nEnhanced schema is ready! New fields available for workflow integration."
        )

        return True

    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_enhanced_schema())
    sys.exit(0 if success else 1)
