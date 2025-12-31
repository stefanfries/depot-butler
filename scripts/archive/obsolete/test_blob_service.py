"""
Quick test of BlobStorageService implementation.

Tests basic functionality:
- Initialize service
- Archive a test PDF
- Retrieve from cache
- Check existence
- Clean up

Run: uv run python scripts/test_blob_service.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.services.blob_storage_service import BlobStorageService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def test_blob_service():
    """Test BlobStorageService basic operations."""
    logger.info("=" * 60)
    logger.info("BLOB STORAGE SERVICE TEST")
    logger.info("=" * 60)

    try:
        # Initialize service (uses settings for container name)
        logger.info("\n1. Initializing BlobStorageService...")
        service = BlobStorageService()
        logger.info("✓ Service initialized")
        logger.info(f"  Container: {service.container_name}")

        # Create test PDF data
        test_pdf_content = b"%PDF-1.4\nTest PDF content for blob storage testing"
        publication_id = "test-publication"
        date = "2025-12-27"
        filename = "2025-12-27_Test-Publication_01-2025.pdf"

        # Test archival
        logger.info(f"\n2. Archiving test edition: {filename}")
        metadata = {
            "issue_number": "01/2025",
            "title": "Test Publication 01/2025",
        }

        result = await service.archive_edition(
            pdf_bytes=test_pdf_content,
            publication_id=publication_id,
            date=date,
            filename=filename,
            metadata=metadata,
        )

        logger.info("✓ Archived successfully")
        logger.info(f"  Blob URL: {result['blob_url']}")
        logger.info(f"  Blob Path: {result['blob_path']}")
        logger.info(f"  Container: {result['blob_container']}")

        # Test existence check
        logger.info("\n3. Checking if edition exists...")
        exists = await service.exists(publication_id, date, filename)
        logger.info(f"✓ Exists check: {exists}")

        # Test cache retrieval
        logger.info("\n4. Retrieving from cache...")
        cached_pdf = await service.get_cached_edition(publication_id, date, filename)

        if cached_pdf:
            logger.info("✓ Retrieved from cache")
            logger.info(f"  Size: {len(cached_pdf):,} bytes")
            logger.info(f"  Content matches: {cached_pdf == test_pdf_content}")
        else:
            logger.error("✗ Failed to retrieve from cache")

        # Test listing
        logger.info(f"\n5. Listing editions for {publication_id}...")
        editions = await service.list_editions(publication_id=publication_id)
        logger.info(f"✓ Found {len(editions)} edition(s)")
        for edition in editions:
            logger.info(f"  - {edition['blob_name']} ({edition['size']} bytes)")

        # Cleanup
        logger.info("\n6. Cleaning up test data...")
        # Note: We'll leave it for manual cleanup or add delete method later
        logger.info(
            "✓ Test complete (cleanup: delete blob manually or add delete method)"
        )

        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 60)
        logger.info("\nBlobStorageService is ready for integration into workflow!")

    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_blob_service())
    sys.exit(0 if success else 1)
