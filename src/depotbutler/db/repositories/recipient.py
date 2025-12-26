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

    def get_recipient_preference(
        self,
        recipient: dict,
        publication: dict,
        pref_key: str,
        pub_key: str | None = None,
        default: str | bool | None = None,
    ) -> str | bool | None:
        """
        Generic preference resolver with recipient override support.

        This method implements a priority-based preference resolution:
        1. Recipient's custom preference for this publication
        2. Publication's default setting
        3. Provided default value

        Args:
            recipient: Recipient document with publication_preferences
            publication: Publication document
            pref_key: Key to look up in recipient's publication_preferences
            pub_key: Key to look up in publication document (defaults to pref_key)
            default: Default value if not found in either location

        Returns:
            Resolved preference value (type matches default)
        """
        if pub_key is None:
            pub_key = pref_key

        # Check recipient's custom preference for this publication
        preferences = recipient.get("publication_preferences", [])
        for pref in preferences:
            if pref.get("publication_id") == publication["publication_id"]:
                value = pref.get(pref_key)
                if value is not None:
                    logger.debug(
                        f"Using recipient override for {recipient['email']}: "
                        f"{pref_key}={value}"
                    )
                    # Return the value cast to the expected return type
                    return value  # type: ignore[no-any-return]
                break

        # Fall back to publication default
        pub_value = publication.get(pub_key, default)
        logger.debug(
            f"Using publication default for {recipient['email']}: {pub_key}={pub_value}"
        )
        # Return the publication value cast to the expected return type
        return pub_value  # type: ignore[no-any-return]

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
        folder = self.get_recipient_preference(
            recipient,
            publication,
            "custom_onedrive_folder",
            "default_onedrive_folder",
            "",
        )
        return str(folder)

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
        organize = self.get_recipient_preference(
            recipient, publication, "organize_by_year", "organize_by_year", True
        )
        return bool(organize)
