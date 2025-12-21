from datetime import date

from pydantic import BaseModel


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
