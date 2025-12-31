import asyncio

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService


async def check_state():
    db = await get_mongodb_service()
    blob_service = BlobStorageService()

    # Sample from MongoDB
    sample = await db.db["processed_editions"].find_one(
        {"edition_key": "2019_18_megatrend-folger"}
    )

    print(f"MongoDB edition: {sample['edition_key']}")
    print(f"  publication_id: {sample['publication_id']}")
    print(f"  blob_path: {sample['blob_path']}")

    # Check actual blob
    blob_client = blob_service.container_client.get_blob_client(sample["blob_path"])
    try:
        exists = blob_client.exists()
        print(f"\nBlob exists at this path: {exists}")

        if exists:
            props = blob_client.get_blob_properties()
            meta = props.metadata or {}
            print(
                f"  Blob metadata publication_id: {meta.get('publication_id', 'NOT SET')}"
            )
    except Exception as e:
        print(f"  Error checking blob: {e}")

    # Check old path
    old_path = sample["blob_path"].replace(
        "/megatrend-folger/", "/die-800-prozent-strategie/"
    )
    old_client = blob_service.container_client.get_blob_client(old_path)
    try:
        old_exists = old_client.exists()
        print(f"\nOld path still exists: {old_exists}")
        if old_exists:
            print(f"  Old path: {old_path}")
    except Exception as e:
        print(f"  Error: {e}")


asyncio.run(check_state())
