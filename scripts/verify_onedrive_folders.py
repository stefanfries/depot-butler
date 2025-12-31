"""Verify OneDrive folder access and structure."""

import asyncio

from depotbutler.db.mongodb import MongoDBService
from depotbutler.onedrive.service import OneDriveService
from depotbutler.settings import Settings


async def verify_folders() -> None:
    """Verify OneDrive folder paths are accessible."""
    settings = Settings()
    db = MongoDBService()
    onedrive = OneDriveService()

    try:
        # Connect to services
        await db.connect()
        await onedrive.authenticate()

        print("\n=== Verifying OneDrive Folder Access ===\n")

        # Get publications
        publications = await db.get_publications()

        for pub in publications:
            pub_id = pub["publication_id"]
            folder = pub.get("default_onedrive_folder", "")
            organize = pub.get("onedrive_organize_by_year", True)

            if not folder:
                print(f"❌ {pub_id}: No folder configured")
                continue

            print(f"Publication: {pub_id}")
            print(f"  Base folder: {folder}")

            # Test with 2025 year
            if organize:
                test_path = f"{folder}/2025"
                print(f"  Test path: {test_path}")
            else:
                test_path = folder
                print(f"  Test path: {test_path}")

            # Try to create/access the folder
            folder_id = await onedrive.create_folder_path(test_path)

            if folder_id:
                print(f"  ✅ Accessible (folder_id: {folder_id[:20]}...)")
            else:
                print("  ❌ Failed to access")

            print()

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(verify_folders())
