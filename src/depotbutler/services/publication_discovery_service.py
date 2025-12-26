"""
Publication discovery and synchronization service.

This module handles automatic discovery of publications from the
boersenmedien.com account and synchronizes them with the MongoDB
publications collection.
"""

import re
from datetime import UTC, datetime
from typing import Any

from depotbutler.db.mongodb import (
    create_publication,
    get_publications,
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

    def _normalize_publication_id(self, name: str) -> str:
        """
        Normalize publication name to a consistent publication_id.

        Examples:
            "DER AKTIONÄR E-Paper" -> "der-aktionaer-epaper"
            "Megatrend Folger" -> "megatrend-folger"
            "Jahresabo" -> "jahresabo"

        Args:
            name: Publication or subscription type name

        Returns:
            Normalized publication ID (lowercase, hyphenated)
        """
        # Remove special characters and convert to lowercase
        normalized = name.lower()
        # Replace umlauts
        normalized = (
            normalized.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
        )
        # Remove non-alphanumeric except spaces and hyphens
        normalized = re.sub(r"[^a-z0-9\s-]", "", normalized)
        # Replace spaces with hyphens
        normalized = re.sub(r"\s+", "-", normalized)
        # Remove multiple hyphens
        normalized = re.sub(r"-+", "-", normalized)
        # Strip leading/trailing hyphens
        normalized = normalized.strip("-")
        return normalized

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

        results = self._initialize_sync_results()

        try:
            # Discover subscriptions
            subscriptions = await self._discover_subscriptions(results)
            if not subscriptions:
                return results

            # Process subscriptions and update results
            await self._process_subscriptions(subscriptions, results)

            # Log summary
            self._log_sync_summary(results)

            return results

        except Exception as e:
            logger.error(f"Publication discovery sync failed: {e}", exc_info=True)
            raise

    def _initialize_sync_results(self) -> dict[str, int | list[str]]:
        """Initialize results dictionary for sync operation."""
        return {
            "discovered_count": 0,
            "new_count": 0,
            "updated_count": 0,
            "errors": [],
        }

    async def _discover_subscriptions(
        self, results: dict[str, int | list[str]]
    ) -> list[Any]:
        """
        Discover subscriptions from account.

        Returns:
            List of subscription objects, empty list if none found
        """
        logger.info("Discovering subscriptions from account...")
        subscriptions = await self.httpx_client.discover_subscriptions()
        results["discovered_count"] = len(subscriptions)

        if not subscriptions:
            logger.warning("No subscriptions discovered from account")
            return []

        logger.info(f"Found {len(subscriptions)} subscription(s)")
        return subscriptions

    async def _process_subscriptions(
        self, subscriptions: list[Any], results: dict[str, int | list[str]]
    ) -> None:
        """Process each discovered subscription and update results."""
        now = datetime.now(UTC)

        # Get all existing publications to match
        all_publications = await get_publications(active_only=False)

        # Create lookup maps for matching
        existing_by_sub_id = {
            pub.get("subscription_id"): pub
            for pub in all_publications
            if pub.get("subscription_id")
        }
        # Group publications by subscription_number
        existing_by_sub_number: dict[str, list[dict]] = {}
        for pub in all_publications:
            if sub_num := pub.get("subscription_number"):
                existing_by_sub_number.setdefault(sub_num, []).append(pub)

        # Track which subscription IDs we've seen (to mark unseen as inactive later)
        seen_sub_ids = set()

        for subscription in subscriptions:
            try:
                seen_sub_ids.add(subscription.subscription_id)

                # Try to match existing publication
                existing = existing_by_sub_id.get(subscription.subscription_id)

                if not existing:
                    # Check for renewal by subscription_number
                    existing = self._find_renewal_match(
                        subscription, existing_by_sub_number
                    )

                if existing:
                    # Update existing publication (or renewal)
                    await self._update_existing_publication(
                        existing["publication_id"], subscription, now, existing
                    )
                    updated_count = results["updated_count"]
                    assert isinstance(updated_count, int)
                    results["updated_count"] = updated_count + 1
                else:
                    # Create new publication
                    await self._create_new_publication(
                        subscription, now, all_publications
                    )
                    new_count = results["new_count"]
                    assert isinstance(new_count, int)
                    results["new_count"] = new_count + 1

            except Exception as e:
                error_msg = f"Failed to process subscription {subscription.subscription_id}: {e}"
                logger.error(error_msg)
                errors = results["errors"]
                assert isinstance(errors, list)
                errors.append(error_msg)

        # Mark publications no longer in account as inactive
        await self._mark_unseen_as_inactive(all_publications, seen_sub_ids, now)

    def _find_renewal_match(
        self, subscription: Any, existing_by_sub_number: dict[str, list[dict]]
    ) -> dict | None:
        """
        Find existing publication that matches this subscription (renewal case).

        Args:
            subscription: New subscription data
            existing_by_sub_number: Map of subscription_number to publication list

        Returns:
            Matching publication or None
        """
        # Get publications with same subscription_number
        candidates = existing_by_sub_number.get(subscription.subscription_number, [])

        if not candidates:
            return None

        # Prefer active publications, then most recently updated
        candidates_sorted = sorted(
            candidates,
            key=lambda p: (p.get("active", False), p.get("updated_at", datetime.min)),
            reverse=True,
        )

        match = candidates_sorted[0]
        logger.info(
            f"Found renewal match: {match['publication_id']} "
            f"(old sub_id: {match.get('subscription_id')}, "
            f"new sub_id: {subscription.subscription_id})"
        )
        return match

    async def _mark_unseen_as_inactive(
        self, all_publications: list[dict], seen_sub_ids: set[str], now: datetime
    ) -> None:
        """
        Mark publications no longer in account as inactive.

        Args:
            all_publications: All publications from database
            seen_sub_ids: Set of subscription IDs seen in current discovery
            now: Current timestamp
        """
        for pub in all_publications:
            if not pub.get("active", False):
                continue  # Already inactive

            sub_id = pub.get("subscription_id")
            if sub_id and sub_id not in seen_sub_ids:
                # Not seen in current discovery - mark inactive
                logger.info(
                    f"Marking publication '{pub['publication_id']}' as inactive "
                    f"(no longer in account)"
                )
                await update_publication(
                    pub["publication_id"], {"active": False, "updated_at": now}
                )

            # Also check expiration
            if duration_end := pub.get("duration_end"):
                # Ensure timezone awareness
                duration_end = (
                    duration_end
                    if duration_end.tzinfo
                    else duration_end.replace(tzinfo=UTC)
                )
                if duration_end < now:
                    # Expired - mark inactive
                    logger.info(
                        f"Marking publication '{pub['publication_id']}' as inactive "
                        f"(expired on {duration_end.date()})"
                    )
                    await update_publication(
                        pub["publication_id"], {"active": False, "updated_at": now}
                    )

    def _log_sync_summary(self, results: dict[str, int | list[str]]) -> None:
        """Log summary of sync operation."""
        errors_list = results["errors"]
        assert isinstance(errors_list, list)
        logger.info(
            f"Discovery sync complete: "
            f"{results['discovered_count']} discovered, "
            f"{results['new_count']} new, "
            f"{results['updated_count']} updated, "
            f"{len(errors_list)} errors"
        )

    async def _create_new_publication(
        self, subscription: Any, now: datetime, all_publications: list[dict]
    ) -> None:
        """
        Create a new publication from a discovered subscription.

        Args:
            subscription: Subscription object from discover_subscriptions()
            now: Current timestamp for discovery tracking
            all_publications: Pre-fetched list of all publications (for settings inheritance)
        """
        # Determine proper publication_id from subscription name
        pub_name = subscription.name or subscription.subscription_type
        publication_id = self._normalize_publication_id(pub_name)

        logger.info(
            f"Creating new publication: {publication_id} "
            f"(sub_id: {subscription.subscription_id}, type: {subscription.subscription_type})"
        )

        publication_data = {
            "publication_id": publication_id,
            "name": pub_name,  # Use actual name from subscription
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

        # Check for expired/inactive publications with same subscription_number to inherit settings
        expired_match = next(
            (
                pub
                for pub in all_publications
                if pub.get("subscription_number") == subscription.subscription_number
                and not pub.get("active", True)
            ),
            None,
        )
        if expired_match:
            logger.info(
                f"Inheriting settings from expired publication: {expired_match['publication_id']}"
            )
            # Inherit settings if present
            for key in ["default_onedrive_folder", "email_enabled", "onedrive_enabled"]:
                if key in expired_match:
                    publication_data[key] = expired_match[key]

        success = await create_publication(publication_data)

        if success:
            logger.info(f"✓ Created publication: {publication_id}")
        else:
            raise Exception(f"Failed to create publication {publication_id}")

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
        is_renewal = existing.get("subscription_id") != subscription.subscription_id

        if is_renewal:
            logger.info(
                f"Updating publication {pub_id} with renewed subscription "
                f"(old: {existing.get('subscription_id')}, new: {subscription.subscription_id})"
            )
        else:
            logger.debug(f"Updating publication: {pub_id}")

        update_data = {
            "subscription_id": subscription.subscription_id,  # Update to new sub_id for renewals
            "subscription_number": subscription.subscription_number,
            "subscription_type": subscription.subscription_type,
            "duration": subscription.duration,
            "last_seen": now,
            "active": True,  # Reactivate if it was inactive
        }

        # Update name if it's a renewal and the name improved
        if is_renewal and subscription.name:
            update_data["name"] = subscription.name

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
