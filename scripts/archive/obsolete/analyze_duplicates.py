"""
Analyze the duplicate situation more carefully
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.services.blob_storage_service import BlobStorageService


async def main():
    print("=" * 80)
    print("ANALYZING DUPLICATE FILE SITUATION")
    print("=" * 80)

    blob_service = BlobStorageService()
    blob_list = blob_service.container_client.list_blobs()

    # Create lookup dictionaries
    percent_files = {}  # key: normalized path -> full path
    prozent_files = {}  # key: normalized path -> full path

    for blob in blob_list:
        if "Die-800%-Strategie" in blob.name:
            # Normalize by removing the specific pattern
            normalized = blob.name.replace("Die-800%-Strategie", "NORMALIZED")
            percent_files[normalized] = blob.name
        elif "Die-800-Prozent-Strategie" in blob.name:
            normalized = blob.name.replace("Die-800-Prozent-Strategie", "NORMALIZED")
            prozent_files[normalized] = blob.name

    print(f"% files: {len(percent_files)}")
    print(f"-Prozent files: {len(prozent_files)}")

    # Find which have both versions
    both_versions = set(percent_files.keys()) & set(prozent_files.keys())
    only_percent = set(percent_files.keys()) - set(prozent_files.keys())
    only_prozent = set(prozent_files.keys()) - set(percent_files.keys())

    print(f"\nFiles with BOTH versions: {len(both_versions)}")
    print(f"Files with ONLY % version: {len(only_percent)}")
    print(f"Files with ONLY -Prozent version: {len(only_prozent)}")

    if both_versions:
        print("\nFirst 5 files with both versions:")
        for norm_path in list(both_versions)[:5]:
            print(f"  % version: {percent_files[norm_path]}")
            print(f"  -Prozent:  {prozent_files[norm_path]}")
            print()

    if only_percent:
        print("\nFirst 5 files with ONLY % version (NO -Prozent equivalent):")
        for norm_path in list(only_percent)[:5]:
            print(f"  {percent_files[norm_path]}")

    if only_prozent:
        print("\nFirst 5 files with ONLY -Prozent version (NO % equivalent):")
        for norm_path in list(only_prozent)[:5]:
            print(f"  {prozent_files[norm_path]}")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("Strategy needed:")
    if len(only_percent) > 0:
        print(
            f"  1. For {len(only_percent)} files: RENAME % to -Prozent (no duplicate exists)"
        )
        print(f"  2. For {len(both_versions)} files: DELETE % version (keep -Prozent)")
    else:
        print(f"  1. For {len(both_versions)} files: DELETE % version (keep -Prozent)")


if __name__ == "__main__":
    asyncio.run(main())
