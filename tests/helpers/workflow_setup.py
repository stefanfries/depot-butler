"""Helper utilities for setting up workflow tests.

This module provides reusable helper functions that reduce boilerplate
in workflow tests. These functions handle common patterns like MongoDB
mocking and publication discovery patching.
"""

from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, patch


def patch_mongodb_operations(
    mock_publications: list[dict], mock_recipients: list[dict]
):
    """Create context manager for common MongoDB operation patches.

    Args:
        mock_publications: List of publication documents to return
        mock_recipients: List of recipient documents to return

    Returns:
        Context manager that patches MongoDB operations

    Usage:
        with patch_mongodb_operations(publications, recipients):
            # Test code here - MongoDB operations are mocked
            result = await workflow.run_full_workflow()
    """
    stack = ExitStack()

    # Patch get_publications in workflow module (where it's imported)
    stack.enter_context(
        patch(
            "depotbutler.workflow.get_publications",
            new_callable=AsyncMock,
            return_value=mock_publications,
        )
    )

    # Patch the recipient repository's get_recipients_for_publication method
    # This needs to filter recipients based on publication_id and delivery_method
    async def mock_get_recipients(publication_id: str, delivery_method: str):
        """Mock implementation that filters recipients by publication and method."""
        field_name = f"{delivery_method}_enabled"
        return [
            r
            for r in mock_recipients
            if any(
                pref.get("publication_id") == publication_id
                and pref.get("enabled", False)
                and pref.get(field_name, False)
                for pref in r.get("publication_preferences", [])
            )
        ]

    # Create a mock MongoDB service with the get_recipients_for_publication method
    mock_mongodb_service = AsyncMock()
    mock_mongodb_service.get_recipients_for_publication = AsyncMock(
        side_effect=mock_get_recipients
    )
    mock_mongodb_service.get_onedrive_folder_for_recipient = (
        lambda recipient, pub_data: (pub_data.get("default_onedrive_folder"))
    )
    mock_mongodb_service.get_organize_by_year_for_recipient = (
        lambda recipient, pub_data: (pub_data.get("organize_by_year", True))
    )

    # Patch get_mongodb_service to return our mock
    stack.enter_context(
        patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            new_callable=AsyncMock,
            return_value=mock_mongodb_service,
        )
    )

    return stack


def patch_discovery_service(
    new_count: int = 0,
    updated_count: int = 0,
    deactivated_count: int = 0,
    discovered_count: int = 0,
):
    """Create context manager for publication discovery service patching.

    Args:
        new_count: Number of new publications discovered
        updated_count: Number of updated publications
        deactivated_count: Number of deactivated publications
        discovered_count: Total number of publications discovered

    Returns:
        Context manager that patches PublicationDiscoveryService

    Usage:
        with patch_discovery_service():
            # Discovery service is mocked
            result = await workflow.run_full_workflow()
    """
    return patch(
        "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
        new_callable=AsyncMock,
        return_value={
            "new_count": new_count,
            "updated_count": updated_count,
            "deactivated_count": deactivated_count,
            "discovered_count": discovered_count,
            "errors": [],
        },
    )


def patch_file_operations():
    """Create context manager for file system operation patches.

    Returns:
        ExitStack context manager that patches file operations

    Usage:
        with patch_file_operations():
            # File operations are mocked (no actual file I/O)
            result = await workflow.run_full_workflow()
    """
    stack = ExitStack()
    stack.enter_context(
        patch.multiple(
            "pathlib.Path",
            exists=lambda self: True,
            mkdir=lambda self, **kwargs: None,
        )
    )
    stack.enter_context(patch.multiple("os.path", exists=lambda path: True))
    stack.enter_context(patch("os.remove", lambda path: None))
    return stack


def create_mock_publication(
    publication_id: str = "megatrend-folger",
    name: str = "Megatrend Folger",
    subscription_id: str = "2477462",
    email_enabled: bool = True,
    onedrive_enabled: bool = True,
    active: bool = True,
    **kwargs: Any,
) -> dict:
    """Create a mock publication document with sensible defaults.

    Args:
        publication_id: Unique publication identifier
        name: Display name
        subscription_id: Subscription ID from boersenmedien.com
        email_enabled: Whether email delivery is enabled
        onedrive_enabled: Whether OneDrive upload is enabled
        active: Whether publication is active
        **kwargs: Additional publication fields

    Returns:
        Publication document dictionary

    Usage:
        pub = create_mock_publication(
            publication_id="custom-pub",
            name="Custom Publication",
            organize_by_year=False
        )
    """
    publication = {
        "publication_id": publication_id,
        "name": name,
        "subscription_id": subscription_id,
        "subscription_number": "AM-01029205",
        "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent",
        "email_enabled": email_enabled,
        "onedrive_enabled": onedrive_enabled,
        "organize_by_year": True,
        "active": active,
    }
    publication.update(kwargs)
    return publication


def create_mock_recipient(
    name: str = "Test User",
    email: str = "test@example.com",
    publication_id: str = "megatrend-folger",
    email_enabled: bool = True,
    upload_enabled: bool = True,
    custom_onedrive_folder: str | None = None,
    publication_preferences: list[dict] | None = None,
    **kwargs: Any,
) -> dict:
    """Create a mock recipient document with sensible defaults.

    Args:
        name: Recipient name
        email: Recipient email address
        publication_id: Publication ID for default preference
        email_enabled: Whether email delivery is enabled
        upload_enabled: Whether OneDrive upload is enabled
        custom_onedrive_folder: Optional custom OneDrive folder
        publication_preferences: Per-publication preferences (overrides defaults)
        **kwargs: Additional recipient fields

    Returns:
        Recipient document dictionary

    Usage:
        # With default preferences:
        recipient = create_mock_recipient(
            name="John Doe",
            email="john@example.com",
            publication_id="megatrend-folger"
        )

        # With custom folder:
        recipient = create_mock_recipient(
            custom_onedrive_folder="shared:drive_id:item_id"
        )

        # With explicit preferences:
        recipient = create_mock_recipient(
            publication_preferences=[
                {
                    "publication_id": "custom-pub",
                    "enabled": True,
                    "email_enabled": False,
                    "upload_enabled": True
                }
            ]
        )
    """
    # If no explicit preferences provided, create default preference
    if publication_preferences is None:
        pref = {
            "publication_id": publication_id,
            "enabled": True,
            "email_enabled": email_enabled,
            "upload_enabled": upload_enabled,
        }
        if custom_onedrive_folder:
            pref["custom_onedrive_folder"] = custom_onedrive_folder
        publication_preferences = [pref]

    recipient = {
        "name": name,
        "email": email,
        "active": True,
        "publication_preferences": publication_preferences,
    }
    recipient.update(kwargs)
    return recipient
