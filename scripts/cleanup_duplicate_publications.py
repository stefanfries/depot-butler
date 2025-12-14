"""
Clean up duplicate publications created by the discovery sync.

This script identifies and removes publications that:
- Were created by discovery sync (numeric publication_id)
- Don't have a proper "name" field
- Have a subscription_id that matches an existing properly-configured publication

Run this to fix the duplicate publications issue.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import MongoDBService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def clean_duplicate_publications():
    """Identify and remove duplicate publications."""

    logger.info("🔍 Analyzing publications for duplicates...")

    async with MongoDBService() as db:
        # Get all publications
        publications = await db.get_publications(active_only=False)

        if not publications:
            logger.info("No publications found")
            return

        logger.info(f"Found {len(publications)} total publications")

        # Separate good and bad publications
        good_pubs = []
        bad_pubs = []

        for pub in publications:
            pub_id = pub.get("publication_id")
            name = pub.get("name")
            sub_id = pub.get("subscription_id")

            # Bad publication criteria:
            # - publication_id is numeric (should be human-readable like "megatrend-folger")
            # - OR missing a proper "name" field (just has subscription_type)
            if pub_id and pub_id.isdigit():
                bad_pubs.append(pub)
                logger.warning(
                    f"❌ Bad publication found: publication_id='{pub_id}' "
                    f"(numeric ID, should be human-readable)"
                )
            elif not name or name == pub.get("subscription_type"):
                bad_pubs.append(pub)
                logger.warning(
                    f"❌ Bad publication found: publication_id='{pub_id}' "
                    f"(missing proper name, has '{name}')"
                )
            else:
                good_pubs.append(pub)
                logger.info(
                    f"✓ Good publication: publication_id='{pub_id}', "
                    f"name='{name}', subscription_id='{sub_id}'"
                )

        if not bad_pubs:
            logger.info("✅ No duplicate publications found!")
            return

        logger.warning(f"\n{'='*60}")
        logger.warning(f"Found {len(bad_pubs)} duplicate publication(s) to delete:")
        logger.warning(f"{'='*60}")

        for pub in bad_pubs:
            logger.warning(
                f"  - publication_id: {pub.get('publication_id')}\n"
                f"    name: {pub.get('name')}\n"
                f"    subscription_id: {pub.get('subscription_id')}\n"
                f"    subscription_type: {pub.get('subscription_type')}"
            )

        logger.warning(f"{'='*60}\n")

        # Ask for confirmation
        response = (
            input("Do you want to delete these publications? (yes/no): ")
            .strip()
            .lower()
        )

        if response != "yes":
            logger.info("Deletion cancelled")
            return

        # Delete bad publications
        deleted_count = 0
        for pub in bad_pubs:
            pub_id = pub.get("publication_id")
            try:
                # Delete from MongoDB
                result = await db.db.publications.delete_one({"publication_id": pub_id})

                if result.deleted_count > 0:
                    deleted_count += 1
                    logger.info(f"✓ Deleted: {pub_id}")
                else:
                    logger.error(f"✗ Failed to delete: {pub_id}")

            except Exception as e:
                logger.error(f"✗ Error deleting {pub_id}: {e}")

        logger.info(f"\n{'='*60}")
        logger.info(
            f"✅ Cleanup complete: Deleted {deleted_count}/{len(bad_pubs)} publications"
        )
        logger.info(f"{'='*60}")

        # Show remaining publications
        remaining = await db.get_publications(active_only=False)
        logger.info(f"\n📊 Remaining publications: {len(remaining)}")
        for pub in remaining:
            logger.info(
                f"  - {pub.get('publication_id')}: {pub.get('name')} "
                f"(subscription_id: {pub.get('subscription_id')})"
            )


async def main():
    """Run the cleanup process."""
    try:
        await clean_duplicate_publications()
        return 0
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
