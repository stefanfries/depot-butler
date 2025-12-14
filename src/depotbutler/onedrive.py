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
        json: Optional[dict] = None,
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

        try:
            response = await self.http_client.request(
                method=method, url=url, content=data, json=json, headers=auth_headers
            )
            return response
        except Exception as e:
            logger.error(
                f"Graph API request failed: {method} {url}: {type(e).__name__}: {e}"
            )
            raise

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
        self,
        local_file_path: str,
        edition: Edition,
        folder_name: Optional[str] = None,
        organize_by_year: bool = True,
    ) -> UploadResult:
        """
        Upload file to OneDrive with hierarchical folder organization.
        Uses your existing create_filename helper.

        Args:
            local_file_path: Path to the local file to upload
            edition: Edition information for filename generation
            folder_name: Base folder path (required - from publication config)
            organize_by_year: Whether to add /YYYY subfolder (default: True)
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

            # Build folder path based on organize_by_year setting
            if organize_by_year:
                # Extract year from first 4 characters of filename (YYYY-MM-dd format)
                year = filename[:4]
                folder_path = f"{base_folder_path}/{year}"
                logger.info("Organizing by year: %s", year)
            else:
                # Use base folder path as-is
                folder_path = base_folder_path
                logger.info("Not organizing by year")

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

            file_size = file_path.stat().st_size
            logger.info("Uploading file: %s (%s bytes)", filename, file_size)

            # Use chunked upload for large files (>4MB)
            if file_size > 4 * 1024 * 1024:
                logger.info("Using chunked upload for large file")
                return await self._upload_large_file(
                    file_path, folder_id, filename, folder_path
                )

            # Simple upload for small files
            file_content = file_path.read_bytes()

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
            error_msg = (
                f"Upload error: {type(e).__name__}: {str(e) or 'No error message'}"
            )
            logger.error(error_msg, exc_info=True)
            return UploadResult(success=False, error=error_msg)

    async def _upload_large_file(
        self, file_path: Path, folder_id: str, filename: str, folder_path: str
    ) -> UploadResult:
        """
        Upload large file using upload session (chunked upload).

        For files larger than 4MB, OneDrive recommends using upload sessions
        with chunks up to 320 KiB (327,680 bytes) per request.

        Args:
            file_path: Path to the local file
            folder_id: Target OneDrive folder ID
            filename: Target filename in OneDrive
            folder_path: Folder path for logging

        Returns:
            UploadResult with upload status
        """
        try:
            file_size = file_path.stat().st_size

            # Create upload session
            session_endpoint = (
                f"me/drive/items/{folder_id}:/{filename}:/createUploadSession"
            )
            session_payload = {
                "item": {
                    "@microsoft.graph.conflictBehavior": "replace",
                    "name": filename,
                }
            }

            response = await self._make_graph_request(
                "POST", session_endpoint, json=session_payload
            )

            if response.status_code not in [200, 201]:
                error_msg = f"Failed to create upload session: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return UploadResult(success=False, error=error_msg)

            upload_url = response.json().get("uploadUrl")
            if not upload_url:
                return UploadResult(
                    success=False, error="No uploadUrl in session response"
                )

            # Upload in chunks (320 KiB per chunk as recommended)
            chunk_size = 320 * 1024  # 327,680 bytes
            total_chunks = (file_size + chunk_size - 1) // chunk_size

            logger.info(
                f"Uploading {file_size} bytes in {total_chunks} chunks of {chunk_size} bytes"
            )

            with file_path.open("rb") as f:
                for chunk_num in range(total_chunks):
                    start = chunk_num * chunk_size
                    end = min(start + chunk_size, file_size)
                    chunk_data = f.read(chunk_size)

                    # Content-Range header
                    headers = {
                        "Content-Length": str(len(chunk_data)),
                        "Content-Range": f"bytes {start}-{end-1}/{file_size}",
                    }

                    logger.info(
                        f"Uploading chunk {chunk_num + 1}/{total_chunks} ({start}-{end-1}/{file_size})"
                    )

                    # Upload chunk directly to upload URL (no authorization needed)
                    chunk_response = await self.http_client.request(
                        method="PUT",
                        url=upload_url,
                        content=chunk_data,
                        headers=headers,
                        timeout=60.0,  # Longer timeout for chunks
                    )

                    # Check for errors on non-final chunks (should be 202 Accepted)
                    if chunk_num < total_chunks - 1:
                        if chunk_response.status_code not in [200, 202]:
                            error_msg = f"Chunk upload failed: {chunk_response.status_code} - {chunk_response.text}"
                            logger.error(error_msg)
                            return UploadResult(success=False, error=error_msg)
                    # Final chunk should return 200/201 with file metadata
                    else:
                        if chunk_response.status_code not in [200, 201]:
                            error_msg = f"Final chunk upload failed: {chunk_response.status_code} - {chunk_response.text}"
                            logger.error(error_msg)
                            return UploadResult(success=False, error=error_msg)

                        file_data = chunk_response.json()
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

            # Should not reach here
            return UploadResult(success=False, error="Upload completed but no response")

        except Exception as e:
            error_msg = f"Chunked upload error: {type(e).__name__}: {str(e) or 'No error message'}"
            logger.error(error_msg, exc_info=True)
            return UploadResult(success=False, error=error_msg)

    async def upload_for_recipients(
        self, edition: Edition, publication: dict, local_path: str
    ) -> list[UploadResult]:
        """
        Upload file to OneDrive for all recipients subscribed to this publication.

        This method:
        1. Gets all recipients with upload enabled for the publication
        2. Resolves custom folder and organize_by_year per recipient
        3. Uploads to each recipient's folder
        4. Returns aggregated results

        Args:
            edition: Edition information
            publication: Publication document with settings
            local_path: Local file path to upload

        Returns:
            List of UploadResult (one per recipient)
        """
        from depotbutler.db.mongodb import (
            get_onedrive_folder_for_recipient,
            get_organize_by_year_for_recipient,
            get_recipients_for_publication,
        )

        try:
            # Get recipients with upload enabled for this publication
            recipients = await get_recipients_for_publication(
                publication["publication_id"], "upload"
            )

            if not recipients:
                logger.info(
                    "No recipients with upload enabled for publication: %s",
                    publication["publication_id"],
                )
                return []

            logger.info(
                "📤 Starting OneDrive uploads for %s recipient(s) [publication=%s]",
                len(recipients),
                publication["name"],
            )

            results = []
            for idx, recipient in enumerate(recipients, 1):
                try:
                    # Resolve folder and organize_by_year for this recipient
                    folder = get_onedrive_folder_for_recipient(recipient, publication)
                    organize_by_year = get_organize_by_year_for_recipient(
                        recipient, publication
                    )

                    logger.info(
                        "Uploading for recipient %s/%s [email=%s, folder=%s, organize_by_year=%s]",
                        idx,
                        len(recipients),
                        recipient["email"],
                        folder,
                        organize_by_year,
                    )

                    # Upload file for this recipient
                    result = await self.upload_file(
                        local_file_path=local_path,
                        edition=edition,
                        folder_name=folder,
                        organize_by_year=organize_by_year,
                    )

                    # Add recipient context to result
                    result.recipient_email = recipient["email"]
                    results.append(result)

                    if result.success:
                        logger.info(
                            "✅ Upload successful for %s [%s/%s]",
                            recipient["email"],
                            idx,
                            len(recipients),
                        )
                    else:
                        logger.error(
                            "❌ Upload failed for %s [%s/%s]: %s",
                            recipient["email"],
                            idx,
                            len(recipients),
                            result.error,
                        )

                except Exception as e:
                    logger.error(
                        "Failed to upload for recipient %s: %s", recipient["email"], e
                    )
                    results.append(
                        UploadResult(
                            success=False,
                            error=str(e),
                            recipient_email=recipient["email"],
                        )
                    )

            success_count = sum(1 for r in results if r.success)
            logger.info(
                "📤 OneDrive upload batch complete: %s/%s successful",
                success_count,
                len(results),
            )

            return results

        except Exception as e:
            logger.error(
                "Failed to upload for recipients (publication=%s): %s",
                publication["publication_id"],
                e,
            )
            return []

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
