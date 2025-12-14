"""
Publication discovery and synchronization service.

This module handles automatic discovery of publications from the
boersenmedien.com account and synchronizes them with the MongoDB
publications collection.
"""

from datetime import datetime, timezone
from typing import Any

from depotbutler.db.mongodb import (
    create_publication,
    get_publication,
    update_publication,
)
from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class PublicationDiscoveryService:
    """
    Service for discovering and synchronizing publications from web account.

    This service:
    - Discovers active subscriptions from boersenmedien.com
    - Creates new publication records for unknown subscriptions
    - Updates last_seen timestamps for existing publications
    - Marks publications as inactive if they're no longer in the account
    """

    def __init__(self, httpx_client: HttpxBoersenmedienClient):
        """
        Initialize the discovery service.

        Args:
            httpx_client: Configured HTTP client for boersenmedien.com
        """
        self.httpx_client = httpx_client

    async def sync_publications_from_account(self) -> dict[str, Any]:
        """
        Synchronize publications from web account to MongoDB.

        This method:
        1. Discovers all subscriptions from the account
        2. Creates new publications for previously unseen subscriptions
        3. Updates last_seen timestamps for existing publications
        4. Returns summary of sync operation

        Returns:
            Dictionary with sync results:
            {
                "discovered_count": int,  # Total subscriptions found
                "new_count": int,         # New publications created
                "updated_count": int,     # Existing publications updated
                "errors": list[str]       # Any errors encountered
            }

        Raises:
            Exception: If discovery fails completely
        """
        logger.info("Starting publication discovery sync")

        results = {
            "discovered_count": 0,
            "new_count": 0,
            "updated_count": 0,
            "errors": [],
        }

        try:
            # Step 1: Discover subscriptions from account
            logger.info("Discovering subscriptions from account...")
            subscriptions = await self.httpx_client.discover_subscriptions()
            results["discovered_count"] = len(subscriptions)

            if not subscriptions:
                logger.warning("No subscriptions discovered from account")
                return results

            logger.info(f"Found {len(subscriptions)} subscription(s)")

            # Step 2: Process each discovered subscription
            now = datetime.now(timezone.utc)

            # Get all existing publications to match by subscription_id
            all_publications = await get_publications(active_only=False)
            
            # Create a lookup map: subscription_id -> publication
            existing_by_sub_id = {
                pub.get("subscription_id"): pub 
                for pub in all_publications 
                if pub.get("subscription_id")
            }

            for subscription in subscriptions:
                try:
                    # Match by subscription_id (not publication_id)
                    # subscription_id is the numeric ID from boersenmedien.com
                    existing = existing_by_sub_id.get(subscription.subscription_id)

                    if existing:
                        # Update existing publication using its publication_id
                        await self._update_existing_publication(
                            existing["publication_id"], subscription, now, existing
                        )
                        results["updated_count"] += 1
                    else:
                        # Create new publication
                        await self._create_new_publication(subscription, now)
                        results["new_count"] += 1

                except Exception as e:
                    error_msg = f"Failed to process subscription {subscription.subscription_id}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

            # Step 3: Log summary
            logger.info(
                f"Discovery sync complete: "
                f"{results['discovered_count']} discovered, "
                f"{results['new_count']} new, "
                f"{results['updated_count']} updated, "
                f"{len(results['errors'])} errors"
            )

            return results

        except Exception as e:
            logger.error(f"Publication discovery sync failed: {e}", exc_info=True)
            raise

    async def _create_new_publication(self, subscription: Any, now: datetime) -> None:
        """
        Create a new publication from a discovered subscription.

        Args:
            subscription: Subscription object from discover_subscriptions()
            now: Current timestamp for discovery tracking
        """
        logger.info(
            f"Creating new publication: {subscription.subscription_id} "
            f"({subscription.subscription_type})"
        )

        publication_data = {
            "publication_id": subscription.subscription_id,
            "name": subscription.subscription_type,  # Use subscription type as default name
            "subscription_id": subscription.subscription_id,
            "subscription_number": subscription.subscription_number,
            "subscription_type": subscription.subscription_type,
            "duration": subscription.duration,
            "active": True,
            # Discovery tracking
            "discovered": True,
            "first_discovered": now,
            "last_seen": now,
            # Default delivery settings (disabled until explicitly configured)
            "email_enabled": False,
            "onedrive_enabled": False,
        }

        # Add duration dates if available
        if subscription.duration_start:
            publication_data["duration_start"] = datetime.combine(
                subscription.duration_start, datetime.min.time()
            )
        if subscription.duration_end:
            publication_data["duration_end"] = datetime.combine(
                subscription.duration_end, datetime.min.time()
            )

        success = await create_publication(publication_data)

        if success:
            logger.info(f"✓ Created publication: {subscription.subscription_id}")
        else:
            raise Exception(
                f"Failed to create publication {subscription.subscription_id}"
            )

    async def _update_existing_publication(
        self,
        pub_id: str,
        subscription: Any,
        now: datetime,
        existing: dict[str, Any],
    ) -> None:
        """
        Update an existing publication with latest subscription data.

        Args:
            pub_id: Publication ID
            subscription: Latest subscription data from account
            now: Current timestamp for last_seen update
            existing: Existing publication document from database
        """
        logger.debug(f"Updating publication: {pub_id}")

        update_data = {
            "subscription_number": subscription.subscription_number,
            "subscription_type": subscription.subscription_type,
            "duration": subscription.duration,
            "last_seen": now,
        }

        # If this was previously not discovered (manual entry), mark it as discovered now
        if not existing.get("discovered", False):
            update_data["discovered"] = True
            update_data["first_discovered"] = now
            logger.info(f"Marking previously manual publication {pub_id} as discovered")

        # Update duration dates if available
        if subscription.duration_start:
            update_data["duration_start"] = datetime.combine(
                subscription.duration_start, datetime.min.time()
            )
        if subscription.duration_end:
            update_data["duration_end"] = datetime.combine(
                subscription.duration_end, datetime.min.time()
            )

        success = await update_publication(pub_id, update_data)

        if success:
            logger.debug(f"✓ Updated publication: {pub_id}")
        else:
            raise Exception(f"Failed to update publication {pub_id}")
