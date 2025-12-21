"""
Publication configuration and management.
Supports multiple publications from boersenmedien.com.

Note: Publications are now auto-discovered from your account and stored in MongoDB.
This module provides the PublicationConfig dataclass for type definitions.
"""

from dataclasses import dataclass

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
    recipients: list[EmailStr] | None = None

    # Optional: subscription number and ID (if known)
    # If None, will be auto-discovered from account
    subscription_number: str | None = None
    subscription_id: str | None = None
