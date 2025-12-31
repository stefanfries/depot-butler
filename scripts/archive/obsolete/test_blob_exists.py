"""Test if specific blobs exist in Azure."""

from azure.storage.blob import BlobServiceClient

from depotbutler.settings import Settings

settings = Settings()

# Use connection string from settings
client = BlobServiceClient.from_connection_string(
    settings.blob_storage.connection_string.get_secret_value()
)

container = client.get_container_client("editions")

test_paths = [
    "2014/megatrend-folger/2014-03-06_Die-800-Prozent-Strategie_01-2014.pdf",
    "2015/megatrend-folger/2015-01-08_Die-800-Prozent-Strategie_02-2015.pdf",
    "2016/megatrend-folger/2016-01-07_Die-800-Prozent-Strategie_01-2016.pdf",
    "2017/megatrend-folger/2017-01-05_Die-800-Prozent-Strategie_01-2017.pdf",
]

print("\n🔍 Checking if early year blobs exist in Azure:")
for path in test_paths:
    blob_client = container.get_blob_client(path)
    exists = blob_client.exists()
    print(f"  {path[:50]}... {'✓ EXISTS' if exists else '✗ NOT FOUND'}")
