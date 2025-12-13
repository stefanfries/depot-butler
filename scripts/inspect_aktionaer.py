"""Inspect DER AKTIONÄR E-Paper subscription."""

import asyncio
import sys

from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.publications import PublicationConfig


async def inspect_aktionaer():
    """Check DER AKTIONÄR E-Paper details."""
    client = HttpxBoersenmedienClient()
    await client.login()

    subscriptions = await client.discover_subscriptions()

    for sub in subscriptions:
        if "AKTIONÄR" in sub.name.upper():
            print(f"Found: {sub.name}")
            print(f"ID: {sub.subscription_id}")
            print(f"Number: {sub.subscription_number}")
            print(f"URL: {sub.content_url}\n")

            # Try to get latest edition
            test_pub = PublicationConfig(
                id="test", name=sub.name, onedrive_folder="test"
            )

            edition = await client.get_latest_edition(test_pub)
            if edition:
                print(f"Latest Edition:")
                print(f"  Title: {edition.title}")
                print(f"  Date: {edition.publication_date}")
                print(f"  Download URL: {edition.download_url}")
            else:
                print("No edition found")

    await client.close()


if __name__ == "__main__":
    sys.path.insert(0, "src")
    asyncio.run(inspect_aktionaer())
