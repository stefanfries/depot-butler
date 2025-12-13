"""
Seed publications collection from discovered subscriptions.

This script:
1. Discovers all subscriptions from the boersenmedien.com account
2. Maps them to configured publications
3. Creates/updates publication documents in MongoDB with metadata
"""

import asyncio
import sys
from datetime import datetime

from depotbutler.db.mongodb import (
    create_publication,
    get_publication,
    update_publication,
)
from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.publications import PUBLICATIONS
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


# Mapping from publication IDs to subscription IDs
PUBLICATION_SUBSCRIPTION_MAP = {
    "megatrend-folger": "2477462",  # Megatrend Folger subscription ID
    "der-aktionaer-epaper": "2300989",  # DER AKTIONÄR E-Paper subscription ID
}


async def seed_publications():
    """Discover subscriptions and seed publications collection."""
    logger.info("=" * 80)
    logger.info("Starting publication seeding process")
    logger.info("=" * 80)

    # Step 1: Discover subscriptions
    logger.info("\n[Step 1/3] Discovering subscriptions from account...")
    client = HttpxBoersenmedienClient()
    try:
        await client.login()
        subscriptions = await client.discover_subscriptions()

        if not subscriptions:
            logger.error("No subscriptions discovered. Exiting.")
            return False

        logger.info(f"✓ Discovered {len(subscriptions)} subscriptions")

        # Create lookup by subscription ID
        subscription_lookup = {sub.subscription_id: sub for sub in subscriptions}

        # Step 2: Process each configured publication
        logger.info("\n[Step 2/3] Processing configured publications...")
        success_count = 0
        error_count = 0

        for pub_config in PUBLICATIONS:
            pub_id = pub_config.id
            logger.info(f"\n--- Processing: {pub_config.name} ---")

            # Find matching subscription
            expected_sub_id = PUBLICATION_SUBSCRIPTION_MAP.get(pub_id)
            if not expected_sub_id:
                logger.warning(f"No subscription mapping for {pub_id}. Skipping.")
                error_count += 1
                continue

            subscription = subscription_lookup.get(expected_sub_id)
            if not subscription:
                logger.warning(
                    f"Subscription {expected_sub_id} not found in account. Skipping."
                )
                error_count += 1
                continue

            # Build publication document
            publication_data = {
                "publication_id": pub_id,
                "name": pub_config.name,
                "subscription_id": subscription.subscription_id,
                "subscription_number": subscription.subscription_number,
                "subscription_type": subscription.subscription_type,
                "duration": subscription.duration,
                "active": True,
            }

            # Add parsed dates if available (convert date to datetime for MongoDB)
            if subscription.duration_start:
                publication_data["duration_start"] = datetime.combine(
                    subscription.duration_start, datetime.min.time()
                )
            if subscription.duration_end:
                publication_data["duration_end"] = datetime.combine(
                    subscription.duration_end, datetime.min.time()
                )

            # Configure delivery settings per publication
            if pub_id == "megatrend-folger":
                publication_data["email_enabled"] = True
                publication_data["onedrive_enabled"] = True
                publication_data["default_onedrive_folder"] = pub_config.onedrive_folder
            elif pub_id == "der-aktionaer-epaper":
                publication_data["email_enabled"] = False
                publication_data["onedrive_enabled"] = True
                publication_data["default_onedrive_folder"] = "TSI"

            # Check if publication already exists
            existing = await get_publication(pub_id)
            if existing:
                logger.info(f"Publication {pub_id} already exists. Updating...")
                # Remove fields that shouldn't be updated
                update_data = {
                    k: v
                    for k, v in publication_data.items()
                    if k not in ["publication_id", "created_at"]
                }
                success = await update_publication(pub_id, update_data)
                if success:
                    logger.info(f"✓ Updated {pub_config.name}")
                    success_count += 1
                else:
                    logger.error(f"✗ Failed to update {pub_config.name}")
                    error_count += 1
            else:
                logger.info(f"Creating new publication: {pub_id}")
                success = await create_publication(publication_data)
                if success:
                    logger.info(f"✓ Created {pub_config.name}")
                    success_count += 1
                else:
                    logger.error(f"✗ Failed to create {pub_config.name}")
                    error_count += 1

        # Step 3: Summary
        logger.info("\n[Step 3/3] Summary")
        logger.info("=" * 80)
        logger.info(f"Total publications processed: {len(PUBLICATIONS)}")
        logger.info(f"Successfully created/updated: {success_count}")
        logger.info(f"Errors: {error_count}")
        logger.info("=" * 80)

        return error_count == 0

    except Exception as e:
        logger.error(f"Failed to seed publications: {e}", exc_info=True)
        return False
    finally:
        await client.close()


def main():
    """Run the seeding script."""
    try:
        result = asyncio.run(seed_publications())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\nSeeding cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
