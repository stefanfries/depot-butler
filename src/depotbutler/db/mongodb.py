"""MongoDB database operations for depot-butler using Motor (async driver)."""

from datetime import datetime
from types import TracebackType
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure

from depotbutler.db.repositories import (
    ConfigRepository,
    EditionRepository,
    PublicationRepository,
    RecipientRepository,
)
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class MongoDBService:
    """Service for MongoDB operations using async Motor driver with repository pattern."""

    def __init__(self) -> None:
        """Initialize MongoDB service (connection happens in connect())."""
        self.settings = Settings()
        self.client: AsyncIOMotorClient | None = None
        self.db: Any = None
        self._connected = False

        # Repository instances (initialized in connect())
        self.recipient_repo: RecipientRepository | None = None
        self.edition_repo: EditionRepository | None = None
        self.config_repo: ConfigRepository | None = None
        self.publication_repo: PublicationRepository | None = None

    async def connect(self) -> None:
        """
        Establish connection to MongoDB and initialize repositories.

        Raises:
            ConnectionFailure: If connection to MongoDB fails
        """
        if self._connected:
            logger.debug("MongoDB already connected")
            return

        try:
            logger.info("Connecting to MongoDB...")

            # Create async Motor client with timeouts
            self.client = AsyncIOMotorClient(
                self.settings.mongodb.connection_string,
                serverSelectionTimeoutMS=self.settings.database.server_selection_timeout_ms,
                connectTimeoutMS=self.settings.database.connect_timeout_ms,
                socketTimeoutMS=self.settings.database.socket_timeout_ms,
            )

            # Get database reference
            self.db = self.client[self.settings.mongodb.name]

            # Test connection with ping
            await self.client.admin.command("ping")

            # Initialize repositories
            self.recipient_repo = RecipientRepository(
                self.client, self.settings.mongodb.name
            )
            self.edition_repo = EditionRepository(
                self.client, self.settings.mongodb.name
            )
            self.config_repo = ConfigRepository(self.client, self.settings.mongodb.name)
            self.publication_repo = PublicationRepository(
                self.client, self.settings.mongodb.name
            )

            logger.info("✅ Connected to MongoDB")
            self._connected = True

        except ConnectionFailure as e:
            logger.error("❌ Failed to connect to MongoDB: %s", e)
            raise
        except Exception as e:
            logger.error("❌ Unexpected error connecting to MongoDB: %s", e)
            raise ConnectionFailure(f"Failed to connect to MongoDB: {e}") from e

    async def __aenter__(self) -> "MongoDBService":
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Closed MongoDB connection")

    # ==================== Recipient Operations ====================

    async def get_active_recipients(self) -> list[dict]:
        """Fetch all active recipients from the database."""
        assert self.recipient_repo is not None
        return await self.recipient_repo.get_active_recipients()

    async def update_recipient_stats(
        self, email: str, publication_id: str | None = None
    ) -> None:
        """Update statistics for a recipient."""
        assert self.recipient_repo is not None
        await self.recipient_repo.update_recipient_stats(email, publication_id)

    async def get_recipients_for_publication(
        self, publication_id: str, delivery_method: str
    ) -> list[dict]:
        """Get recipients who have enabled a specific delivery method for a publication."""
        assert self.recipient_repo is not None
        return await self.recipient_repo.get_recipients_for_publication(
            publication_id, delivery_method
        )

    def get_onedrive_folder_for_recipient(
        self, recipient: dict, publication: dict
    ) -> str:
        """Resolve OneDrive folder path for a recipient and publication."""
        assert self.recipient_repo is not None
        return self.recipient_repo.get_onedrive_folder_for_recipient(
            recipient, publication
        )

    def get_organize_by_year_for_recipient(
        self, recipient: dict, publication: dict
    ) -> bool:
        """Resolve organize_by_year setting for a recipient and publication."""
        assert self.recipient_repo is not None
        return self.recipient_repo.get_organize_by_year_for_recipient(
            recipient, publication
        )

    # ==================== Edition Tracking Operations ====================

    async def is_edition_processed(self, edition_key: str) -> bool:
        """Check if an edition has already been processed."""
        assert self.edition_repo is not None
        return await self.edition_repo.is_edition_processed(edition_key)

    async def mark_edition_processed(
        self,
        edition_key: str,
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
        """Mark an edition as processed with optional blob storage metadata and source tracking."""
        assert self.edition_repo is not None
        return await self.edition_repo.mark_edition_processed(
            edition_key=edition_key,
            title=title,
            publication_date=publication_date,
            download_url=download_url,
            file_path=file_path,
            downloaded_at=downloaded_at,
            blob_url=blob_url,
            blob_path=blob_path,
            blob_container=blob_container,
            file_size_bytes=file_size_bytes,
            archived_at=archived_at,
            source=source,
        )

    async def get_processed_editions_count(self) -> int:
        """Get total count of processed editions."""
        assert self.edition_repo is not None
        return await self.edition_repo.get_processed_editions_count()

    async def get_recent_processed_editions(self, days: int = 30) -> list[dict]:
        """Get editions processed in the last N days."""
        assert self.edition_repo is not None
        return await self.edition_repo.get_recent_processed_editions(days)

    async def remove_edition_from_tracking(self, edition_key: str) -> bool:
        """Remove an edition from tracking to allow reprocessing."""
        assert self.edition_repo is not None
        return await self.edition_repo.remove_edition_from_tracking(edition_key)

    async def cleanup_old_editions(self, days_to_keep: int = 90) -> None:
        """Remove editions older than specified days."""
        assert self.edition_repo is not None
        await self.edition_repo.cleanup_old_editions(days_to_keep)

    # ==================== Config Operations ====================

    async def get_auth_cookie(self) -> str | None:
        """Get the authentication cookie from MongoDB config collection."""
        assert self.config_repo is not None
        return await self.config_repo.get_auth_cookie()

    async def update_auth_cookie(
        self,
        cookie_value: str,
        expires_at: datetime | None = None,
        updated_by: str = "system",
    ) -> bool:
        """Update the authentication cookie in MongoDB config collection."""
        assert self.config_repo is not None
        return await self.config_repo.update_auth_cookie(
            cookie_value, expires_at, updated_by
        )

    async def get_cookie_expiration_info(self) -> dict | None:
        """Get cookie expiration information from MongoDB."""
        assert self.config_repo is not None
        return await self.config_repo.get_cookie_expiration_info()

    async def get_app_config(self, key: str, default: Any = None) -> Any:
        """Get an application configuration value from MongoDB."""
        assert self.config_repo is not None
        return await self.config_repo.get_app_config(key, default)

    async def update_app_config(self, updates: dict) -> bool:
        """Update application configuration in MongoDB."""
        assert self.config_repo is not None
        return await self.config_repo.update_app_config(updates)

    # ==================== Publications Management ====================

    async def get_publications(self, active_only: bool = True) -> list[dict]:
        """Get all publications from database."""
        assert self.publication_repo is not None
        return await self.publication_repo.get_publications(active_only=active_only)

    async def get_publication(self, publication_id: str) -> dict | None:
        """Get a single publication by ID."""
        assert self.publication_repo is not None
        return await self.publication_repo.get_publication(publication_id)

    async def create_publication(self, publication_data: dict) -> bool:
        """Create a new publication in database (legacy - returns bool)."""
        assert self.publication_repo is not None
        return await self.publication_repo.create_publication(publication_data)

    async def update_publication(self, publication_id: str, updates: dict) -> bool:
        """Update an existing publication (legacy - returns bool)."""
        assert self.publication_repo is not None
        return await self.publication_repo.update_publication(publication_id, updates)


# ==================== Module-Level Functions ====================
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


async def update_recipient_stats(email: str, publication_id: str | None = None) -> None:
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
    service.recipient_repo = RecipientRepository.__new__(RecipientRepository)
    return service.recipient_repo.get_onedrive_folder_for_recipient(
        recipient, publication
    )


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
    service.recipient_repo = RecipientRepository.__new__(RecipientRepository)
    return service.recipient_repo.get_organize_by_year_for_recipient(
        recipient, publication
    )


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


async def close_mongodb_connection() -> None:
    """Close the MongoDB connection."""
    global _mongodb_service
    if _mongodb_service:
        await _mongodb_service.close()
        _mongodb_service = None
