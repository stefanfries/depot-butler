"""Check current OneDrive folder configuration in MongoDB."""

import asyncio

from depotbutler.db.mongodb import MongoDBService
from depotbutler.settings import Settings


async def check_folders() -> None:
    """Display current OneDrive folder paths for all publications."""
    settings = Settings()
    db = MongoDBService()

    try:
        await db.connect()
        print("\n=== OneDrive Folder Configuration ===\n")

        # Get all publications
        publications = await db.get_publications()

        if not publications:
            print("No publications found in database.")
            return

        for pub in publications:
            pub_id = pub["publication_id"]
            folder = pub.get("default_onedrive_folder", "NOT SET")
            organize = pub.get("onedrive_organize_by_year", "NOT SET")
            active = pub.get("active", False)

            print(f"Publication: {pub_id}")
            print(f"  Active: {active}")
            print(f"  Folder: {folder}")
            print(f"  Organize by year: {organize}")
            print()

        # Check global setting
        print("Global setting (from settings.py):")
        print(f"  organize_by_year: {settings.onedrive.organize_by_year}")
        print()

        # Check for any recipient-specific overrides
        try:
            # Get recipients through publication repo
            if db.publication_repo:
                override_count = 0
                for pub in publications:
                    recipients_with_prefs = (
                        await db.publication_repo.get_recipients_with_preferences(
                            pub["publication_id"]
                        )
                    )
                    for recipient in recipients_with_prefs:
                        custom_folder = recipient.get("custom_onedrive_folder")
                        if custom_folder:
                            if override_count == 0:
                                print("=== Recipient-Specific Folder Overrides ===\n")
                            print(
                                f"{recipient.get('email', 'unknown')} → {pub['publication_id']}: {custom_folder}"
                            )
                            override_count += 1

                if override_count > 0:
                    print(f"\nTotal recipient overrides: {override_count}")
                else:
                    print("No recipient-specific folder overrides found.")
        except Exception as e:
            print(f"Could not check recipient overrides: {e}")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(check_folders())
