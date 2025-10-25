from pydantic import Field, SecretStr
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

    basefolder: str
    username: SecretStr
    password: SecretStr


class MailSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_prefix="SMTP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    server: SecretStr
    port: int
    username: SecretStr
    password: SecretStr
    recipients: list[str] = Field(default_factory=list)


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
