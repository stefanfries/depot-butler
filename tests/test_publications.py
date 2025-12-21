"""Tests for publications configuration module."""

from depotbutler.publications import PublicationConfig


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


def test_publication_config_is_dataclass():
    """Test that PublicationConfig is a dataclass."""
    pub = PublicationConfig(
        id="test-pub",
        name="Test Publication",
        onedrive_folder="test/folder",
    )

    # Verify dataclass behavior
    assert hasattr(pub, "__dataclass_fields__")
    assert "id" in pub.__dataclass_fields__
    assert "name" in pub.__dataclass_fields__
    assert "onedrive_folder" in pub.__dataclass_fields__
