"""
Edition tracking service to prevent duplicate processing.
Tracks processed editions using MongoDB for centralized tracking across environments.
"""

from depotbutler.db.mongodb import MongoDBService
from depotbutler.models import Edition, ProcessedEdition
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class EditionTrackingService:
    """
    Tracks processed editions to prevent duplicate downloads and emails.

    Uses MongoDB for persistence, which provides centralized tracking across
    local development and Azure Container Apps environments.
    """

    def __init__(
        self,
        mongodb: MongoDBService,
        retention_days: int = 90,
    ):
        """
        Initialize the edition tracker.

        Args:
            mongodb: MongoDB service instance
            retention_days: How many days to keep tracking records.
        """
        self.mongodb = mongodb
        self.retention_days = retention_days
        logger.info(
            "EditionTracker initialized with MongoDB backend (retention: %s days)",
            retention_days,
        )

    def _generate_edition_key(self, edition: Edition) -> str:
        """Generate a unique key for an edition."""
        # Use publication date + title for uniqueness
        return f"{edition.publication_date}_{edition.title}"

    async def is_already_processed(self, edition: Edition) -> bool:
        """
        Check if an edition has already been processed.

        Args:
            edition: The edition to check

        Returns:
            True if already processed, False otherwise
        """
        key = self._generate_edition_key(edition)
        is_processed = await self.mongodb.is_edition_processed(key)

        if is_processed:
            logger.info(
                "Edition already processed: %s (%s)",
                edition.title,
                edition.publication_date,
            )
        else:
            logger.debug("Edition not yet processed: %s", key)

        return is_processed

    async def mark_as_processed(
        self, edition: Edition, publication_id: str, file_path: str = ""
    ) -> None:
        """
        Mark an edition as processed.

        Args:
            edition: The edition that was processed
            publication_id: The publication identifier
            file_path: Optional path to the downloaded file
        """
        key = self._generate_edition_key(edition)

        success = await self.mongodb.mark_edition_processed(
            edition_key=key,
            publication_id=publication_id,
            title=edition.title,
            publication_date=edition.publication_date,
            download_url=edition.download_url,
            file_path=file_path,
        )

        if success:
            logger.info(
                "Marked edition as processed: %s (%s)",
                edition.title,
                edition.publication_date,
            )
        else:
            logger.warning("Failed to mark edition as processed: %s", key)

    async def get_processed_count(self) -> int:
        """Get the number of processed editions."""
        return await self.mongodb.get_processed_editions_count()

    async def get_recent_editions(self, days: int = 30) -> list[ProcessedEdition]:
        """
        Get editions processed in the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of processed editions from the last N days
        """
        editions_data = await self.mongodb.get_recent_processed_editions(days)

        editions = []
        for data in editions_data:
            edition = ProcessedEdition(
                title=data["title"],
                publication_date=data["publication_date"],
                download_url=data["download_url"],
                processed_at=data["processed_at"],
                file_path=data.get("file_path", ""),
            )
            editions.append(edition)

        return editions

    async def force_reprocess(self, edition: Edition) -> bool:
        """
        Remove an edition from tracking to allow reprocessing.

        Args:
            edition: The edition to allow reprocessing

        Returns:
            True if the edition was removed from tracking, False if it wasn't tracked
        """
        key = self._generate_edition_key(edition)
        removed = await self.mongodb.remove_edition_from_tracking(key)

        if removed:
            logger.info(
                "Removed edition from tracking - will be reprocessed: %s", edition.title
            )
        else:
            logger.info("Edition was not in tracking: %s", edition.title)

        return removed

    async def cleanup_old_entries(self) -> None:
        """Remove entries older than retention period."""
        await self.mongodb.cleanup_old_editions(self.retention_days)
