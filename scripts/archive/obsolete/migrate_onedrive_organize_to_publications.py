"""
Migrate onedrive_organize_by_year from app_config to publications collection.

This script:
1. Reads onedrive_organize_by_year from app_config (defaults to True)
2. Adds onedrive_organize_by_year field to all publications
3. Removes onedrive_base_folder_path and onedrive_organize_by_year from app_config
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def migrate() -> None:
    """Migrate onedrive settings from app_config to publications."""
    logger.info("Starting migration: onedrive_organize_by_year → publications")

    mongodb = await get_mongodb_service()
    assert mongodb.publication_repo is not None, (
        "Publication repository not initialized"
    )

    # Step 1: Read current app_config value
    organize_by_year = await mongodb.get_app_config(
        "onedrive_organize_by_year", default=True
    )
    logger.info(
        f"Current app_config value: onedrive_organize_by_year={organize_by_year}"
    )

    # Step 2: Get all publications
    publications = await mongodb.get_publications(active_only=False)
    logger.info(f"Found {len(publications)} publications")

    # Step 3: Update each publication
    updated_count = 0
    already_have_field = 0

    for pub in publications:
        pub_id = pub.get("publication_id", "unknown")
        pub_name = pub.get("name", "unknown")

        # Check if already has the field
        if "onedrive_organize_by_year" in pub:
            logger.info(
                f"  [{pub_id}] {pub_name} - Already has onedrive_organize_by_year={pub['onedrive_organize_by_year']}"
            )
            already_have_field += 1
            continue

        # Add the field
        result = await mongodb.publication_repo.update_publication(
            publication_id=pub_id,
            updates={"onedrive_organize_by_year": organize_by_year},
        )

        if result:
            logger.info(
                f"  ✅ [{pub_id}] {pub_name} - Added onedrive_organize_by_year={organize_by_year}"
            )
            updated_count += 1
        else:
            logger.error(f"  ❌ [{pub_id}] {pub_name} - Failed to update")

    logger.info(
        f"Updated {updated_count} publications, {already_have_field} already had the field"
    )

    # Step 4: Remove deprecated app_config settings if ALL publications have the field
    all_publications_have_field = (updated_count + already_have_field) == len(
        publications
    )

    if all_publications_have_field:
        logger.info(
            "\nAll publications updated. Removing deprecated app_config settings..."
        )

        # Access config collection via db attribute
        config_collection = mongodb.db.config

        # Remove onedrive_base_folder_path
        result1 = await config_collection.update_one(
            {"config_key": "app_config"}, {"$unset": {"onedrive_base_folder_path": ""}}
        )
        if result1.modified_count > 0:
            logger.info("  ✅ Removed onedrive_base_folder_path from app_config")
        else:
            logger.info("  ℹ️  onedrive_base_folder_path not found in app_config")

        # Remove onedrive_organize_by_year
        result2 = await config_collection.update_one(
            {"config_key": "app_config"}, {"$unset": {"onedrive_organize_by_year": ""}}
        )
        if result2.modified_count > 0:
            logger.info("  ✅ Removed onedrive_organize_by_year from app_config")
        else:
            logger.info("  ℹ️  onedrive_organize_by_year not found in app_config")

        logger.info("\n✅ Migration complete!")
    else:
        logger.warning(
            "\n⚠️  Some publications not updated. Keeping app_config settings as fallback."
        )

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(migrate())
