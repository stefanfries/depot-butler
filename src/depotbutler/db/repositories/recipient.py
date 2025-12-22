"""Recipient repository for MongoDB operations."""

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from pymongo.errors import OperationFailure

from depotbutler.db.repositories.base import BaseRepository
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class RecipientRepository(BaseRepository):
    """Repository for recipient-related database operations."""

    @property
    def collection(self) -> Any:
        """Return the recipients collection."""
        return self.db.recipients

    async def get_active_recipients(self) -> list[dict]:
        """
        Fetch all active recipients from MongoDB.

        Returns:
            List of recipient documents with email, first_name, last_name
        """
        try:
            start_time = perf_counter()

            cursor = self.collection.find(
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
            return list(recipients)

        except OperationFailure as e:
            logger.error("Failed to fetch recipients from MongoDB: %s", e)
            return []
        except Exception as e:
            logger.error("Unexpected error fetching recipients: %s", e)
            return []

    async def update_recipient_stats(
        self, email: str, publication_id: str | None = None
    ) -> None:
        """
        Update send statistics for a recipient.

        Args:
            email: Recipient email address
            publication_id: Optional publication ID for per-publication tracking
        """
        try:
            start_time = perf_counter()

            if publication_id:
                # Update per-publication stats
                result = await self.collection.update_one(
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
                result = await self.collection.update_one(
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

            cursor = self.collection.find(query, projection).sort("email", 1)
            recipients = await cursor.to_list(length=None)

            elapsed = perf_counter() - start_time
            logger.info(
                "Retrieved %s recipients for publication=%s, method=%s [query_time=%.2fms]",
                len(recipients),
                publication_id,
                delivery_method,
                elapsed * 1000,
            )
            return list(recipients)

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
                    return str(custom_folder)
                break

        # Fall back to publication default
        default_folder = publication.get("default_onedrive_folder", "")
        logger.debug(
            f"Using publication default folder for {recipient['email']}: {default_folder}"
        )
        return str(default_folder)

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
                    return bool(organize_by_year)
                break

        # Fall back to publication setting, default to True
        publication_setting = publication.get("organize_by_year", True)
        logger.debug(
            f"Using publication organize_by_year for {recipient['email']}: {publication_setting}"
        )
        return bool(publication_setting)
