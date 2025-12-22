"""
OneDrive folder management operations.
Handles hierarchical folder creation and verification.
"""

from collections.abc import Callable

import httpx

from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class FolderManager:
    """
    Manages OneDrive folder operations.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        graph_url: str,
        get_auth_header_func: Callable[[], dict[str, str]],
    ) -> None:
        """
        Initialize folder manager.

        Args:
            http_client: Async HTTP client for API requests
            graph_url: Microsoft Graph API base URL
            get_auth_header_func: Function that returns authorization header dict
        """
        self.http_client = http_client
        self.graph_url = graph_url
        self.get_auth_header = get_auth_header_func

    async def create_folder_path(self, folder_path: str) -> str | None:
        """
        Create a hierarchical folder path in OneDrive.
        Returns the final folder ID if successful, None otherwise.

        Args:
            folder_path: Path like "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent/2025"
        """
        try:
            # Split path into individual folder names
            folder_names = [name for name in folder_path.split("/") if name.strip()]

            current_parent_id = None  # Start from root

            for folder_name in folder_names:
                folder_id = await self._create_or_get_folder(
                    folder_name, current_parent_id
                )
                if not folder_id:
                    logger.error("Failed to create/get folder: %s", folder_name)
                    return None
                current_parent_id = folder_id

            logger.info("Successfully created/verified folder path: %s", folder_path)
            return current_parent_id

        except Exception as e:
            logger.error("Error creating folder path '%s': %s", folder_path, e)
            return None

    async def _create_or_get_folder(
        self, folder_name: str, parent_id: str | None = None
    ) -> str | None:
        """
        Create or get a single folder in the specified parent location.

        Args:
            folder_name: Name of the folder to create/get
            parent_id: Parent folder ID (None for root)

        Returns:
            Folder ID if successful, None otherwise
        """
        try:
            # Determine the endpoint for listing children (no filter - we'll filter in Python)
            if parent_id:
                list_endpoint = f"me/drive/items/{parent_id}/children"
            else:
                list_endpoint = "me/drive/root/children"

            # Check if folder already exists
            response = await self._make_request("GET", list_endpoint)

            if response.status_code == 200:
                data = response.json()
                all_items = data.get("value", [])

                # Filter for folders with matching name in Python
                folders = [
                    item
                    for item in all_items
                    if item.get("folder") is not None
                    and item.get("name") == folder_name
                ]

                if folders:
                    folder_data = folders[0]
                    logger.info("Folder '%s' already exists", folder_name)
                    return str(folder_data["id"])
                else:
                    # Folder doesn't exist, create it
                    return await self._create_single_folder(folder_name, parent_id)
            else:
                logger.error(
                    "Failed to list children for folder check: %s", response.text
                )
                return None

        except Exception as e:
            logger.error("Error checking/creating folder '%s': %s", folder_name, e)
            return None

    async def _create_single_folder(
        self, folder_name: str, parent_id: str | None = None
    ) -> str | None:
        """Create a single folder in the specified parent location."""
        try:
            import json

            create_data = {
                "name": folder_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "rename",
            }

            # Determine the endpoint for creating folder
            if parent_id:
                create_endpoint = f"me/drive/items/{parent_id}/children"
            else:
                create_endpoint = "me/drive/root/children"

            response = await self._make_request(
                "POST",
                create_endpoint,
                data=json.dumps(create_data).encode(),
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 201:
                folder_data = response.json()
                logger.info("Created folder '%s'", folder_name)
                return str(folder_data["id"])
            else:
                logger.error(
                    "Failed to create folder '%s': %s", folder_name, response.text
                )
                return None

        except Exception as e:
            logger.error("Error creating folder '%s': %s", folder_name, e)
            return None

    async def create_folder_if_not_exists(self, folder_name: str) -> str | None:
        """
        Legacy method for backward compatibility.
        Creates a single folder in root. Use create_folder_path for hierarchical paths.
        """
        return await self._create_or_get_folder(folder_name, None)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: bytes | None = None,
        json: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make authenticated request to Microsoft Graph API."""
        # Fix URL construction - ensure endpoint starts without leading slash
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]

        url = f"{self.graph_url}/{endpoint}"
        auth_headers = self.get_auth_header()

        if headers:
            auth_headers.update(headers)

        try:
            response = await self.http_client.request(
                method=method, url=url, content=data, json=json, headers=auth_headers
            )
            return response  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(
                f"Graph API request failed: {method} {url}: {type(e).__name__}: {e}"
            )
            raise
