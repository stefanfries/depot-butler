"""Edition tracking repository for MongoDB operations."""

from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

from depotbutler.db.repositories.base import BaseRepository
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class EditionRepository(BaseRepository):
    """Repository for edition tracking database operations."""

    @property
    def collection(self) -> Any:
        """Return the processed_editions collection."""
        return self.db.processed_editions

    async def is_edition_processed(self, edition_key: str) -> bool:
        """
        Check if an edition has already been processed.

        Args:
            edition_key: Unique key for the edition (publication_date_title)

        Returns:
            True if edition was already processed, False otherwise
        """
        try:
            result = await self.collection.find_one({"edition_key": edition_key})
            return result is not None

        except Exception as e:
            logger.error("Failed to check edition processing status: %s", e)
            return False

    async def get_edition(self, edition_key: str) -> dict[str, Any] | None:
        """
        Get an edition by its key.

        Args:
            edition_key: Unique key for the edition (publication_date_title)

        Returns:
            Edition document if found, None otherwise
        """
        try:
            result = await self.collection.find_one({"edition_key": edition_key})
            return dict(result) if result else None

        except Exception as e:
            logger.error("Failed to get edition: %s", e)
            return None

    async def mark_edition_processed(
        self,
        edition_key: str,
        publication_id: str,
        title: str,
        publication_date: str,
        download_url: str,
        file_path: str = "",
        downloaded_at: datetime | None = None,
        blob_url: str | None = None,
        blob_path: str | None = None,
        blob_container: str | None = None,
        file_size_bytes: int | None = None,
        archived_at: datetime | None = None,
        source: str = "scheduled_job",
    ) -> bool:
        """
        Mark an edition as processed with granular tracking.

        Args:
            edition_key: Unique key for the edition
            publication_id: Publication ID (e.g., 'megatrend-folger')
            title: Edition title
            publication_date: Publication date
            download_url: URL where edition was downloaded from
            file_path: Optional local file path (temp for scheduled/web, permanent for OneDrive)
            downloaded_at: When PDF was downloaded (optional)
            blob_url: Azure Blob Storage URL (optional)
            blob_path: Blob path within container (optional)
            blob_container: Blob container name (optional)
            file_size_bytes: File size in bytes (optional)
            archived_at: When archived to blob storage (optional)
            source: Ingestion source (scheduled_job|web_historical|onedrive_import)
        """
        try:
            start_time = perf_counter()

            update_doc = {
                "edition_key": edition_key,
                "publication_id": publication_id,
                "title": title,
                "publication_date": publication_date,
                "download_url": download_url,
                "source": source,
                "processed_at": datetime.now(UTC),
            }

            # Add optional fields if provided
            if file_path:  # Only set file_path if not empty (may already be set by update_file_path)
                update_doc["file_path"] = file_path
            if downloaded_at:
                update_doc["downloaded_at"] = downloaded_at
            if blob_url:
                update_doc["blob_url"] = blob_url
            if blob_path:
                update_doc["blob_path"] = blob_path
            if blob_container:
                update_doc["blob_container"] = blob_container
            if file_size_bytes is not None:
                update_doc["file_size_bytes"] = file_size_bytes
            if archived_at:
                update_doc["archived_at"] = archived_at

            await self.collection.update_one(
                {"edition_key": edition_key},
                {"$set": update_doc},
                upsert=True,
            )

            elapsed = perf_counter() - start_time
            logger.info(
                "Marked edition as processed [key=%s, time=%.2fms]",
                edition_key,
                elapsed * 1000,
            )
            return True

        except Exception as e:
            logger.error("Failed to mark edition as processed: %s", e)
            return False

    async def get_processed_editions_count(self) -> int:
        """Get total count of processed editions."""
        try:
            count = await self.collection.count_documents({})
            return int(count)
        except Exception as e:
            logger.error("Failed to get processed editions count: %s", e)
            return 0

    async def get_recent_processed_editions(self, days: int = 30) -> list[dict]:
        """
        Get editions processed in the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of processed edition documents
        """
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            cursor = self.collection.find(
                {"processed_at": {"$gte": cutoff_date}}, {"_id": 0}
            ).sort("processed_at", -1)

            editions = await cursor.to_list(length=None)
            return list(editions)

        except Exception as e:
            logger.error("Failed to get recent processed editions: %s", e)
            return []

    async def remove_edition_from_tracking(self, edition_key: str) -> bool:
        """
        Remove an edition from tracking to allow reprocessing.

        Args:
            edition_key: Unique key for the edition

        Returns:
            True if edition was removed, False if not found
        """
        try:
            result = await self.collection.delete_one({"edition_key": edition_key})
            return bool(result.deleted_count > 0)

        except Exception as e:
            logger.error("Failed to remove edition from tracking: %s", e)
            return False

    async def cleanup_old_editions(self, days_to_keep: int = 90) -> None:
        """
        Remove editions older than specified days.

        Args:
            days_to_keep: Number of days to retain tracking data
        """
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)

            result = await self.collection.delete_many(
                {"processed_at": {"$lt": cutoff_date}}
            )

            if result.deleted_count > 0:
                logger.info(
                    "Cleaned up %s old edition tracking entries", result.deleted_count
                )

        except Exception as e:
            logger.error("Failed to cleanup old editions: %s", e)

    async def update_email_sent_timestamp(
        self, edition_key: str, timestamp: datetime | None = None
    ) -> bool:
        """
        Update email_sent_at timestamp for an edition.

        Args:
            edition_key: Unique key for the edition
            timestamp: Timestamp to set (defaults to now)

        Returns:
            True if updated successfully
        """
        try:
            result = await self.collection.update_one(
                {"edition_key": edition_key},
                {"$set": {"email_sent_at": timestamp or datetime.now(UTC)}},
            )
            return bool(result.modified_count > 0)
        except Exception as e:
            logger.error("Failed to update email_sent_at timestamp: %s", e)
            return False

    async def update_onedrive_uploaded_timestamp(
        self, edition_key: str, timestamp: datetime | None = None
    ) -> bool:
        """
        Update onedrive_uploaded_at timestamp for an edition.

        Args:
            edition_key: Unique key for the edition
            timestamp: Timestamp to set (defaults to now)

        Returns:
            True if updated successfully
        """
        try:
            result = await self.collection.update_one(
                {"edition_key": edition_key},
                {"$set": {"onedrive_uploaded_at": timestamp or datetime.now(UTC)}},
            )
            return bool(result.modified_count > 0)
        except Exception as e:
            logger.error("Failed to update onedrive_uploaded_at timestamp: %s", e)
            return False

    async def update_file_path(self, edition_key: str, file_path: str) -> bool:
        """
        Update file_path for an edition (e.g., when OneDrive path is determined).

        Args:
            edition_key: Unique key for the edition
            file_path: OneDrive file path to set

        Returns:
            True if updated successfully
        """
        try:
            result = await self.collection.update_one(
                {"edition_key": edition_key},
                {"$set": {"file_path": file_path}},
            )
            return bool(result.modified_count > 0)
        except Exception as e:
            logger.error("Failed to update file_path: %s", e)
            return False

    async def update_blob_metadata(
        self,
        edition_key: str,
        blob_url: str,
        blob_path: str,
        blob_container: str,
        file_size_bytes: int,
        archived_at: datetime | None = None,
    ) -> bool:
        """
        Update blob storage metadata for an edition.

        Args:
            edition_key: Unique key for the edition
            blob_url: Azure Blob Storage URL
            blob_path: Blob path within container
            blob_container: Blob container name
            file_size_bytes: File size in bytes
            archived_at: Archive timestamp (defaults to now)

        Returns:
            True if updated successfully
        """
        try:
            result = await self.collection.update_one(
                {"edition_key": edition_key},
                {
                    "$set": {
                        "blob_url": blob_url,
                        "blob_path": blob_path,
                        "blob_container": blob_container,
                        "file_size_bytes": file_size_bytes,
                        "archived_at": archived_at or datetime.now(UTC),
                    }
                },
            )
            return bool(result.modified_count > 0)
        except Exception as e:
            logger.error("Failed to update blob metadata: %s", e)
            return False

    async def update_edition_metadata(
        self, edition_key: str, updates: dict[str, Any]
    ) -> bool:
        """
        Update arbitrary metadata fields for an edition without reprocessing.

        Use this to modify specific fields (e.g., source, file_path, timestamps)
        without triggering the full workflow (downloads, emails, uploads).

        Args:
            edition_key: Unique key for the edition
            updates: Dictionary of field names and values to update

        Returns:
            True if updated successfully, False if edition not found or error

        Example:
            await repo.update_edition_metadata(
                "2025-12-17_DER AKTIONÄR 52/25 + 01/26",
                {"source": "web_historical", "file_path": "OneDrive/path/..."}
            )
        """
        try:
            result = await self.collection.update_one(
                {"edition_key": edition_key}, {"$set": updates}
            )
            if result.matched_count == 0:
                logger.warning(
                    "Edition not found for metadata update [key=%s]", edition_key
                )
                return False

            logger.info(
                "Updated edition metadata [key=%s, fields=%s]",
                edition_key,
                list(updates.keys()),
            )
            return bool(result.modified_count > 0)

        except Exception as e:
            logger.error("Failed to update edition metadata: %s", e)
            return False
