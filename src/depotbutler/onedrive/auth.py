"""
MSAL authentication for Microsoft Graph API / OneDrive.
Handles refresh token retrieval, authentication, and initial setup.
"""

import os
from typing import Any

import msal
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from depotbutler.exceptions import AuthenticationError, ConfigurationError
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class OneDriveAuth:
    """
    Handles MSAL authentication for OneDrive/Graph API.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client_id = settings.onedrive.client_id
        self.client_secret = settings.onedrive.client_secret.get_secret_value()
        self.refresh_token = self._get_refresh_token()

        # Microsoft Graph API configuration
        # Use consumers endpoint for personal Microsoft accounts
        self.authority = "https://login.microsoftonline.com/consumers"
        self.scopes = ["https://graph.microsoft.com/Files.ReadWrite.All"]

        # Initialize MSAL app
        self.msal_app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority,
        )

        self.access_token: str | None = None

    def _get_refresh_token(self) -> str | None:
        """
        Get refresh token from environment variable or Azure Key Vault.
        Priority: Environment Variable > Azure Key Vault > None
        """
        # Try environment variable first (for container deployment)
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
                return str(secret.value)
        except Exception as e:
            logger.warning("Could not retrieve refresh token from Key Vault: %s", e)

        logger.error("No refresh token found. Please run initial authentication.")
        return None

    async def authenticate(self) -> bool:
        """
        Authenticate using refresh token and get access token.
        Returns True if successful, raises exception on failure.
        """
        if not self.refresh_token:
            logger.error("No refresh token available. Cannot authenticate.")
            raise ConfigurationError(
                "OneDrive refresh token not configured. "
                "Please set up OneDrive authentication."
            )

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
                error_desc = result.get("error_description", "Unknown error")
                logger.error("Authentication failed: %s", error_desc)
                raise AuthenticationError(
                    f"OneDrive authentication failed: {error_desc}"
                )

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error("Authentication error: %s", e)
            raise AuthenticationError(f"OneDrive authentication error: {e}") from e

    def get_access_token(self) -> str:
        """Get current access token. Raises if not authenticated."""
        if not self.access_token:
            raise ConfigurationError("Not authenticated. Call authenticate() first.")
        return self.access_token


class OneDriveAuthenticator:
    """
    Helper class for initial authentication setup.
    Use this locally to generate refresh token, then store in Azure Container.
    """

    def __init__(self) -> None:
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
        return str(auth_url)

    def exchange_code_for_tokens(self, authorization_code: str) -> dict[str, Any]:
        """
        Exchange authorization code for tokens.
        Save the refresh_token to Azure Container environment variables.
        """
        result = self.msal_app.acquire_token_by_authorization_code(
            code=authorization_code, scopes=self.scopes, redirect_uri=self.redirect_uri
        )

        if "refresh_token" in result:
            print("SUCCESS! Save this refresh token to Azure Container:")
            print(f"ONEDRIVE_REFRESH_TOKEN={result['refresh_token']}")
            return dict(result)
        else:
            print(f"ERROR: {result.get('error_description', 'Unknown error')}")
            return dict(result)
