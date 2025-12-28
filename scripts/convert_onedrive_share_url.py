"""
Convert OneDrive share URL to shared folder format.

Usage:
    python scripts/convert_onedrive_share_url.py <share_url>

Example:
    python scripts/convert_onedrive_share_url.py "https://onedrive.live.com/?id=%2Fpersonal%2F1da839fa6c584797%2FDocuments%2FTSI"

Output:
    shared:1da839fa6c584797:1DA839FA6C584797!21807
"""

import asyncio
import re
import sys
from urllib.parse import parse_qs, unquote, urlparse

from depotbutler.onedrive.auth import OneDriveAuth


async def convert_share_url(share_url: str) -> str:
    """Convert OneDrive share URL to shared:DRIVE_ID:ITEM_ID format.

    Args:
        share_url: OneDrive share URL (e.g., https://onedrive.live.com/?id=...)

    Returns:
        Formatted string: shared:DRIVE_ID:ITEM_ID

    Raises:
        ValueError: If URL format is invalid or API request fails
    """
    # Parse the URL
    parsed = urlparse(share_url)
    query_params = parse_qs(parsed.query)

    # Extract the 'id' parameter
    if "id" not in query_params:
        raise ValueError(
            "Invalid OneDrive share URL: missing 'id' parameter. "
            "Expected format: https://onedrive.live.com/?id=..."
        )

    id_value = unquote(query_params["id"][0])

    # Extract drive ID from the path
    # Format: /personal/{DRIVE_ID}/Documents/... or /personal/{DRIVE_ID}!{ITEM_ID}
    match = re.search(r"/personal/([a-f0-9]+)", id_value, re.IGNORECASE)
    if not match:
        raise ValueError(
            f"Could not extract drive ID from URL. ID parameter: {id_value}"
        )

    drive_id = match.group(1).lower()

    # Extract folder path (everything after /personal/{DRIVE_ID}/)
    folder_path_match = re.search(r"/personal/[a-f0-9]+/(.+)", id_value, re.IGNORECASE)
    if not folder_path_match:
        raise ValueError(
            f"Could not extract folder path from URL. ID parameter: {id_value}"
        )

    folder_path = folder_path_match.group(1)

    print(f"✓ Extracted drive ID: {drive_id}")
    print(f"✓ Extracted folder path: {folder_path}")

    # Use OneDrive API to get the item ID
    print("\n🔍 Looking up item ID via Microsoft Graph API...")

    from depotbutler.settings import Settings

    settings = Settings()
    auth = OneDriveAuth(settings)
    await auth.authenticate()
    token = auth.get_access_token()

    import httpx

    async with httpx.AsyncClient() as client:
        # Try to get the item ID by path
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{folder_path}"
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            raise ValueError(
                f"Failed to lookup folder via Graph API (HTTP {response.status_code}): {response.text}"
            )

        data = response.json()
        item_id = data.get("id")

        if not item_id:
            raise ValueError(f"API response missing 'id' field: {data}")

        print(f"✓ Found item ID: {item_id}")

    # Format the result
    result = f"shared:{drive_id}:{item_id}"
    return result


async def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("ERROR: Missing share URL argument")
        print()
        print(__doc__)
        sys.exit(1)

    share_url = sys.argv[1]

    print("📋 Converting OneDrive share URL...")
    print(f"   URL: {share_url}")
    print()

    try:
        result = await convert_share_url(share_url)
        print()
        print("=" * 70)
        print("✅ SUCCESS!")
        print("=" * 70)
        print()
        print("Use this value with set_custom_onedrive_folder.py:")
        print()
        print(f'  --folder "{result}"')
        print()
        print("Full example:")
        print()
        print("  python scripts/set_custom_onedrive_folder.py \\")
        print("    --email recipient@example.com \\")
        print("    --publication der-aktionaer-epaper \\")
        print(f'    --folder "{result}"')
        print()

    except Exception as e:
        print()
        print("=" * 70)
        print("❌ ERROR")
        print("=" * 70)
        print()
        print(f"Failed to convert URL: {e}")
        print()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
