from pydantic import EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MegatrendSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_prefix="MEGATREND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str
    login_url: str
    abo_nummer: str
    abo_id: str
    # content_url: str
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

    server: str
    port: int
    username: str
    password: SecretStr
    recipients: list[EmailStr] = Field(default_factory=list)
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

    # Path to the tracking file (use Azure File Share path in production)
    file_path: str = "/mnt/data/processed_editions.json"

    # How long to keep tracking records (days)
    retention_days: int = 90

    # Enable/disable duplicate checking
    enabled: bool = True


class Settings:
    """Top-level app configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    megatrend = MegatrendSettings()  # type: ignore
    onedrive = OneDriveSettings()  # type: ignore
    mail = MailSettings()  # type: ignore
    tracking = TrackingSettings()  # type: ignore
