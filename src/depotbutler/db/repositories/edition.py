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

    async def mark_edition_processed(
        self,
        edition_key: str,
        title: str,
        publication_date: str,
        download_url: str,
        file_path: str = "",
    ) -> bool:
        """
        Mark an edition as processed.

        Args:
            edition_key: Unique key for the edition
            title: Edition title
            publication_date: Publication date
            download_url: URL where edition was downloaded from
            file_path: Optional local file path
        """
        try:
            start_time = perf_counter()

            await self.collection.update_one(
                {"edition_key": edition_key},
                {
                    "$set": {
                        "edition_key": edition_key,
                        "title": title,
                        "publication_date": publication_date,
                        "download_url": download_url,
                        "file_path": file_path,
                        "processed_at": datetime.now(UTC),
                    }
                },
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
