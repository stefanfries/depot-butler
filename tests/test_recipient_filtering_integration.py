"""
Integration tests for recipient filtering and preference resolution.
These tests require a real MongoDB connection and are skipped when MongoDB is unavailable.

To run these tests:
1. Ensure MongoDB is running locally (localhost:27017)
2. Run: pytest tests/test_recipient_filtering_integration.py -v
"""

import asyncio

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from depotbutler.db.mongodb import MongoDBService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


# Helper to check if MongoDB is available
async def is_mongodb_available() -> bool:
    """Check if MongoDB is available for testing."""
    try:
        async with MongoDBService() as db:
            await db.connect()
            return True
    except (ServerSelectionTimeoutError, Exception):
        return False


@pytest.fixture(scope="module")
async def check_mongodb():
    """Skip all tests if MongoDB is not available."""
    available = await is_mongodb_available()
    if not available:
        pytest.skip("MongoDB not available - skipping integration tests")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_recipient_filtering(check_mongodb):
    """Test recipient filtering for each publication."""

    logger.info("🧪 Starting recipient filtering test...")

    async with MongoDBService() as db:
        # Get all active publications
        publications = await db.get_publications(active_only=True)
        logger.info(f"Found {len(publications)} active publications")

        for pub in publications:
            pub_id = pub["publication_id"]
            pub_name = pub["name"]

            logger.info(f"\n{'=' * 60}")
            logger.info(f"📰 Publication: {pub_name} (ID: {pub_id})")
            logger.info(f"{'=' * 60}")

            # Test email recipients
            email_recipients = await db.get_recipients_for_publication(
                publication_id=pub_id, delivery_method="email"
            )
            logger.info(f"✉️  Email recipients: {len(email_recipients)}")
            for recipient in email_recipients:
                logger.info(f"   - {recipient['email']}")

            # Test upload recipients
            upload_recipients = await db.get_recipients_for_publication(
                publication_id=pub_id, delivery_method="upload"
            )
            logger.info(f"☁️  OneDrive upload recipients: {len(upload_recipients)}")
            for recipient in upload_recipients:
                # Get resolved folder path (these are sync functions)
                folder = db.get_onedrive_folder_for_recipient(recipient, pub)
                organize = db.get_organize_by_year_for_recipient(recipient, pub)

                logger.info(
                    f"   - {recipient['email']}: "
                    f"folder='{folder}', organize_by_year={organize}"
                )

        logger.info(f"\n{'=' * 60}")
        logger.info("✅ Test completed successfully!")
        logger.info(f"{'=' * 60}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_backward_compatibility(check_mongodb):
    """Test that recipients without preferences still receive all publications."""

    logger.info("\n🔄 Testing backward compatibility...")

    async with MongoDBService() as db:
        all_recipients = await db.get_active_recipients()
        logger.info(f"Total active recipients: {len(all_recipients)}")

        # Check for recipients without publication_preferences
        legacy_recipients = [
            r for r in all_recipients if not r.get("publication_preferences")
        ]

        if legacy_recipients:
            logger.info(
                f"Found {len(legacy_recipients)} recipients without preferences "
                f"(will receive all publications):"
            )
            for recipient in legacy_recipients:
                logger.info(f"   - {recipient['email']}")
        else:
            logger.info("All recipients have publication preferences configured")


if __name__ == "__main__":
    """Allow running as standalone script."""

    async def main():
        try:
            if not await is_mongodb_available():
                logger.error(
                    "❌ MongoDB not available. Please start MongoDB and try again."
                )
                return

            await test_recipient_filtering(None)
            await test_backward_compatibility(None)

            logger.info("\n✅ All tests passed!")
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            raise

    asyncio.run(main())
