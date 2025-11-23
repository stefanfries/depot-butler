"""MongoDB database operations for depot-butler using Motor (async driver)."""

from datetime import datetime, timezone
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
            from time import perf_counter

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
            from time import perf_counter

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
            from time import perf_counter

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
