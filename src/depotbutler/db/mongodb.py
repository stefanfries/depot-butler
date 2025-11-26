"""MongoDB database operations for depot-butler using Motor (async driver)."""

from datetime import datetime, timedelta, timezone
from time import perf_counter
from types import TracebackType
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, OperationFailure

from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class MongoDBService:
    """Service class for async MongoDB operations using Motor with context manager support."""

    def __init__(self):
        """Initialize MongoDB connection."""
        self.settings = Settings()
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self._connected = False

    async def __aenter__(self):
        """Async context manager entry - establishes connection."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ):
        """Async context manager exit - closes connection."""
        await self.close()

    async def connect(self):
        """Establish connection to MongoDB."""
        if self._connected:
            return

        try:
            start_time = perf_counter()

            connection_string = self.settings.mongodb.connection_string
            # Extract host for logging (hide credentials)
            host = (
                connection_string.split("@")[-1].split("/")[0]
                if "@" in connection_string
                else "localhost"
            )

            self.client = AsyncIOMotorClient(
                connection_string, serverSelectionTimeoutMS=5000
            )

            # Test connection
            await self.client.admin.command("ping")

            self.db = self.client[self.settings.mongodb.name]
            self._connected = True

            elapsed = perf_counter() - start_time
            logger.info(
                "Successfully connected to MongoDB [host=%s, db=%s, time=%.2fms]",
                host,
                self.settings.mongodb.name,
                elapsed * 1000,
            )

        except ConnectionFailure as e:
            logger.error("Failed to connect to MongoDB: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error connecting to MongoDB: %s", e)
            raise

    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Closed MongoDB connection")

    async def get_active_recipients(self) -> list[dict]:
        """
        Fetch all active recipients from MongoDB.

        Returns:
            List of recipient documents with email, first_name, last_name
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            cursor = self.db.recipients.find(  # type: ignore
                {"active": True},
                {
                    "email": 1,
                    "first_name": 1,
                    "last_name": 1,
                    "recipient_type": 1,
                    "_id": 0,
                },
            ).sort("email", 1)

            recipients = await cursor.to_list(length=None)

            elapsed = perf_counter() - start_time
            logger.info(
                "Retrieved %s active recipients from MongoDB [query_time=%.2fms]",
                len(recipients),
                elapsed * 1000,
            )
            return recipients

        except OperationFailure as e:
            logger.error("Failed to fetch recipients from MongoDB: %s", e)
            return []
        except Exception as e:
            logger.error("Unexpected error fetching recipients: %s", e)
            return []

    async def update_recipient_stats(self, email: str):
        """
        Update send statistics for a recipient.

        Args:
            email: Recipient email address
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            result = await self.db.recipients.update_one(  # type: ignore
                {"email": email},
                {
                    "$set": {"last_sent_at": datetime.now(timezone.utc)},
                    "$inc": {"send_count": 1},
                },
            )

            elapsed = perf_counter() - start_time
            if result.modified_count > 0:
                logger.info(
                    "Updated stats for recipient [email=%s, update_time=%.2fms]",
                    email,
                    elapsed * 1000,
                )
            else:
                logger.warning(
                    "Recipient not found in database [email=%s, update_time=%.2fms]",
                    email,
                    elapsed * 1000,
                )

        except Exception as e:
            logger.error("Failed to update recipient stats for %s: %s", email, e)

    async def is_edition_processed(self, edition_key: str) -> bool:
        """
        Check if an edition has already been processed.

        Args:
            edition_key: Unique key for the edition (publication_date_title)

        Returns:
            True if edition was already processed, False otherwise
        """
        if not self._connected:
            await self.connect()

        try:
            result = await self.db.processed_editions.find_one(  # type: ignore
                {"edition_key": edition_key}
            )
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
    ):
        """
        Mark an edition as processed.

        Args:
            edition_key: Unique key for the edition
            title: Edition title
            publication_date: Publication date
            download_url: URL where edition was downloaded from
            file_path: Optional local file path
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            await self.db.processed_editions.update_one(  # type: ignore
                {"edition_key": edition_key},
                {
                    "$set": {
                        "edition_key": edition_key,
                        "title": title,
                        "publication_date": publication_date,
                        "download_url": download_url,
                        "file_path": file_path,
                        "processed_at": datetime.now(timezone.utc),
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
        if not self._connected:
            await self.connect()

        try:
            count = await self.db.processed_editions.count_documents({})  # type: ignore
            return count
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
        if not self._connected:
            await self.connect()

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            cursor = self.db.processed_editions.find(  # type: ignore
                {"processed_at": {"$gte": cutoff_date}}, {"_id": 0}
            ).sort("processed_at", -1)

            editions = await cursor.to_list(length=None)
            return editions

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
        if not self._connected:
            await self.connect()

        try:
            result = await self.db.processed_editions.delete_one(  # type: ignore
                {"edition_key": edition_key}
            )
            return result.deleted_count > 0

        except Exception as e:
            logger.error("Failed to remove edition from tracking: %s", e)
            return False

    async def cleanup_old_editions(self, days_to_keep: int = 90):
        """
        Remove editions older than specified days.

        Args:
            days_to_keep: Number of days to retain tracking data
        """
        if not self._connected:
            await self.connect()

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

            result = await self.db.processed_editions.delete_many(  # type: ignore
                {"processed_at": {"$lt": cutoff_date}}
            )

            if result.deleted_count > 0:
                logger.info(
                    "Cleaned up %s old edition tracking entries", result.deleted_count
                )

        except Exception as e:
            logger.error("Failed to cleanup old editions: %s", e)


# Singleton instance
_mongodb_service: Optional[MongoDBService] = None


async def get_mongodb_service() -> MongoDBService:
    """Get or create the MongoDB service singleton."""
    global _mongodb_service
    if _mongodb_service is None:
        _mongodb_service = MongoDBService()
        await _mongodb_service.connect()
    return _mongodb_service


async def get_active_recipients() -> list[dict]:
    """
    Convenience function to get active recipients.

    Returns:
        List of recipient dicts with email, first_name, last_name
    """
    service = await get_mongodb_service()
    return await service.get_active_recipients()


async def update_recipient_stats(email: str):
    """
    Convenience function to update recipient statistics.

    Args:
        email: Recipient email address
    """
    service = await get_mongodb_service()
    await service.update_recipient_stats(email)


async def close_mongodb_connection():
    """Close the MongoDB connection."""
    global _mongodb_service
    if _mongodb_service:
        await _mongodb_service.close()
        _mongodb_service = None
