"""
Publication configuration and management.
Supports multiple publications from boersenmedien.com.
"""

from dataclasses import dataclass
from typing import Optional

from pydantic import EmailStr


@dataclass
class PublicationConfig:
    """Configuration for a single publication."""

    # Publication identifier (used internally)
    id: str

    # Display name
    name: str

    # OneDrive folder path (relative to base)
    onedrive_folder: str

    # Optional: specific recipients for this publication
    # If None, uses default SMTP_RECIPIENTS from settings
    recipients: Optional[list[EmailStr]] = None

    # Optional: subscription number and ID (if known)
    # If None, will be auto-discovered from account
    subscription_number: Optional[str] = None
    subscription_id: Optional[str] = None


# Publication Registry
# Add your subscribed publications here


PUBLICATIONS = [
    PublicationConfig(
        id="megatrend-folger",
        name="Megatrend Folger",
        onedrive_folder="Dokumente/Banken/DerAktionaer/Strategie_800-Prozent",
        # subscription_number and subscription_id will be auto-discovered
    ),
    PublicationConfig(
        id="der-aktionaer-epaper",
        name="DER AKTIONÄR E-Paper",
        onedrive_folder="Dokumente/Banken/DerAktionaer/Magazin",
        # subscription_number and subscription_id will be auto-discovered
    ),
]


def get_publication(publication_id: str) -> Optional[PublicationConfig]:
    """Get publication config by ID."""
    for pub in PUBLICATIONS:
        if pub.id == publication_id:
            return pub
    return None


def get_all_publications() -> list[PublicationConfig]:
    """Get all configured publications."""
    return PUBLICATIONS
