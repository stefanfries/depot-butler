from pydantic import EmailStr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BoersenmedienSettings(BaseSettings):
    """Settings for Börsenmedien account access."""

    model_config = SettingsConfigDict(
        env_prefix="BOERSENMEDIEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str
    login_url: str
    username: SecretStr
    password: SecretStr


class OneDriveSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ONEDRIVE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OAuth2 Configuration for Azure App
    client_id: str
    client_secret: SecretStr
    refresh_token: SecretStr

    # OneDrive upload settings (global defaults)
    # Note: Folder paths are configured per publication in MongoDB (publications.default_onedrive_folder)
    # and can be overridden per recipient (publication_preferences.custom_onedrive_folder)
    organize_by_year: bool = (
        True  # Default, can be overridden per publication/recipient
    )
    overwrite_files: bool = True


class MailSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SMTP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    server: str = "smtp.gmx.net"  # Default, can be overridden by MongoDB
    port: int = 587  # Default, can be overridden by MongoDB
    username: str
    password: SecretStr
    admin_address: EmailStr

    # Email template settings
    sender_name: str = "Depot Butler"
    enable_html: bool = True


class TrackingSettings(BaseSettings):
    """Settings for edition tracking to prevent duplicates."""

    model_config = SettingsConfigDict(
        env_prefix="TRACKING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # How long to keep tracking records (days)
    retention_days: int = 90

    # Enable/disable duplicate checking
    enabled: bool = True

    # Temporary directory for PDF downloads
    temp_dir: str = "/mnt/data/tmp"


class MongoDBSettings(BaseSettings):
    """Settings for MongoDB connection."""

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str
    root_username: str
    root_password: SecretStr
    connection_string: str


class DiscoverySettings(BaseSettings):
    """Settings for publication discovery and synchronization."""

    model_config = SettingsConfigDict(
        env_prefix="DISCOVERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Enable/disable automatic publication discovery
    enabled: bool = True


class DatabaseSettings(BaseSettings):
    """MongoDB database configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="MONGODB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Connection timeouts (milliseconds)
    server_selection_timeout_ms: int = 5000
    connect_timeout_ms: int = 10000
    socket_timeout_ms: int = 30000

    # Query settings
    cursor_batch_size: int = 1000


class HttpSettings(BaseSettings):
    """HTTP client configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="HTTP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Request timeout (seconds)
    request_timeout: float = 30.0

    # Retry settings
    max_retries: int = 3
    retry_backoff: float = 2.0


class NotificationSettings(BaseSettings):
    """Notification and alerting settings."""

    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Cookie expiration warning threshold (days)
    cookie_warning_days: int = 3

    # Email notification toggles
    send_summary_emails: bool = True
    admin_notification_enabled: bool = True


class Settings:
    """Top-level app configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    boersenmedien = BoersenmedienSettings()  # type: ignore
    onedrive = OneDriveSettings()  # type: ignore
    mail = MailSettings()  # type: ignore
    tracking = TrackingSettings()  # type: ignore
    mongodb = MongoDBSettings()  # type: ignore
    discovery = DiscoverySettings()  # type: ignore
    database = DatabaseSettings()  # type: ignore
    http = HttpSettings()  # type: ignore
    notifications = NotificationSettings()  # type: ignore
