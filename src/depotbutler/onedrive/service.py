"""
OneDrive service for file upload/download operations.
Orchestrates authentication, folder management, and Graph API file operations.
"""

from pathlib import Path
from typing import Any

import httpx

from depotbutler.exceptions import ConfigurationError
from depotbutler.models import Edition, UploadResult
from depotbutler.onedrive.auth import OneDriveAuth, OneDriveAuthenticator
from depotbutler.onedrive.folder_manager import FolderManager
from depotbutler.settings import Settings
from depotbutler.utils.helpers import create_filename
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class OneDriveService:
    """
    OneDrive service for uploading files using Microsoft Graph API.
    Supports both local development and Azure Container deployment.
    """

    def __init__(self) -> None:
        self.settings = Settings()

        # Microsoft Graph API endpoint
        self.graph_url = "https://graph.microsoft.com/v1.0"

        # Initialize HTTP client
        self.http_client = httpx.AsyncClient()

        # Initialize auth manager
        self.auth = OneDriveAuth(self.settings)

        # Initialize folder manager (with callback to get auth headers)
        self.folder_manager = FolderManager(
            http_client=self.http_client,
            graph_url=self.graph_url,
            get_auth_header_func=self._get_auth_headers,
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authorization headers for Graph API requests."""
        access_token = self.auth.get_access_token()
        return {"Authorization": f"Bearer {access_token}"}

    async def authenticate(self) -> bool:
        """
        Authenticate using refresh token and get access token.
        Returns True if successful, raises exception on failure.
        """
        return await self.auth.authenticate()

    async def _make_graph_request(
        self,
        method: str,
        endpoint: str,
        data: bytes | None = None,
        json: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make authenticated request to Microsoft Graph API."""
        if not self.auth.access_token:
            raise ConfigurationError("Not authenticated. Call authenticate() first.")

        # Fix URL construction - ensure endpoint starts without leading slash
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]

        url = f"{self.graph_url}/{endpoint}"
        auth_headers = self._get_auth_headers()

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

    async def create_folder_path(self, folder_path: str) -> str | None:
        """
        Create a hierarchical folder path in OneDrive.
        Returns the final folder ID if successful, None otherwise.

        Args:
            folder_path: Path like "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent/2025"
        """
        return await self.folder_manager.create_folder_path(folder_path)

    async def create_folder_if_not_exists(self, folder_name: str) -> str | None:
        """
        Legacy method for backward compatibility.
        Creates a single folder in root. Use create_folder_path for hierarchical paths.
        """
        return await self.folder_manager.create_folder_if_not_exists(folder_name)

    async def upload_file(
        self,
        local_file_path: str,
        edition: Edition,
        folder_name: str | None = None,
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

        For files larger than 4MB, OneDrive recommends using upload sessions.
        Chunks can be 320 KiB to 60 MB. We use 10 MB for optimal speed/reliability balance.

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

            # Upload in chunks (10 MB per chunk - balances speed and reliability)
            # Microsoft supports chunks up to 60 MB, minimum 320 KiB
            chunk_size = 10 * 1024 * 1024  # 10,485,760 bytes (10 MB)
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
                        "Content-Range": f"bytes {start}-{end - 1}/{file_size}",
                    }

                    logger.info(
                        f"Uploading chunk {chunk_num + 1}/{total_chunks} ({start}-{end - 1}/{file_size})"
                    )

                    # Upload chunk directly to upload URL (no authorization needed)
                    chunk_response = await self.http_client.request(
                        method="PUT",
                        url=upload_url,
                        content=chunk_data,
                        headers=headers,
                        timeout=120.0,  # 2 minutes per chunk for 10MB chunks
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

    async def list_files(self, folder_name: str | None = None) -> list[dict[str, Any]]:
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
                return list(data.get("value", []))
            else:
                logger.error("Failed to list files: %s", response.text)
                return []

        except Exception as e:
            logger.error("Error listing files: %s", e)
            return []

    async def close(self) -> None:
        """Clean up HTTP client."""
        await self.http_client.aclose()


# Re-export OneDriveAuthenticator for backward compatibility
__all__ = ["OneDriveService", "OneDriveAuthenticator"]
