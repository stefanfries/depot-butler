"""List OneDrive folders to find the shared folder path."""

import asyncio
import os
from depotbutler.onedrive import OneDriveService


async def list_onedrive_folders():
    """List OneDrive folders to find shared folder."""
    onedrive = OneDriveService()
    
    try:
        await onedrive.authenticate()
        
        # List root folders
        print("=== Root Level Folders ===")
        await list_folder(onedrive, "")
        
        # Check common locations
        print("\n=== Checking Documents ===")
        await list_folder(onedrive, "Documents")
        
        print("\n=== Checking root ===")
        await list_folder(onedrive, "root")
        
    finally:
        await onedrive.close()


async def list_folder(onedrive, path):
    """List contents of a folder."""
    try:
        files = await onedrive.list_files(path)
        
        if not files:
            print(f"  (empty or inaccessible)")
            return
            
        for item in files:
            item_type = "📁" if item.get("folder") else "📄"
            name = item.get("name", "Unknown")
            print(f"  {item_type} {name}")
            
            # Show if it's a shared item
            if item.get("remoteItem"):
                print(f"      ↳ Shared from another OneDrive")
                
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    asyncio.run(list_onedrive_folders())
