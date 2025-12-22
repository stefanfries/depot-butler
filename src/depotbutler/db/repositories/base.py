"""Base repository class with shared connection management."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient


class BaseRepository:
    """Base class for all repositories with shared connection."""

    def __init__(self, client: AsyncIOMotorClient, db_name: str) -> None:
        """
        Initialize repository with MongoDB client and database.

        Args:
            client: AsyncIOMotorClient instance
            db_name: Name of the database
        """
        self.client = client
        self.db = client[db_name]

    @property
    def collection(self) -> Any:
        """Return the collection for this repository. Must be overridden."""
        raise NotImplementedError("Subclasses must implement collection property")
