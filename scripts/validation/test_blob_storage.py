"""
Test Azure Blob Storage setup and operations.

This script validates that we can:
1. Connect to Azure Blob Storage
2. Create container (editions)
3. Upload test PDF
4. Download and verify
5. List blobs
6. Delete test data

Run: uv run python scripts/validation/test_blob_storage.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import asyncio
import os

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

# Explicitly load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)
print(f"Loading .env from: {env_path}")
print(
    f"AZURE_STORAGE_CONNECTION_STRING loaded: {bool(os.getenv('AZURE_STORAGE_CONNECTION_STRING'))}"
)

settings = Settings()

logger = get_logger(__name__)


def get_blob_service_client() -> BlobServiceClient:
    """Create Blob Service Client from connection string."""
    # For now, use connection string (can switch to managed identity in production)
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

    if not connection_string:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set in environment")

    return BlobServiceClient.from_connection_string(connection_string)


async def test_connection():
    """Test connection to Azure Blob Storage."""
    logger.info("Testing Azure Blob Storage connection...")

    try:
        client = get_blob_service_client()

        # List containers (simple operation to verify connection)
        containers = list(client.list_containers())
        logger.info("✅ Connected successfully")
        logger.info(f"Existing containers: {[c.name for c in containers]}")
        return client

    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        raise


async def test_container_creation(
    client: BlobServiceClient, container_name: str = "editions-test"
):
    """Test creating a container."""
    logger.info(f"\nTesting container creation: {container_name}")

    try:
        container_client = client.create_container(
            container_name,
            public_access=None,  # Private
        )
        logger.info(f"✅ Container '{container_name}' created")
        return container_client

    except ResourceExistsError:
        logger.info(f"✅ Container '{container_name}' already exists")
        return client.get_container_client(container_name)

    except Exception as e:
        logger.error(f"❌ Container creation failed: {e}")
        raise


async def test_upload(container_client, test_content: bytes = b"Test PDF content"):
    """Test uploading a blob."""
    logger.info("\nTesting blob upload...")

    blob_name = "test/2025-12-26_Test_01-2025.pdf"

    try:
        blob_client = container_client.get_blob_client(blob_name)

        # Upload with metadata
        blob_client.upload_blob(
            test_content,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/pdf"),
            metadata={
                "publication_id": "test",
                "publication_date": "2025-12-26",
                "issue_number": "01/2025",
            },
        )

        logger.info(f"✅ Uploaded blob: {blob_name}")
        logger.info(f"   Size: {len(test_content)} bytes")
        return blob_name

    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        raise


async def test_download(container_client, blob_name: str, expected_content: bytes):
    """Test downloading a blob."""
    logger.info("\nTesting blob download...")

    try:
        blob_client = container_client.get_blob_client(blob_name)

        # Download
        download_stream = blob_client.download_blob()
        downloaded_content = download_stream.readall()

        # Verify
        if downloaded_content == expected_content:
            logger.info(f"✅ Downloaded and verified: {blob_name}")
            logger.info(f"   Size: {len(downloaded_content)} bytes")
        else:
            logger.error("❌ Content mismatch!")
            logger.error(f"   Expected: {len(expected_content)} bytes")
            logger.error(f"   Got: {len(downloaded_content)} bytes")
            return False

        # Check properties and metadata
        properties = blob_client.get_blob_properties()
        logger.info(f"   Content type: {properties.content_settings.content_type}")
        logger.info(f"   Metadata: {properties.metadata}")

        return True

    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        raise


async def test_list_blobs(container_client):
    """Test listing blobs."""
    logger.info("\nTesting blob listing...")

    try:
        blobs = list(container_client.list_blobs(name_starts_with="test/"))

        logger.info(f"✅ Listed {len(blobs)} blobs")
        for blob in blobs:
            logger.info(f"   - {blob.name} ({blob.size} bytes)")

        return len(blobs)

    except Exception as e:
        logger.error(f"❌ Listing failed: {e}")
        raise


async def test_delete(container_client, blob_name: str):
    """Test deleting a blob."""
    logger.info("\nTesting blob deletion...")

    try:
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.delete_blob()

        logger.info(f"✅ Deleted blob: {blob_name}")
        return True

    except ResourceNotFoundError:
        logger.warning(f"⚠️ Blob not found (already deleted?): {blob_name}")
        return True

    except Exception as e:
        logger.error(f"❌ Deletion failed: {e}")
        raise


async def cleanup_test_container(
    client: BlobServiceClient, container_name: str = "editions-test"
):
    """Clean up test container."""
    logger.info(f"\nCleaning up test container: {container_name}")

    try:
        client.delete_container(container_name)
        logger.info("✅ Test container deleted")

    except ResourceNotFoundError:
        logger.info("✅ Test container already deleted")

    except Exception as e:
        logger.warning(f"⚠️ Cleanup failed: {e}")


async def main():
    """Run all Blob Storage validation tests."""
    logger.info("=" * 60)
    logger.info("AZURE BLOB STORAGE VALIDATION")
    logger.info("=" * 60)

    test_content = b"Test PDF content for validation"
    container_name = "editions-test"

    try:
        # Test 1: Connection
        client = await test_connection()

        # Test 2: Container creation
        container_client = await test_container_creation(client, container_name)

        # Test 3: Upload
        blob_name = await test_upload(container_client, test_content)

        # Test 4: List
        await test_list_blobs(container_client)

        # Test 5: Download
        await test_download(container_client, blob_name, test_content)

        # Test 6: Delete
        await test_delete(container_client, blob_name)

        # Cleanup
        await cleanup_test_container(client, container_name)

        logger.info("=" * 60)
        logger.info("VALIDATION COMPLETE")
        logger.info("=" * 60)
        logger.info("\n✅ All tests passed!")
        logger.info("\nNext steps:")
        logger.info("1. Create production 'editions' container")
        logger.info("2. Configure lifecycle policy (Cool tier after upload)")
        logger.info("3. Implement BlobStorageService class")
        logger.info("4. Proceed to test_yfinance.py (optional for Phase 2)")

    except Exception as e:
        logger.error(f"\n❌ Validation failed: {e}")
        logger.info("\nTroubleshooting:")
        logger.info("1. Check AZURE_STORAGE_CONNECTION_STRING in .env")
        logger.info("2. Verify Azure Storage account exists")
        logger.info("3. Check network connectivity")
        raise


if __name__ == "__main__":
    asyncio.run(main())
