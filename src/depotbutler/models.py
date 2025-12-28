from datetime import date, datetime

from pydantic import BaseModel, EmailStr


class PublicationConfig(BaseModel):
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


class ProcessedEdition(BaseModel):
    """Represents a processed edition entry with granular pipeline tracking."""

    title: str
    publication_date: str
    download_url: str
    processed_at: datetime
    file_path: str = ""

    # Blob storage metadata (Phase 0)
    blob_url: str | None = None
    blob_path: str | None = None
    blob_container: str | None = None
    file_size_bytes: int | None = None
    archived_at: datetime | None = None

    # Granular pipeline timestamps for performance tracking
    downloaded_at: datetime | None = None
    email_sent_at: datetime | None = None
    onedrive_uploaded_at: datetime | None = None


class PublicationResult(BaseModel):
    """Result of processing a single publication."""

    publication_id: str
    publication_name: str
    success: bool
    edition: "Edition | None" = None
    already_processed: bool = False
    error: str | None = None
    download_path: str | None = None
    email_result: bool | None = None
    upload_result: "UploadResult | None" = None
    recipients_emailed: int = 0
    recipients_uploaded: int = 0
    # Blob archival tracking
    archived: bool | None = None
    blob_url: str | None = None
    archived_at: datetime | None = None


class Subscription(BaseModel):
    """
    Represents a discovered subscription from boersenmedien.com account.
    """

    name: str
    subscription_number: str
    subscription_id: str
    content_url: str
    subscription_type: str | None = None  # e.g., "Jahresabo"
    duration: str | None = None  # e.g., "02.07.2025 - 01.07.2026"
    duration_start: date | None = None  # Parsed start date
    duration_end: date | None = None  # Parsed end date


class Edition(BaseModel):
    """
    Represents a financial issue with relevant metadata.
    Attributes:
        title (str): The title of the issue.
        details_url (HttpUrl): URL linking to detailed information about the issue.
        download_link (HttpUrl): URL to download the issue document.
        published_date (str): The publication date of the issue.
    """

    title: str
    details_url: str
    download_url: str
    publication_date: str


class UploadResult(BaseModel):
    """
    Result of OneDrive file upload operation.
    """

    success: bool
    file_id: str | None = None
    file_url: str | None = None
    filename: str | None = None
    size: int | None = None
    error: str | None = None
    recipient_email: str | None = None  # For multi-recipient uploads
