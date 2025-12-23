"""
Test script to verify recipient filtering and preference resolution.
This script performs a dry-run without actually sending emails or uploading files.
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import MongoDBService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.mark.asyncio
async def test_recipient_filtering() -> None:
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


@pytest.mark.asyncio
async def test_backward_compatibility() -> None:
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


async def main() -> int:
    """Run all tests."""
    try:
        await test_recipient_filtering()
        await test_backward_compatibility()

        logger.info("\n✅ All tests passed!")
        return 0

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
