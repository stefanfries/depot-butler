"""
Azure Blob Storage service for PDF archival.

Handles long-term storage of edition PDFs in Azure Blob Storage (Cool tier).
Provides caching layer to avoid repeated downloads during development.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings

from depotbutler.exceptions import ConfigurationError, TransientError, UploadError
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
settings = Settings()


class BlobStorageService:
    """Service for archiving PDFs to Azure Blob Storage."""

    def __init__(self, container_name: str | None = None) -> None:
        """
        Initialize blob storage service.

        Args:
            container_name: Name of the blob container (default: from settings)

        Raises:
            ConfigurationError: If Azure Storage connection string not configured
        """
        self.settings = settings  # Reference to module-level settings
        self.container_name = (
            container_name or self.settings.blob_storage.container_name
        )

        # Get connection string from settings
        connection_string_secret = self.settings.blob_storage.connection_string
        if connection_string_secret is None:
            raise ConfigurationError(
                "Azure Storage connection string not configured. "
                "Set AZURE_STORAGE_CONNECTION_STRING in .env file. "
                "See docs/VALIDATION_SETUP.md for setup instructions."
            )

        self.connection_string = connection_string_secret.get_secret_value()

        if not self.connection_string:
            raise ConfigurationError(
                "Azure Storage connection string is empty. "
                "Set AZURE_STORAGE_CONNECTION_STRING in .env file. "
                "See docs/VALIDATION_SETUP.md for setup instructions."
            )

        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
            self.container_client = self.blob_service_client.get_container_client(
                self.container_name
            )

            # Ensure container exists
            if not self.container_client.exists():
                logger.info(f"Creating container: {self.container_name}")
                self.container_client.create_container()
                logger.info(f"✓ Container '{self.container_name}' created")

        except Exception as e:
            raise ConfigurationError(
                f"Failed to initialize Azure Blob Storage client: {e}"
            ) from e

    def _generate_blob_path(self, publication_id: str, date: str, filename: str) -> str:
        """
        Generate blob path following convention: {year}/{publication_id}/{filename}.

        Args:
            publication_id: Publication identifier (e.g., "megatrend-folger")
            date: Publication date in YYYY-MM-DD format
            filename: PDF filename (e.g., "2025-12-18_Megatrend-Folger_51-2025.pdf")

        Returns:
            Blob path (e.g., "2025/megatrend-folger/2025-12-18_Megatrend-Folger_51-2025.pdf")
        """
        year = date.split("-")[0]
        return f"{year}/{publication_id}/{filename}"

    async def archive_edition(
        self,
        pdf_bytes: bytes,
        publication_id: str,
        date: str,
        filename: str,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """
        Archive edition PDF to blob storage.

        Args:
            pdf_bytes: PDF file content
            publication_id: Publication identifier
            date: Publication date in YYYY-MM-DD format
            filename: PDF filename
            metadata: Optional metadata to store with blob

        Returns:
            Dictionary with blob URL, path, and upload timestamp

        Raises:
            UploadError: If upload fails
        """
        blob_path = self._generate_blob_path(publication_id, date, filename)

        try:
            blob_client = self.container_client.get_blob_client(blob_path)

            # Prepare metadata
            blob_metadata = metadata or {}
            blob_metadata.update(
                {
                    "publication_id": publication_id,
                    "publication_date": date,
                    "archived_at": datetime.now(UTC).isoformat(),
                }
            )

            # Upload with PDF content type
            content_settings = ContentSettings(content_type="application/pdf")

            blob_client.upload_blob(
                pdf_bytes,
                overwrite=True,
                content_settings=content_settings,
                metadata=blob_metadata,
            )

            blob_url = blob_client.url
            file_size = len(pdf_bytes)

            logger.info(f"✓ Archived to blob storage: {blob_path}")
            logger.info(f"  URL: {blob_url}")
            logger.info(f"  Size: {file_size:,} bytes")

            return {
                "blob_url": blob_url,
                "blob_path": blob_path,
                "blob_container": self.container_name,
                "file_size_bytes": str(file_size),
                "archived_at": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to archive edition to blob storage: {e}")
            raise UploadError(f"Blob storage upload failed: {e}") from e

    async def get_cached_edition(
        self, publication_id: str, date: str, filename: str
    ) -> bytes | None:
        """
        Retrieve edition PDF from blob storage cache.

        Args:
            publication_id: Publication identifier
            date: Publication date in YYYY-MM-DD format
            filename: PDF filename

        Returns:
            PDF bytes if found, None if not in cache

        Raises:
            TransientError: If download fails
        """
        blob_path = self._generate_blob_path(publication_id, date, filename)

        try:
            blob_client = self.container_client.get_blob_client(blob_path)

            if not blob_client.exists():
                logger.debug(f"Edition not in cache: {blob_path}")
                return None

            # Download blob
            download_stream = blob_client.download_blob()
            pdf_bytes: bytes = download_stream.readall()  # type: ignore[assignment]

            logger.info(f"✓ Retrieved from cache: {blob_path}")
            logger.info(f"  Size: {len(pdf_bytes):,} bytes")

            return pdf_bytes

        except ResourceNotFoundError:
            logger.debug(f"Edition not in cache: {blob_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve from cache: {e}")
            raise TransientError(f"Blob storage download failed: {e}") from e

    async def exists(self, publication_id: str, date: str, filename: str) -> bool:
        """
        Check if edition exists in blob storage.

        Args:
            publication_id: Publication identifier
            date: Publication date in YYYY-MM-DD format
            filename: PDF filename

        Returns:
            True if blob exists, False otherwise
        """
        blob_path = self._generate_blob_path(publication_id, date, filename)

        try:
            blob_client = self.container_client.get_blob_client(blob_path)
            return bool(blob_client.exists())
        except Exception as e:
            logger.warning(f"Failed to check blob existence: {e}")
            return False

    async def list_editions(
        self, publication_id: str | None = None, year: str | None = None
    ) -> list[dict[str, str]]:
        """
        List editions in blob storage.

        Args:
            publication_id: Filter by publication ID (optional)
            year: Filter by year (optional)

        Returns:
            List of dictionaries with blob metadata
        """
        try:
            prefix = ""
            if year and publication_id:
                prefix = f"{year}/{publication_id}/"
            elif year:
                prefix = f"{year}/"
            elif publication_id:
                # Need to list all and filter (no year-independent prefix)
                pass

            blobs = self.container_client.list_blobs(name_starts_with=prefix)

            results = []
            for blob in blobs:
                # If publication_id specified without year, filter manually
                if (
                    publication_id
                    and not year
                    and f"/{publication_id}/" not in blob.name
                ):
                    continue

                results.append(
                    {
                        "blob_name": blob.name,
                        "blob_url": f"{self.container_client.url}/{blob.name}",
                        "size": str(blob.size),
                        "created": blob.creation_time.isoformat()
                        if blob.creation_time
                        else "",
                        "last_modified": blob.last_modified.isoformat()
                        if blob.last_modified
                        else "",
                    }
                )

            logger.info(f"Listed {len(results)} blobs (prefix: '{prefix}')")
            return results

        except Exception as e:
            logger.error(f"Failed to list blobs: {e}")
            return []

    async def archive_from_file(
        self,
        file_path: Path,
        publication_id: str,
        date: str,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """
        Archive edition from local file.

        Args:
            file_path: Path to local PDF file
            publication_id: Publication identifier
            date: Publication date in YYYY-MM-DD format
            metadata: Optional metadata to store with blob

        Returns:
            Dictionary with blob URL, path, and upload timestamp

        Raises:
            UploadError: If upload fails
        """
        try:
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()

            filename = file_path.name
            return await self.archive_edition(
                pdf_bytes, publication_id, date, filename, metadata
            )

        except FileNotFoundError as e:
            raise UploadError(f"File not found: {file_path}") from e
        except Exception as e:
            raise UploadError(f"Failed to archive from file: {e}") from e

    async def download_to_file(
        self, publication_id: str, date: str, filename: str, destination: Path
    ) -> bool:
        """
        Download edition from blob storage to local file.

        Args:
            publication_id: Publication identifier
            date: Publication date in YYYY-MM-DD format
            filename: PDF filename
            destination: Local file path to save to

        Returns:
            True if successful, False if not found
        """
        pdf_bytes = await self.get_cached_edition(publication_id, date, filename)

        if pdf_bytes is None:
            return False

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, "wb") as f:
                f.write(pdf_bytes)

            logger.info(f"✓ Downloaded to: {destination}")
            return True

        except Exception as e:
            logger.error(f"Failed to write downloaded file: {e}")
            raise UploadError(f"Failed to save downloaded file: {e}") from e
