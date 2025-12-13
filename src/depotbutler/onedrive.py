"""
OneDrive integration using Microsoft Graph API via MSAL.
Designed for Azure Container deployment with refresh token authentication.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import msal
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from depotbutler.models import Edition, UploadResult
from depotbutler.settings import Settings
from depotbutler.utils.helpers import create_filename
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class OneDriveService:
    """
    OneDrive service for uploading files using Microsoft Graph API.
    Supports both local development and Azure Container deployment.
    """

    def __init__(self):
        self.settings = Settings()
        self.client_id = self.settings.onedrive.client_id
        self.client_secret = self.settings.onedrive.client_secret.get_secret_value()
        self.refresh_token = self._get_refresh_token()

        # Microsoft Graph API endpoints
        # Use consumers endpoint for personal Microsoft accounts
        self.authority = "https://login.microsoftonline.com/consumers"
        self.graph_url = "https://graph.microsoft.com/v1.0"
        self.scopes = ["https://graph.microsoft.com/Files.ReadWrite.All"]

        # Initialize MSAL app
        self.msal_app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority,
        )

        self.access_token: Optional[str] = None
        self.http_client = httpx.AsyncClient()

    def _get_refresh_token(self) -> Optional[str]:
        """
        Get refresh token from environment variable or Azure Key Vault.
        Priority: Environment Variable > Azure Key Vault > None
        """
        # Try environment variable first (for container deployment)
        # refresh_token = os.getenv("ONEDRIVE_REFRESH_TOKEN")
        refresh_token = self.settings.onedrive.refresh_token.get_secret_value()
        if refresh_token:
            logger.info("Using refresh token from environment variable")
            return refresh_token

        # Try Azure Key Vault (for enhanced security)
        try:
            key_vault_url = os.getenv("AZURE_KEY_VAULT_URL")
            if key_vault_url:
                credential = DefaultAzureCredential()
                client = SecretClient(vault_url=key_vault_url, credential=credential)
                secret = client.get_secret("onedrive-refresh-token")
                logger.info("Using refresh token from Azure Key Vault")
                return secret.value
        except Exception as e:
            logger.warning("Could not retrieve refresh token from Key Vault: %s", e)

        logger.error("No refresh token found. Please run initial authentication.")
        return None

    async def authenticate(self) -> bool:
        """
        Authenticate using refresh token and get access token.
        Returns True if successful, False otherwise.
        """
        if not self.refresh_token:
            logger.error("No refresh token available. Cannot authenticate.")
            return False

        try:
            # Use refresh token to get new access token
            result = self.msal_app.acquire_token_by_refresh_token(
                refresh_token=self.refresh_token, scopes=self.scopes
            )

            if "access_token" in result:
                self.access_token = result["access_token"]
                logger.info("Successfully authenticated with OneDrive")
                return True
            else:
                logger.error(
                    "Authentication failed: %s",
                    result.get("error_description", "Unknown error"),
                )
                return False

        except Exception as e:
            logger.error("Authentication error: %s", e)
            return False

    async def _make_graph_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Make authenticated request to Microsoft Graph API."""
        if not self.access_token:
            raise ValueError("Not authenticated. Call authenticate() first.")

        # Fix URL construction - ensure endpoint starts without leading slash
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]

        url = f"{self.graph_url}/{endpoint}"
        auth_headers = {"Authorization": f"Bearer {self.access_token}"}

        if headers:
            auth_headers.update(headers)

        response = await self.http_client.request(
            method=method, url=url, content=data, headers=auth_headers
        )

        return response

    async def create_folder_path(self, folder_path: str) -> Optional[str]:
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
        self, folder_name: str, parent_id: Optional[str] = None
    ) -> Optional[str]:
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
                list_endpoint = f"me/drive/root/children"

            # Check if folder already exists
            response = await self._make_graph_request("GET", list_endpoint)

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
                    return folder_data["id"]
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
        self, folder_name: str, parent_id: Optional[str] = None
    ) -> Optional[str]:
        """Create a single folder in the specified parent location."""
        try:
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

            response = await self._make_graph_request(
                "POST",
                create_endpoint,
                data=json.dumps(create_data).encode(),
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 201:
                folder_data = response.json()
                logger.info("Created folder '%s'", folder_name)
                return folder_data["id"]
            else:
                logger.error(
                    "Failed to create folder '%s': %s", folder_name, response.text
                )
                return None

        except Exception as e:
            logger.error("Error creating folder '%s': %s", folder_name, e)
            return None

    async def create_folder_if_not_exists(self, folder_name: str) -> Optional[str]:
        """
        Legacy method for backward compatibility.
        Creates a single folder in root. Use create_folder_path for hierarchical paths.
        """
        return await self._create_or_get_folder(folder_name, None)

    async def upload_file(
        self, local_file_path: str, edition: Edition, folder_name: Optional[str] = None
    ) -> UploadResult:
        """
        Upload file to OneDrive with hierarchical folder organization.
        Uses your existing create_filename helper.
        """
        try:
            if not await self.authenticate():
                return UploadResult(
                    success=False,
                    error="Authentication failed",
                )

            # Generate filename using your existing helper
            filename = create_filename(edition)
            logger.info("Generated filename: %s", filename)

            # Build the folder path based on publication settings
            from depotbutler.db.mongodb import get_mongodb_service

            mongodb = await get_mongodb_service()

            # Validate that publication-specific folder is provided
            if not folder_name:
                error_msg = "No default_onedrive_folder configured for this publication"
                logger.error(error_msg)
                return UploadResult(success=False, error=error_msg)

            base_folder_path = folder_name
            logger.info("Using publication folder: %s", base_folder_path)

            # Check if organize_by_year is enabled (global setting)
            settings = Settings()
            organize_by_year = await mongodb.get_app_config(
                "onedrive_organize_by_year", default=settings.onedrive.organize_by_year
            )

            if organize_by_year:
                # Extract year from first 4 characters of filename (YYYY-MM-dd format)
                year = filename[:4]
                folder_path = f"{base_folder_path}/{year}"
            else:
                # Use base folder path as-is
                folder_path = base_folder_path

            logger.info("Target folder path: %s", folder_path)

            # Create the full folder hierarchy
            folder_id = await self.create_folder_path(folder_path)
            if not folder_id:
                return UploadResult(
                    success=False,
                    error=f"Failed to create folder path: {folder_path}",
                )

            # Read file content
            file_path = Path(local_file_path)
            if not file_path.exists():
                return UploadResult(
                    success=False, error=f"Local file not found: {local_file_path}"
                )

            file_content = file_path.read_bytes()
            file_size = len(file_content)
            logger.info("Uploading file: %s (%s bytes)", filename, file_size)

            # Upload endpoint with conflict behavior
            upload_endpoint = f"me/drive/items/{folder_id}:/{filename}:/content?@microsoft.graph.conflictBehavior=replace"

            # Headers for file upload
            headers = {
                "Content-Type": "application/octet-stream",
            }

            # Upload file
            response = await self._make_graph_request(
                "PUT", upload_endpoint, data=file_content, headers=headers
            )

            if response.status_code in [200, 201]:
                file_data = response.json()
                file_url = file_data.get("webUrl", "")

                logger.info(
                    "Successfully uploaded '%s' to OneDrive folder: %s",
                    filename,
                    folder_path,
                )
                return UploadResult(
                    success=True,
                    file_id=file_data.get("id"),
                    file_url=file_url,
                    filename=filename,
                    size=file_size,
                )
            else:
                error_msg = f"Upload failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return UploadResult(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            logger.error(error_msg)
            return UploadResult(success=False, error=error_msg)

    async def list_files(
        self, folder_name: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """
        List files in OneDrive folder.
        Useful for checking existing files or cleanup.
        """
        try:
            if folder_name:
                folder_id = await self.create_folder_if_not_exists(folder_name)
                if not folder_id:
                    return []
                endpoint = f"/me/drive/items/{folder_id}/children"
            else:
                endpoint = "/me/drive/root/children"

            response = await self._make_graph_request("GET", endpoint)

            if response.status_code == 200:
                data = response.json()
                return data.get("value", [])
            else:
                logger.error("Failed to list files: %s", response.text)
                return []

        except Exception as e:
            logger.error("Error listing files: %s", e)
            return []

    async def close(self):
        """Clean up HTTP client."""
        await self.http_client.aclose()


class OneDriveAuthenticator:
    """
    Helper class for initial authentication setup.
    Use this locally to generate refresh token, then store in Azure Container.
    """

    def __init__(self):
        self.settings = Settings()
        self.client_id = self.settings.onedrive.client_id
        self.client_secret = self.settings.onedrive.client_secret.get_secret_value()
        self.redirect_uri = (
            "http://localhost:8080/"  # For local auth flow (with trailing slash)
        )

        # Use consumers endpoint for personal Microsoft accounts
        self.authority = "https://login.microsoftonline.com/consumers"
        self.scopes = ["https://graph.microsoft.com/Files.ReadWrite.All"]

        self.msal_app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority,
        )

    def get_authorization_url(self) -> str:
        """
        Get authorization URL for initial setup.
        Open this URL in browser to grant permissions.
        """
        auth_url = self.msal_app.get_authorization_request_url(
            scopes=self.scopes, redirect_uri=self.redirect_uri
        )
        return auth_url

    def exchange_code_for_tokens(self, authorization_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens.
        Save the refresh_token to Azure Container environment variables.
        """
        result = self.msal_app.acquire_token_by_authorization_code(
            code=authorization_code, scopes=self.scopes, redirect_uri=self.redirect_uri
        )

        if "refresh_token" in result:
            print(f"SUCCESS! Save this refresh token to Azure Container:")
            print(f"ONEDRIVE_REFRESH_TOKEN={result['refresh_token']}")
            return result
        else:
            print(f"ERROR: {result.get('error_description', 'Unknown error')}")
            return result
