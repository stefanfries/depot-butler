"""Tests for publications configuration module."""

from depotbutler.publications import (
    PUBLICATIONS,
    PublicationConfig,
    get_all_publications,
    get_publication,
)


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


def test_publications_registry_not_empty():
    """Test that PUBLICATIONS registry contains at least one publication."""
    assert len(PUBLICATIONS) > 0


def test_publications_registry_structure():
    """Test that all publications in registry have required fields."""
    for pub in PUBLICATIONS:
        assert isinstance(pub, PublicationConfig)
        assert pub.id is not None
        assert pub.name is not None
        assert pub.onedrive_folder is not None
        assert isinstance(pub.id, str)
        assert isinstance(pub.name, str)
        assert isinstance(pub.onedrive_folder, str)


def test_get_publication_existing():
    """Test retrieving an existing publication by ID."""
    # Use the actual publication from the registry
    expected_pub = PUBLICATIONS[0]
    result = get_publication(expected_pub.id)

    assert result is not None
    assert result.id == expected_pub.id
    assert result.name == expected_pub.name
    assert result.onedrive_folder == expected_pub.onedrive_folder


def test_get_publication_nonexistent():
    """Test retrieving a non-existent publication returns None."""
    result = get_publication("nonexistent-publication-id")
    assert result is None


def test_get_all_publications():
    """Test getting all publications."""
    result = get_all_publications()

    assert isinstance(result, list)
    assert len(result) == len(PUBLICATIONS)
    assert result == PUBLICATIONS


def test_get_all_publications_returns_same_list():
    """Test that get_all_publications returns the same list instance."""
    result1 = get_all_publications()
    result2 = get_all_publications()

    assert result1 is result2
    assert result1 is PUBLICATIONS


def test_publication_ids_are_unique():
    """Test that all publication IDs are unique."""
    ids = [pub.id for pub in PUBLICATIONS]
    assert len(ids) == len(set(ids)), "Publication IDs must be unique"


def test_publication_names_are_not_empty():
    """Test that all publication names are non-empty strings."""
    for pub in PUBLICATIONS:
        assert len(pub.name.strip()) > 0, f"Publication {pub.id} has empty name"


def test_onedrive_folders_are_valid_paths():
    """Test that all OneDrive folder paths are valid."""
    for pub in PUBLICATIONS:
        assert len(pub.onedrive_folder.strip()) > 0
        # Should not start with / or \
        assert not pub.onedrive_folder.startswith("/")
        assert not pub.onedrive_folder.startswith("\\")


def test_megatrend_folger_publication_exists():
    """Test that the Megatrend Folger publication is configured."""
    result = get_publication("megatrend-folger")

    assert result is not None
    assert result.name == "Megatrend Folger"
    assert result.subscription_number is None  # Auto-discovery enabled
    assert result.subscription_id is None  # Auto-discovery enabled
