"""MongoDB database operations for depot-butler using Motor (async driver)."""

from datetime import UTC, datetime, timedelta
from time import perf_counter
from types import TracebackType

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
        self.client: AsyncIOMotorClient | None = None
        self.db = None
        self._connected = False

    async def __aenter__(self):
        """Async context manager entry - establishes connection."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
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

    async def update_recipient_stats(
        self, email: str, publication_id: str | None = None
    ):
        """
        Update send statistics for a recipient.

        Args:
            email: Recipient email address
            publication_id: Optional publication ID for per-publication tracking
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            if publication_id:
                # Update per-publication stats
                result = await self.db.recipients.update_one(  # type: ignore
                    {
                        "email": email,
                        "publication_preferences.publication_id": publication_id,
                    },
                    {
                        "$set": {
                            "publication_preferences.$.last_sent_at": datetime.now(UTC)
                        },
                        "$inc": {"publication_preferences.$.send_count": 1},
                    },
                )
            else:
                # Legacy: Update global stats (for backward compatibility)
                result = await self.db.recipients.update_one(  # type: ignore
                    {"email": email},
                    {
                        "$set": {"last_sent_at": datetime.now(UTC)},
                        "$inc": {"send_count": 1},
                    },
                )

            elapsed = perf_counter() - start_time
            if result.modified_count > 0:
                context = (
                    f"publication={publication_id}" if publication_id else "global"
                )
                logger.info(
                    "Updated stats for recipient [email=%s, %s, update_time=%.2fms]",
                    email,
                    context,
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

    async def get_recipients_for_publication(
        self, publication_id: str, delivery_method: str
    ) -> list[dict]:
        """
        Get recipients who have enabled a specific delivery method for a publication.

        This function implements an explicit opt-in model:
        - Recipients with empty publication_preferences receive NOTHING (must opt-in)
        - Recipients must have explicit preference with enabled=True for the publication
        - This ensures intentional delivery and prevents unwanted emails

        Args:
            publication_id: The publication ID to filter by
            delivery_method: Either "email" or "upload"

        Returns:
            List of recipient dictionaries with preference details
        """
        if not self._connected:
            await self.connect()

        if delivery_method not in ("email", "upload"):
            logger.error(f"Invalid delivery_method: {delivery_method}")
            return []

        try:
            start_time = perf_counter()

            # MongoDB query: Get recipients who have explicit preference for this publication
            # Empty publication_preferences = receive nothing (opt-in model)
            field_name = f"{delivery_method}_enabled"

            query = {
                "active": True,
                # Must have explicit preference for this publication with method enabled
                "publication_preferences": {
                    "$elemMatch": {
                        "publication_id": publication_id,
                        "enabled": True,
                        field_name: True,
                    }
                },
            }

            projection = {
                "email": 1,
                "first_name": 1,
                "last_name": 1,
                "recipient_type": 1,
                "publication_preferences": 1,
                "_id": 0,
            }

            cursor = self.db.recipients.find(query, projection).sort("email", 1)  # type: ignore
            recipients = await cursor.to_list(length=None)

            elapsed = perf_counter() - start_time
            logger.info(
                "Retrieved %s recipients for publication=%s, method=%s [query_time=%.2fms]",
                len(recipients),
                publication_id,
                delivery_method,
                elapsed * 1000,
            )
            return recipients

        except Exception as e:
            logger.error(
                f"Failed to get recipients for publication {publication_id}: {e}"
            )
            return []

    def get_onedrive_folder_for_recipient(
        self, recipient: dict, publication: dict
    ) -> str:
        """
        Resolve OneDrive folder path for a recipient and publication.

        Priority:
        1. Recipient's custom_onedrive_folder (if set in preferences)
        2. Publication's default_onedrive_folder

        Args:
            recipient: Recipient document with publication_preferences
            publication: Publication document

        Returns:
            Resolved folder path
        """
        # Check if recipient has custom folder for this publication
        preferences = recipient.get("publication_preferences", [])
        for pref in preferences:
            if pref.get("publication_id") == publication["publication_id"]:
                custom_folder = pref.get("custom_onedrive_folder")
                if custom_folder:
                    logger.debug(
                        f"Using custom folder for {recipient['email']}: {custom_folder}"
                    )
                    return custom_folder
                break

        # Fall back to publication default
        default_folder = publication.get("default_onedrive_folder", "")
        logger.debug(
            f"Using publication default folder for {recipient['email']}: {default_folder}"
        )
        return default_folder

    def get_organize_by_year_for_recipient(
        self, recipient: dict, publication: dict
    ) -> bool:
        """
        Resolve organize_by_year setting for a recipient and publication.

        Priority:
        1. Recipient's organize_by_year preference (if not None)
        2. Publication's organize_by_year setting
        3. Default to True

        Args:
            recipient: Recipient document with publication_preferences
            publication: Publication document

        Returns:
            Whether to organize uploads by year
        """
        # Check if recipient has organize_by_year override for this publication
        preferences = recipient.get("publication_preferences", [])
        for pref in preferences:
            if pref.get("publication_id") == publication["publication_id"]:
                organize_by_year = pref.get("organize_by_year")
                if organize_by_year is not None:
                    logger.debug(
                        f"Using recipient organize_by_year override for {recipient['email']}: {organize_by_year}"
                    )
                    return organize_by_year
                break

        # Fall back to publication setting, default to True
        publication_setting = publication.get("organize_by_year", True)
        logger.debug(
            f"Using publication organize_by_year for {recipient['email']}: {publication_setting}"
        )
        return publication_setting

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
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

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
            cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)

            result = await self.db.processed_editions.delete_many(  # type: ignore
                {"processed_at": {"$lt": cutoff_date}}
            )

            if result.deleted_count > 0:
                logger.info(
                    "Cleaned up %s old edition tracking entries", result.deleted_count
                )

        except Exception as e:
            logger.error("Failed to cleanup old editions: %s", e)

    async def get_auth_cookie(self) -> str | None:
        """
        Get the authentication cookie from MongoDB config collection.

        Returns:
            Cookie value string if found, None otherwise
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            config_doc = await self.db.config.find_one(  # type: ignore
                {"_id": "auth_cookie"}
            )

            elapsed_ms = (perf_counter() - start_time) * 1000

            if config_doc and config_doc.get("cookie_value"):
                cookie_value = config_doc["cookie_value"]
                logger.info(
                    "Retrieved auth cookie from MongoDB [length=%d, time=%.2fms]",
                    len(cookie_value),
                    elapsed_ms,
                )
                return cookie_value
            else:
                logger.warning(
                    "No auth cookie found in MongoDB [time=%.2fms]", elapsed_ms
                )
                return None

        except Exception as e:
            logger.error("Failed to get auth cookie from MongoDB: %s", e)
            return None

    async def update_auth_cookie(
        self,
        cookie_value: str,
        expires_at: datetime | None = None,
        updated_by: str = "system",
    ) -> bool:
        """
        Update the authentication cookie in MongoDB config collection.

        Args:
            cookie_value: The new cookie value to store
            expires_at: When the cookie expires (optional, from cookie metadata)
            updated_by: Username or identifier of who updated the cookie

        Returns:
            True if update was successful, False otherwise
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            update_data = {
                "cookie_value": cookie_value,
                "updated_at": datetime.now(UTC),
                "updated_by": updated_by,
            }

            if expires_at:
                update_data["expires_at"] = expires_at

            result = await self.db.config.update_one(  # type: ignore
                {"_id": "auth_cookie"},
                {"$set": update_data},
                upsert=True,
            )

            elapsed_ms = (perf_counter() - start_time) * 1000

            if result.upserted_id or result.modified_count > 0:
                expire_info = f", expires={expires_at}" if expires_at else ""
                logger.info(
                    "Updated auth cookie in MongoDB [updated_by=%s, time=%.2fms%s]",
                    updated_by,
                    elapsed_ms,
                    expire_info,
                )
                return True
            else:
                logger.warning(
                    "Auth cookie update had no effect [time=%.2fms]", elapsed_ms
                )
                return False

        except Exception as e:
            logger.error("Failed to update auth cookie in MongoDB: %s", e)
            return False

    async def get_cookie_expiration_info(self) -> dict | None:
        """
        Get cookie expiration information from MongoDB.

        Returns:
            Dict with expires_at, days_remaining, is_expired, or None if not found
        """
        if not self._connected:
            await self.connect()

        try:
            config_doc = await self.db.config.find_one(  # type: ignore
                {"_id": "auth_cookie"}
            )

            if not config_doc:
                return None

            expires_at = config_doc.get("expires_at")
            if not expires_at:
                return {
                    "expires_at": None,
                    "days_remaining": None,
                    "is_expired": None,
                    "warning": "No expiration date stored",
                }

            now = datetime.now(UTC)

            # Ensure expires_at is timezone-aware
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

            time_remaining = expires_at - now
            days_remaining = time_remaining.days
            is_expired = days_remaining < 0

            return {
                "expires_at": expires_at,
                "days_remaining": days_remaining,
                "is_expired": is_expired,
                "updated_at": config_doc.get("updated_at"),
                "updated_by": config_doc.get("updated_by"),
            }

        except Exception as e:
            logger.error("Failed to get cookie expiration info: %s", e)
            return None

    async def get_app_config(self, key: str, default: any = None) -> any:
        """
        Get an application configuration value from MongoDB.

        Args:
            key: Configuration key (e.g., 'log_level', 'cookie_warning_days')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if not self._connected:
            await self.connect()

        try:
            config_doc = await self.db.config.find_one(  # type: ignore
                {"_id": "app_config"}
            )

            if config_doc and key in config_doc:
                value = config_doc[key]
                if default is not None and value != default:
                    logger.info(
                        "Using MongoDB config for '%s': %s (default: %s)",
                        key,
                        value,
                        default,
                    )
                return value
            else:
                if default is not None:
                    logger.info(
                        "Using default value for '%s': %s (not found in MongoDB)",
                        key,
                        default,
                    )
                return default

        except Exception as e:
            logger.error("Failed to get app config '%s': %s", key, e)
            if default is not None:
                logger.info(
                    "Using default value for '%s': %s (due to error)", key, default
                )
            return default

    async def update_app_config(self, updates: dict) -> bool:
        """
        Update application configuration in MongoDB.

        Args:
            updates: Dict of key-value pairs to update

        Returns:
            True if update was successful, False otherwise
        """
        if not self._connected:
            await self.connect()

        try:
            result = await self.db.config.update_one(  # type: ignore
                {"_id": "app_config"},
                {"$set": updates},
                upsert=True,
            )

            if result.upserted_id or result.modified_count > 0:
                logger.info(
                    "Updated app config in MongoDB [keys=%s]",
                    ", ".join(updates.keys()),
                )
                return True
            else:
                logger.warning("App config update had no effect")
                return False

        except Exception as e:
            logger.error("Failed to update app config: %s", e)
            return False

    # ==================== Publications Management ====================

    async def get_publications(self, active_only: bool = True) -> list[dict]:
        """
        Get all publications from database.

        Args:
            active_only: If True, only return active publications

        Returns:
            List of publication documents
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            query = {"active": True} if active_only else {}
            publications = []

            async for pub in self.db.publications.find(query):
                publications.append(pub)

            elapsed = perf_counter() - start_time
            logger.info(
                "Retrieved %d publications from MongoDB [time=%.2fms]",
                len(publications),
                elapsed * 1000,
            )

            return publications

        except Exception as e:
            logger.error("Failed to get publications: %s", e)
            return []

    async def get_publication(self, publication_id: str) -> dict | None:
        """
        Get a single publication by ID.

        Args:
            publication_id: Unique publication identifier

        Returns:
            Publication document or None if not found
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            publication = await self.db.publications.find_one(
                {"publication_id": publication_id}
            )

            elapsed = perf_counter() - start_time

            if publication:
                logger.info(
                    "Retrieved publication '%s' from MongoDB [time=%.2fms]",
                    publication_id,
                    elapsed * 1000,
                )
            else:
                logger.warning("Publication '%s' not found", publication_id)

            return publication

        except Exception as e:
            logger.error("Failed to get publication '%s': %s", publication_id, e)
            return None

    async def create_publication(self, publication_data: dict) -> bool:
        """
        Create a new publication in database.

        Args:
            publication_data: Publication document with all fields

        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            # Add timestamps
            now = datetime.now(UTC)
            publication_data["created_at"] = now
            publication_data["updated_at"] = now

            result = await self.db.publications.insert_one(publication_data)

            elapsed = perf_counter() - start_time
            logger.info(
                "Created publication '%s' in MongoDB [time=%.2fms]",
                publication_data.get("publication_id"),
                elapsed * 1000,
            )

            return result.inserted_id is not None

        except Exception as e:
            logger.error("Failed to create publication: %s", e)
            return False

    async def update_publication(self, publication_id: str, updates: dict) -> bool:
        """
        Update an existing publication.

        Args:
            publication_id: Publication identifier
            updates: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            await self.connect()

        try:
            start_time = perf_counter()

            # Add update timestamp
            updates["updated_at"] = datetime.now(UTC)

            result = await self.db.publications.update_one(
                {"publication_id": publication_id}, {"$set": updates}
            )

            elapsed = perf_counter() - start_time

            if result.modified_count > 0:
                logger.info(
                    "Updated publication '%s' in MongoDB [time=%.2fms]",
                    publication_id,
                    elapsed * 1000,
                )
                return True
            else:
                logger.warning(
                    "No publication updated for '%s' (not found or no changes)",
                    publication_id,
                )
                return False

        except Exception as e:
            logger.error("Failed to update publication '%s': %s", publication_id, e)
            return False


# Singleton instance
_mongodb_service: MongoDBService | None = None


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


async def update_recipient_stats(email: str, publication_id: str | None = None):
    """
    Convenience function to update recipient statistics.

    Args:
        email: Recipient email address
        publication_id: Optional publication ID for per-publication tracking
    """
    service = await get_mongodb_service()
    await service.update_recipient_stats(email, publication_id)


async def get_recipients_for_publication(
    publication_id: str, delivery_method: str
) -> list[dict]:
    """
    Convenience function to get recipients for a publication and delivery method.

    Args:
        publication_id: Publication identifier
        delivery_method: Either "email" or "upload"

    Returns:
        List of recipient dicts
    """
    service = await get_mongodb_service()
    return await service.get_recipients_for_publication(publication_id, delivery_method)


def get_onedrive_folder_for_recipient(recipient: dict, publication: dict) -> str:
    """
    Convenience function to resolve OneDrive folder for recipient.

    Args:
        recipient: Recipient document
        publication: Publication document

    Returns:
        Resolved folder path
    """
    service = MongoDBService.__new__(MongoDBService)
    return service.get_onedrive_folder_for_recipient(recipient, publication)


def get_organize_by_year_for_recipient(recipient: dict, publication: dict) -> bool:
    """
    Convenience function to resolve organize_by_year setting for recipient.

    Args:
        recipient: Recipient document
        publication: Publication document

    Returns:
        Whether to organize by year
    """
    service = MongoDBService.__new__(MongoDBService)
    return service.get_organize_by_year_for_recipient(recipient, publication)


async def get_publications(active_only: bool = True) -> list[dict]:
    """
    Convenience function to get publications.

    Args:
        active_only: If True, only return active publications

    Returns:
        List of publication dicts
    """
    service = await get_mongodb_service()
    return await service.get_publications(active_only)


async def get_publication(publication_id: str) -> dict | None:
    """
    Convenience function to get a single publication.

    Args:
        publication_id: Publication identifier

    Returns:
        Publication dict or None
    """
    service = await get_mongodb_service()
    return await service.get_publication(publication_id)


async def create_publication(publication_data: dict) -> bool:
    """
    Convenience function to create a publication.

    Args:
        publication_data: Publication document

    Returns:
        True if successful
    """
    service = await get_mongodb_service()
    return await service.create_publication(publication_data)


async def update_publication(publication_id: str, updates: dict) -> bool:
    """
    Convenience function to update a publication.

    Args:
        publication_id: Publication identifier
        updates: Fields to update

    Returns:
        True if successful
    """
    service = await get_mongodb_service()
    return await service.update_publication(publication_id, updates)


async def close_mongodb_connection():
    """Close the MongoDB connection."""
    global _mongodb_service
    if _mongodb_service:
        await _mongodb_service.close()
        _mongodb_service = None
