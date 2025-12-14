"""
Enhanced OneDrive folder explorer.

Usage:
    python scripts/list_onedrive_folders.py                    # List common locations
    python scripts/list_onedrive_folders.py --path "Documents" # List specific path
    python scripts/list_onedrive_folders.py --recursive        # Recursive listing
    python scripts/list_onedrive_folders.py --test-upload      # Test upload permissions
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from depotbutler.onedrive import OneDriveService
from depotbutler.settings import Settings

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def list_onedrive_folders(
    specific_path: str | None = None, recursive: bool = False, test_upload: bool = False
):
    """List OneDrive folders with various options."""
    onedrive = OneDriveService()

    try:
        print("\n🔐 Authenticating with OneDrive...")
        auth_success = await onedrive.authenticate()

        if not auth_success:
            print("❌ Authentication failed")
            return

        print("✓ Authentication successful\n")

        if test_upload:
            await test_upload_permission(onedrive)
            return

        if specific_path:
            # List specific path
            print(f"=== Listing: {specific_path} ===\n")
            await list_folder(onedrive, specific_path, recursive=recursive, indent=0)
        else:
            # List common locations
            settings = Settings()
            configured_path = settings.onedrive.base_folder_path

            print("=== Configured Path (from .env) ===")
            print(f"ONEDRIVE_BASE_FOLDER_PATH: {configured_path}\n")

            print("=== Root Level Folders ===")
            await list_folder(onedrive, "", recursive=False, indent=0)

            if configured_path:
                print(f"\n=== Your Configured Path: {configured_path} ===")
                await list_folder(
                    onedrive, configured_path, recursive=recursive, indent=0
                )

    finally:
        await onedrive.close()


async def list_folder(onedrive, path, recursive=False, indent=0):
    """List contents of a folder with optional recursion."""
    prefix = "  " * indent

    try:
        files = await onedrive.list_files(path)

        if not files:
            print(f"{prefix}  (empty or inaccessible)")
            return

        # Separate folders and files
        folders = [f for f in files if f.get("folder")]
        regular_files = [f for f in files if not f.get("folder")]

        # List folders first
        for item in folders:
            name = item.get("name", "Unknown")
            is_shared = item.get("remoteItem") is not None
            shared_marker = " [Shared]" if is_shared else ""

            print(f"{prefix}📁 {name}{shared_marker}")

            # Recurse if requested
            if recursive:
                child_path = f"{path}/{name}" if path else name
                await list_folder(
                    onedrive, child_path, recursive=True, indent=indent + 1
                )

        # Then list files
        for item in regular_files:
            name = item.get("name", "Unknown")
            size = item.get("size", 0)
            size_mb = size / (1024 * 1024) if size else 0

            print(f"{prefix}📄 {name} ({size_mb:.2f} MB)")

        # Summary
        if indent == 0:
            print(
                f"\n{prefix}Summary: {len(folders)} folders, {len(regular_files)} files"
            )

    except Exception as e:
        print(f"{prefix}❌ Error: {e}")


async def test_upload_permission(onedrive):
    """Test upload permission to configured folder."""
    settings = Settings()
    test_folder = settings.onedrive.base_folder_path

    print(f"=== Testing Upload Permission ===")
    print(f"Target folder: {test_folder}\n")

    # Create a small test file
    test_filename = f"test-upload-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    test_content = (
        f"Test upload from DepotButler\nTimestamp: {datetime.now().isoformat()}\n"
    )

    print(f"📝 Creating test file: {test_filename}")

    try:
        # Try to upload
        from io import BytesIO

        test_file = BytesIO(test_content.encode())

        print(f"☁️  Uploading to OneDrive...")
        result = await onedrive.upload_file(
            file_content=test_file,
            filename=test_filename,
            folder_path=test_folder,
            organize_by_year=False,
        )

        if result and result.success:
            print(f"✅ Upload successful!")
            print(f"   File URL: {result.onedrive_url}")
            print(f"\n⚠️  Note: You may want to delete this test file from OneDrive")
        else:
            print(f"❌ Upload failed: {result.error if result else 'Unknown error'}")

    except Exception as e:
        print(f"❌ Upload test failed: {e}")


async def main():
    parser = argparse.ArgumentParser(description="List and explore OneDrive folders")
    parser.add_argument("--path", help="Specific path to list")
    parser.add_argument(
        "--recursive", "-r", action="store_true", help="List subfolders recursively"
    )
    parser.add_argument(
        "--test-upload", "-t", action="store_true", help="Test upload permission"
    )

    args = parser.parse_args()

    await list_onedrive_folders(
        specific_path=args.path, recursive=args.recursive, test_upload=args.test_upload
    )


if __name__ == "__main__":
    asyncio.run(main())
