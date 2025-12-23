"""Tests for publications configuration module."""

from depotbutler.models import PublicationConfig


def test_publication_config_creation():
    """Test creating a PublicationConfig instance."""
    pub = PublicationConfig(
        id="test-pub",
        name="Test Publication",
        onedrive_folder="test/folder",
    )

    assert pub.id == "test-pub"
    assert pub.name == "Test Publication"
    assert pub.onedrive_folder == "test/folder"
    assert pub.recipients is None
    assert pub.subscription_number is None
    assert pub.subscription_id is None


def test_publication_config_with_optional_fields():
    """Test creating PublicationConfig with optional fields."""
    pub = PublicationConfig(
        id="test-pub",
        name="Test Publication",
        onedrive_folder="test/folder",
        recipients=["test@example.com"],
        subscription_number="AM-12345",
        subscription_id="67890",
    )

    assert pub.recipients == ["test@example.com"]
    assert pub.subscription_number == "AM-12345"
    assert pub.subscription_id == "67890"


def test_publication_config_is_pydantic_model():
    """Test that PublicationConfig is a Pydantic model."""
    pub = PublicationConfig(
        id="test-pub",
        name="Test Publication",
        onedrive_folder="test/folder",
    )

    # Verify Pydantic model behavior
    assert hasattr(pub, "model_dump")  # Pydantic V2 method
    assert pub.model_dump() == {
        "id": "test-pub",
        "name": "Test Publication",
        "onedrive_folder": "test/folder",
        "recipients": None,
        "subscription_number": None,
        "subscription_id": None,
    }
