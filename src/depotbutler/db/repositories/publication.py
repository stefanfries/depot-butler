"""Publication repository for MongoDB operations."""

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from depotbutler.db.repositories.base import BaseRepository
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class PublicationRepository(BaseRepository):
    """Repository for publication-related database operations."""

    @property
    def collection(self) -> Any:
        """Return the publications collection."""
        return self.db.publications

    async def get_publications(self, active_only: bool = True) -> list[dict]:
        """
        Get all publications from database.

        Args:
            active_only: If True, only return active publications

        Returns:
            List of publication documents
        """
        try:
            start_time = perf_counter()

            query = {"active": True} if active_only else {}
            publications = []

            async for pub in self.collection.find(query):
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
        try:
            start_time = perf_counter()

            publication = await self.collection.find_one(
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

            return dict(publication) if publication else None

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
        try:
            start_time = perf_counter()

            # Add timestamps
            now = datetime.now(UTC)
            publication_data["created_at"] = now
            publication_data["updated_at"] = now

            result = await self.collection.insert_one(publication_data)

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
        try:
            start_time = perf_counter()

            # Add update timestamp
            updates["updated_at"] = datetime.now(UTC)

            result = await self.collection.update_one(
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
