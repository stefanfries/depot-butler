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

    # OneDrive folder settings
    base_folder_path: str = "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent"
    organize_by_year: bool = True
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
