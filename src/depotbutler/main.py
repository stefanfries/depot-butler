import pathlib

from .client import MegatrendClient
from .utils.helpers import create_filename


async def main():

    print("DepotButler starting...")
    client = MegatrendClient()
    await client.login()

    edition = await client.get_latest_edition()
    _ = await client.get_publication_date(edition)

    filename = create_filename(edition)

    cwd = pathlib.Path.cwd()
    filepath = cwd / "downloads" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading edition {edition.title} to: {filepath}")
    response = await client.download_edition(edition, str(filepath))
    print(f"Download result: {response.status_code}")
    await client.close()
