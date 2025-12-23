"""Helper utilities for setting up workflow tests.

This module provides reusable helper functions that reduce boilerplate
in workflow tests. These functions handle common patterns like MongoDB
mocking and publication discovery patching.
"""

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
    return patch.multiple(
        "depotbutler.db.mongodb",
        get_active_publications=AsyncMock(return_value=mock_publications),
        get_recipients_for_publication=AsyncMock(return_value=mock_recipients),
    )


def patch_discovery_service(
    new_count: int = 0, updated_count: int = 0, deactivated_count: int = 0
):
    """Create context manager for publication discovery service patching.

    Args:
        new_count: Number of new publications discovered
        updated_count: Number of updated publications
        deactivated_count: Number of deactivated publications

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
        },
    )


def patch_file_operations():
    """Create context manager for file system operation patches.

    Returns:
        Context manager that patches file operations

    Usage:
        with patch_file_operations():
            # File operations are mocked (no actual file I/O)
            result = await workflow.run_full_workflow()
    """
    return (
        patch.multiple(
            "pathlib.Path",
            exists=lambda self: True,
            mkdir=lambda self, **kwargs: None,
        ),
        patch.multiple(
            "os.path",
            exists=lambda path: True,
        ),
        patch(
            "os.remove",
            lambda path: None,
        ),
    )


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
    publication_preferences: list[dict] | None = None,
    **kwargs: Any,
) -> dict:
    """Create a mock recipient document with sensible defaults.

    Args:
        name: Recipient name
        email: Recipient email address
        publication_preferences: Per-publication preferences
        **kwargs: Additional recipient fields

    Returns:
        Recipient document dictionary

    Usage:
        recipient = create_mock_recipient(
            name="John Doe",
            email="john@example.com",
            publication_preferences=[
                {
                    "publication_id": "megatrend-folger",
                    "custom_onedrive_folder": "Custom/Path"
                }
            ]
        )
    """
    recipient = {
        "name": name,
        "email": email,
        "publication_preferences": publication_preferences or [],
    }
    recipient.update(kwargs)
    return recipient
