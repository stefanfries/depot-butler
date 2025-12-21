# Testing Guide

## Test Types

This project has two types of tests:

### 1. Unit Tests (Default)

Fast, isolated tests that mock external dependencies. Run by default with `pytest`.

### 2. Integration Tests

Tests that require external services (MongoDB, etc.). Marked with `@pytest.mark.integration` and **skipped by default**.

## Running Tests

### Run All Unit Tests (Default)

```bash
# Run all tests (skips integration tests)
uv run pytest

# With coverage
uv run pytest --cov=src/depotbutler --cov-report=term

# Verbose output
uv run pytest -v
```

### Run Integration Tests

Integration tests require external services to be running:

**Prerequisites:**

- MongoDB running on `localhost:27017`
- Test database configured

```bash
# Run ONLY integration tests
uv run pytest -m integration -v

# Run ALL tests including integration
uv run pytest -m "" -v

# Run specific integration test
uv run pytest tests/test_recipient_filtering_integration.py -v
```

### Run Integration Tests as Standalone Script

```bash
# Requires MongoDB to be running
python tests/test_recipient_filtering_integration.py
```

## Test Markers

Tests can be marked with:

- `@pytest.mark.integration` - Requires external services
- `@pytest.mark.slow` - Long-running tests

## Coverage Reports

```bash
# Terminal report
uv run pytest --cov=src/depotbutler --cov-report=term

# HTML report (opens in browser)
uv run pytest --cov=src/depotbutler --cov-report=html
# Then open: htmlcov/index.html

# XML report (for CI/CD)
uv run pytest --cov=src/depotbutler --cov-report=xml
```

## Test Structure

```text
tests/
├── conftest.py                              # Shared fixtures and config
├── test_*.py                               # Unit tests (run by default)
└── test_*_integration.py                   # Integration tests (skipped by default)

scripts/
└── test_*.py                               # Legacy scripts (excluded from collection)
```

## Writing Tests

### Unit Test Example

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_something():
    with patch("module.dependency", new_callable=AsyncMock) as mock:
        mock.return_value = "mocked"
        result = await function_under_test()
        assert result == "expected"
```

### Integration Test Example

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_integration(check_mongodb):
    """Test with real MongoDB."""
    async with MongoDBService() as db:
        result = await db.some_operation()
        assert result is not None
```

## CI/CD

GitHub Actions runs **unit tests only** by default (integration tests skipped).

See `.github/workflows/quality.yml` for CI configuration.
