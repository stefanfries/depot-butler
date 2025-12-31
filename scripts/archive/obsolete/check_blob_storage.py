"""Check Azure Blob Storage for archived PDFs."""

import asyncio

from depotbutler.services.blob_storage_service import BlobStorageService
from depotbutler.settings import Settings


async def main():
    settings = Settings()
    blob_service = BlobStorageService(
        container_name=settings.blob_storage.container_name
    )

    # List all blobs in megatrend-folger folder
    print("Checking Azure Blob Storage...")
    print()

    # Count files by year
    years = {}
    total = 0

    container_client = blob_service.blob_service_client.get_container_client(
        settings.blob_storage.container_name
    )

    # List all blobs (not just 2018+)
    blobs = container_client.list_blobs()
    for blob in blobs:
        year = blob.name.split("/")[0]
        years[year] = years.get(year, 0) + 1
        total += 1

    print(f"Total PDFs in blob storage: {total}")
    print()
    print("By year:")
    for year in sorted(years.keys()):
        print(f"  {year}: {years[year]} files")

    # Sample a few filenames
    print()
    print("Sample files:")
    blobs = container_client.list_blobs(name_starts_with="2025/megatrend-folger/")
    count = 0
    for blob in blobs:
        print(f"  - {blob.name}")
        count += 1
        if count >= 5:
            break


if __name__ == "__main__":
    asyncio.run(main())
