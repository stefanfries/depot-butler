# Contributing to DepotButler

Thank you for your interest in contributing to DepotButler! This document provides guidelines and standards for contributing to this project.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Architecture Guidelines](#architecture-guidelines)
- [Testing Requirements](#testing-requirements)
- [Quality Checks](#quality-checks)
- [Git Workflow](#git-workflow)
- [Pull Request Process](#pull-request-process)

---

## Development Setup

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- Git
- MongoDB (for integration tests)

### Initial Setup

```powershell
# Clone the repository
git clone https://github.com/stefanfries/depot-butler.git
cd depot-butler

# Install dependencies (includes dev dependencies)
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install

# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

### Running the Application

```powershell
# Activate virtual environment (if needed)
.venv\Scripts\activate

# Run in dry-run mode (no emails/uploads)
python -m depotbutler --dry-run

# Run in production mode
python -m depotbutler
```

---

## Code Standards

### Code Style

We use **Ruff** as our sole linter and formatter. Configuration is in `pyproject.toml`.

**Key principles:**
- Line length: 88 characters (Black-compatible)
- Target: Python 3.13
- Type hints required for all functions
- Async/await for I/O operations

### Linting Rules

```toml
# Enabled rules (see pyproject.toml)
E    # pycodestyle errors
F    # pyflakes
I    # isort (import sorting)
N    # pep8-naming
UP   # pyupgrade (modern Python syntax)
B    # flake8-bugbear (common bugs)
C4   # flake8-comprehensions
SIM  # flake8-simplify
TCH  # flake8-type-checking
```

### Running Code Quality Checks

```powershell
# Lint code
uv run ruff check src/

# Auto-fix issues
uv run ruff check --fix src/

# Format code
uv run ruff format src/

# Type checking (excludes tests/)
uv run mypy src/

# Check complexity (find functions > complexity 10)
uv run radon cc src/ -n C

# Run all checks (what CI runs)
uv run pre-commit run --all-files
```

### Complexity Limits

- **Cyclomatic Complexity**: < 10 per function (target: A-B grade)
- **Function Length**: < 50 lines preferred
- **Module Size**: < 500 lines preferred

**Check before committing:**
```powershell
# Functions with complexity >= 10
uv run radon cc src/depotbutler -n C
```

### Naming Conventions

- **Classes**: PascalCase (`MongoDBService`, `HttpxBoersenmedienClient`)
- **Functions/Methods**: snake_case (`get_latest_edition`, `send_email`)
- **Constants**: UPPER_SNAKE_CASE (`BASE_URL`, `COOKIE_MAX_AGE`)
- **Private methods**: Leading underscore (`_send_smtp_email`, `_cleanup_files`)
- **Async functions**: No special prefix, just `async def`

### Import Organization

```python
# Standard library
import asyncio
from datetime import datetime
from pathlib import Path

# Third-party
import httpx
from pydantic import BaseModel

# Local application
from depotbutler.db.mongodb import MongoDBService
from depotbutler.models import Edition
from depotbutler.utils.logger import get_logger
```

Ruff automatically organizes imports with `ruff check --fix`.

---

## Architecture Guidelines

### Clean Architecture Layers

```
depotbutler/
├── models.py              # Domain models (Pydantic)
├── exceptions.py          # Domain exceptions
├── settings.py            # Configuration (Pydantic Settings)
├── db/                    # Infrastructure - Database
│   ├── mongodb.py         #   Facade pattern
│   └── repositories/      #   Repository pattern
├── httpx_client.py        # Infrastructure - HTTP client
├── onedrive/              # Infrastructure - File storage
│   ├── service.py
│   ├── auth.py
│   └── folder_manager.py
├── mailer/                # Infrastructure - Email
│   ├── service.py
│   ├── templates.py
│   └── composers.py
├── services/              # Application services
│   ├── cookie_checker.py
│   ├── notification_service.py
│   └── publication_processor.py
├── workflow.py            # Orchestration layer
└── utils/                 # Utilities
    ├── helpers.py
    └── logger.py
```

### Key Patterns

#### 1. Repository Pattern (Database Layer)

**Purpose**: Isolate database operations from business logic.

```python
# repositories/base.py
class BaseRepository:
    def __init__(self, db: Database):
        self._db = db

# repositories/publication.py
class PublicationRepository(BaseRepository):
    async def get_publications(self, active_only: bool = True) -> list[dict]:
        """Get publications with domain-specific logic."""
        # ...
```

**When to use:**
- All MongoDB operations
- Each collection gets its own repository
- Repositories expose domain-level methods, not raw queries

#### 2. Service Layer Pattern

**Purpose**: Encapsulate business logic and coordinate multiple repositories.

```python
# services/publication_processor.py
class PublicationProcessor:
    def __init__(self, client: HttpxClient, db: MongoDBService, ...):
        self.client = client
        self.db = db
        # ...

    async def process_publication(self, publication_data: dict) -> PublicationResult:
        """Process a single publication end-to-end."""
        # Orchestrates: download, email, upload, tracking
```

**When to use:**
- Complex business logic spanning multiple repositories
- Workflow coordination
- Transaction-like operations

#### 3. Dependency Injection

**Prefer constructor injection:**

```python
class EmailService:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Initialize SMTP connection

# Usage in workflow
self.email_service = EmailService(settings=self.settings)
```

**Don't:**
- Use global state
- Create dependencies inside methods
- Use singletons unnecessarily

### Error Handling

Use domain-specific exceptions from `exceptions.py`:

```python
from depotbutler.exceptions import (
    AuthenticationError,      # Cookie expired, login failed
    TransientError,           # Network timeout, 5xx errors (retry safe)
    ConfigurationError,       # Missing env vars, invalid config
    EditionNotFoundError,     # No edition available
    DownloadError,            # PDF download failed
    UploadError,              # OneDrive upload failed
    EmailDeliveryError,       # Email send failed
)
```

**Pattern:**
```python
try:
    # Operation
    pass
except httpx.TimeoutException as e:
    raise TransientError("Operation timed out") from e
except httpx.HTTPStatusError as e:
    if e.response.status_code >= 500:
        raise TransientError(f"Server error: {e}") from e
    else:
        raise DownloadError(f"Download failed: {e}") from e
```

### Async Context Managers

For resources that need cleanup:

```python
class HttpxBoersenmedienClient:
    async def __aenter__(self):
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# Usage
async with HttpxBoersenmedienClient() as client:
    edition = await client.get_latest_edition(publication)
```

---

## Testing Requirements

### Coverage Targets

- **Overall**: 80%+ (currently 72%)
- **New code**: 90%+ required
- **Critical paths**: 100% (auth, payment, data loss scenarios)

### Test Structure

```
tests/
├── conftest.py                        # Shared fixtures
├── test_<module>.py                   # Unit tests
├── test_<module>_integration.py      # Integration tests
└── fixtures/                          # Test data and builders
```

### Running Tests

```powershell
# All unit tests (default)
uv run pytest

# With coverage report
uv run pytest --cov=src/depotbutler --cov-report=term

# Integration tests only (requires MongoDB)
uv run pytest -m integration -v

# Specific test file
uv run pytest tests/test_workflow.py

# Specific test function
uv run pytest tests/test_workflow.py::test_full_workflow_success -v
```

### Writing Tests

**Unit test example:**

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_send_email_success():
    """Test successful email sending."""
    # Arrange
    mock_smtp = AsyncMock()
    email_service = EmailService(settings=test_settings)

    # Act
    with patch('smtplib.SMTP', return_value=mock_smtp):
        result = await email_service.send_email(...)

    # Assert
    assert result.success is True
    mock_smtp.send_message.assert_called_once()
```

**Integration test example:**

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_workflow_with_real_db():
    """Test complete workflow with real MongoDB."""
    async with MongoDBService() as db:
        # Setup test data
        await db.create_publication({...})

        # Run workflow
        result = await workflow.run_full_workflow()

        # Verify
        assert result["publications_succeeded"] == 1
```

### Test Fixtures

Use pytest fixtures for common setup:

```python
@pytest.fixture
async def mock_mongodb():
    """Mock MongoDB service."""
    db = AsyncMock(spec=MongoDBService)
    db.get_publications.return_value = [test_publication]
    return db

@pytest.fixture
def test_settings():
    """Test configuration."""
    return Settings(
        BOERSENMEDIEN_BASE_URL="https://test.example.com",
        # ... other settings
    )
```

### Mocking Guidelines

- **Mock external services**: HTTP, SMTP, OneDrive API
- **Don't mock**: Domain models, pure functions, database in integration tests
- **Use `AsyncMock`** for async functions
- **Verify calls**: Use `assert_called_once()`, `assert_called_with()`

---

## Quality Checks

### Pre-commit Hooks

Automatically run on `git commit`:

```yaml
# .pre-commit-config.yaml
- ruff (linting)
- ruff-format (formatting)
- trailing whitespace
- end of files
- YAML/TOML validation
- large files check
- merge conflicts check
- mypy (type checking)
```

**Skip hooks (emergency only):**
```powershell
git commit --no-verify -m "message"
```

### CI/CD Pipeline

GitHub Actions runs on every push/PR:

1. ✅ Lint with ruff
2. ✅ Format check (ruff format --check)
3. ✅ Run tests with coverage
4. ✅ Check complexity (radon)
5. ✅ Type checking (mypy)

**View CI results:**
- GitHub Actions tab in repository
- Pull request checks

### Manual Quality Audit

Before major releases:

```powershell
# 1. Run all tests
uv run pytest --cov=src/depotbutler --cov-report=html

# 2. Check coverage report
# Open htmlcov/index.html in browser

# 3. Find complex functions
uv run radon cc src/depotbutler -n C

# 4. Check maintainability index
uv run radon mi src/depotbutler -n B

# 5. Run type checking
uv run mypy src/
```

---

## Git Workflow

### Branching Strategy

**Simple Feature Branch Workflow** (single developer):

```powershell
# For major work (refactoring, new features)
git checkout -b feature-name
# ... work and commit frequently
git push origin feature-name
# Open PR on GitHub for review
# Merge after tests pass, then cleanup
git checkout main
git pull
git branch -d feature-name

# For small fixes/updates
# Work directly on main branch
git commit -m "fix: ..."
git push
```

**Branch naming:**
- `sprint2-refactoring` - Sprint work
- `fix-bug-description` - Bug fixes
- `feature-description` - New features

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring (no behavior change)
- `docs`: Documentation changes
- `test`: Adding/updating tests
- `chore`: Tooling, dependencies, config
- `perf`: Performance improvements

**Examples:**
```
feat(mailer): add consolidated admin notifications

- Build HTML report with all publication results
- Send single email instead of multiple
- Include success, error, and skip counts

Closes #42
```

```
refactor(mongodb): split into repository pattern

- Create RecipientRepository, PublicationRepository, etc.
- Reduce mongodb.py from 1023 to 333 lines (67% reduction)
- All 241 tests still passing

Part of Sprint 2, Task 1
```

### Before Committing

```powershell
# 1. Run tests
uv run pytest

# 2. Check linting/formatting (pre-commit does this)
uv run ruff check src/
uv run ruff format src/

# 3. Verify changes
git status
git diff

# 4. Commit (pre-commit hooks run automatically)
git commit -m "type: message"
```

---

## Pull Request Process

### Creating a PR

1. **Push your branch:**
   ```powershell
   git push origin feature-name
   ```

2. **Open PR on GitHub:**
   - Descriptive title following commit message format
   - Reference related issues
   - Describe what changed and why

3. **PR Description Template:**
   ```markdown
   ## What
   Brief description of changes

   ## Why
   Problem being solved or feature being added

   ## Changes
   - Bullet list of key changes
   - File/module modifications
   - New dependencies (if any)

   ## Testing
   - What tests were added/updated
   - How to test manually (if applicable)

   ## Checklist
   - [ ] Tests passing locally
   - [ ] Coverage maintained/improved
   - [ ] Documentation updated
   - [ ] No new complexity warnings
   ```

### Review Criteria

PRs should:
- ✅ Pass all CI checks
- ✅ Maintain or improve test coverage
- ✅ Follow code standards
- ✅ Include tests for new functionality
- ✅ Update documentation if needed
- ✅ Not introduce high-complexity functions (> 10)

### Merging

- **Main branch** should always be stable and deployable
- **Squash commits** for feature branches (optional)
- **Delete branch** after merging

---

## Additional Resources

### Project Documentation

- **[CODE_QUALITY.md](docs/CODE_QUALITY.md)** - Quality metrics and improvement plan
- **[ARCHITECTURE.md](docs/architecture.md)** - System architecture overview
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Azure deployment guide
- **[TESTING.md](docs/TESTING.md)** - Testing strategy and guidelines

### External Resources

- **[Ruff Documentation](https://docs.astral.sh/ruff/)** - Linter/formatter
- **[Pytest Documentation](https://docs.pytest.org/)** - Testing framework
- **[Pydantic V2](https://docs.pydantic.dev/)** - Data validation
- **[httpx](https://www.python-httpx.org/)** - Async HTTP client
- **[Motor](https://motor.readthedocs.io/)** - Async MongoDB driver

---

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/stefanfries/depot-butler/issues)
- **Discussions**: [GitHub Discussions](https://github.com/stefanfries/depot-butler/discussions)
- **Email**: stefan.fries.burgdorf@gmx.de

---

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.
