from typing import Optional

from pydantic import BaseModel


class Subscription(BaseModel):
    """
    Represents a discovered subscription from boersenmedien.com account.
    """

    name: str
    subscription_number: str
    subscription_id: str
    content_url: str


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
    file_id: Optional[str] = None
    file_url: Optional[str] = None
    filename: Optional[str] = None
    size: Optional[int] = None
    error: Optional[str] = None
