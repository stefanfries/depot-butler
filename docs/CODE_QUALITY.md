# Code Quality Assessment & Improvement Plan

**Assessment Date**: December 21, 2025
**Last Updated**: December 21, 2025
**Overall Grade**: B+ (Good, with room for improvement)
**Test Coverage**: 71%
**Status**: ✅ Quick Wins Complete | Ready for Sprint 1

---

## Table of Contents

1. [Implementation Status](#implementation-status)
2. [Quality Metrics](#quality-metrics)
3. [Current Strengths](#current-strengths)
4. [Areas for Improvement](#areas-for-improvement)
5. [Action Plan](#action-plan)
6. [Quick Wins](#quick-wins)
7. [References](#references)

---

## Implementation Status

### ✅ Completed (December 21, 2025)

#### Quick Wins - All Complete

1. **✅ Quality Tooling Installed**
   - Added ruff 0.14.10 (linter & formatter)
   - Added radon 6.0.1 (complexity analysis)
   - Added mypy 1.19.1 (type checking)
   - Added pre-commit 4.5.1 (git hooks)
   - All tools configured in pyproject.toml

2. **✅ GitHub Actions CI/CD**
   - Created `.github/workflows/quality.yml`
   - Runs on push and pull requests
   - Executes lint, format check, tests, complexity analysis

3. **✅ EditorConfig Created**
   - Created `.editorconfig` with Python, YAML, Markdown rules
   - Ensures consistent formatting across editors

4. **✅ Pre-commit Hooks Configured**
   - Created `.pre-commit-config.yaml`
   - Runs ruff, ruff-format, standard checks, mypy
   - Installed and tested: `pre-commit install`

5. **✅ Code Quality Issues Fixed**
   - Fixed 137 ruff violations (126 auto-fixed, 11 manual)
   - Consolidated entry points (removed `__main__.py`)
   - Fixed undefined variables, exception chains, nested context managers
   - Resolved all linting errors

6. **✅ Build System Configured**
   - Added `[build-system]` section to pyproject.toml
   - Package now auto-installs with `uv sync --extra dev`
   - Entry point: `python -m depotbutler` or `uv run depotbutler`

7. **✅ All Tests Passing**
   - 176/176 tests passing
   - 0 warnings (fixed AsyncMock RuntimeWarning)
   - Test execution time: ~10 seconds

### 📋 Next Steps

**Sprint 1** (Jan-Feb 2026): Test Coverage Enhancement
- Target: Increase coverage from 71% to 80%+
- Focus: discovery.py (39%), workflow.py (66%), onedrive.py (64%)
- See [Action Plan](#action-plan) for details

---

## Quality Metrics

### Current State

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Test Coverage | 71% | 85% | ⚠️ Needs work |
| Largest Module | 824 lines | <500 | ⚠️ Refactor needed |
| Type Coverage | ~95% | 90% | ✅ Excellent |
| Avg Function Length | ~30 lines | <50 | ✅ Good |
| Cyclomatic Complexity | Unknown | <10/func | ⚠️ Check needed |
| Code Duplication | Low | <5% | ✅ Good |
| Custom Exceptions | 0 | Domain-specific | ⚠️ Add |

### Module Sizes (Lines of Code)

```
mongodb.py          824 lines  ⚠️  Exceeds 500
workflow.py         762 lines  ⚠️  Exceeds 500
mailer.py           615 lines  ⚠️  Exceeds 500
onedrive.py         604 lines  ⚠️  Exceeds 500
httpx_client.py     372 lines  ✅
discovery.py        194 lines  ✅
edition_tracker.py  130 lines  ✅
settings.py          94 lines  ✅
```

### Test Coverage by Module

```
edition_tracker.py  100%  ✅
models.py           100%  ✅
publications.py     100%  ✅
settings.py         100%  ✅
helpers.py          100%  ✅
logger.py           100%  ✅
db/__init__.py      100%  ✅
mailer.py            78%  ⚠️
httpx_client.py      74%  ⚠️
mongodb.py           71%  ⚠️
workflow.py          66%  ⚠️
onedrive.py          64%  ⚠️
discovery.py         39%  ❌
```

---

## Current Strengths

### ✅ Architecture & Design

- **Clean separation of concerns**: Domain (models), Infrastructure (db, httpx), Services (mailer, onedrive), Workflow orchestration
- **Type hints everywhere**: Excellent type coverage with Pydantic models and function annotations
- **Async/await properly used**: Consistent async patterns with context managers
- **Configuration management**: Centralized settings with Pydantic validation
- **Logging discipline**: Structured logging with timing metrics throughout

### ✅ Code Style

- **Consistent naming**: Clear, descriptive names for classes, functions, and variables
- **Docstrings present**: Most public methods are documented
- **Error handling**: Specific exceptions with structured logging
- **Modern Python**: Uses dataclasses, Pydantic v2, Python 3.13 features
- **No technical debt markers**: Zero TODOs, FIXMEs, or HACKs in codebase

### ✅ Best Practices

- **No circular dependencies**: Clean import structure
- **Modern tooling**: uv, pytest, Pydantic v2
- **Environment-based configuration**: Type-safe settings
- **Async done right**: Proper context managers, no blocking calls
- **Clean test structure**: 176 tests organized by module

---

## Areas for Improvement

### 1. Module Size & Complexity (Priority: HIGH)

#### Problem: 4 modules exceed 600 lines

**mongodb.py (824 lines)** - Multiple responsibilities:
```
Current structure:
├── Connection management
├── Recipients CRUD + filtering logic
├── Publications CRUD
├── Edition tracking
├── Statistics updates
├── Cookie management
├── App config
└── Complex query builders
```

**Recommended refactoring:**
```
src/depotbutler/db/
  ├── connection.py           # MongoDBService (connect/close)
  ├── repositories/
  │   ├── __init__.py
  │   ├── recipients.py       # RecipientRepository
  │   ├── publications.py     # PublicationRepository
  │   └── editions.py         # EditionRepository
  ├── queries.py              # Query builders
  └── config.py               # App config & cookie management
```

**Benefits:**
- Easier testing (mock only what you need)
- Clearer single responsibility
- Reduces cognitive load (200-300 lines each)
- Better code navigation

---

**workflow.py (762 lines)** - Orchestration + business logic mixed

**Issues:**
- `_process_single_publication` method: 150+ lines
- Contains email composition logic
- Mixes workflow orchestration with domain logic

**Recommended refactoring:**
```
src/depotbutler/services/
  ├── __init__.py
  ├── publication_processor.py  # Process single publication
  ├── notification_service.py   # Consolidated notifications
  └── cookie_checker.py         # Cookie expiration logic

# Keep workflow.py focused on orchestration only
```

**Example breakdown:**
```python
# Instead of one 150-line method:
async def _process_single_publication(self, pub_data: dict) -> PublicationResult:
    result = self._init_result(pub_data)

    edition = await self._fetch_edition(pub_data)
    if not edition:
        return result

    if await self._is_already_processed(edition, pub_data):
        result.already_processed = True
        return result

    pdf_path = await self._download_edition(edition, pub_data)
    if not pdf_path:
        result.error = "Download failed"
        return result

    await self._distribute_edition(pdf_path, edition, pub_data, result)
    await self._mark_as_processed(edition, pub_data)
    await self._cleanup_files(pdf_path)

    result.success = True
    return result

# Each helper: 10-30 lines, easily testable
```

---

**mailer.py (615 lines)** - Email template + SMTP mixed

**Recommended refactoring:**
```
src/depotbutler/mailer/
  ├── __init__.py
  ├── service.py         # EmailService (SMTP logic)
  ├── templates.py       # HTML/text generation
  └── composers.py       # MIME message composition
```

---

**onedrive.py (604 lines)** - Auth + file ops + folder management

**Recommended refactoring:**
```
src/depotbutler/onedrive/
  ├── __init__.py
  ├── service.py         # File upload/download
  ├── auth.py            # MSAL authentication
  └── folder_manager.py  # Folder operations
```

---

### 2. Test Coverage Gaps (Priority: HIGH)

#### Critical Uncovered Code

**discovery.py: 39% coverage** ❌

- Lines 82-83, 101-232: Publication sync logic barely tested
- Need integration tests for account discovery

**onedrive.py: 64% coverage** ⚠️

- Lines 411-509, 531-629: Upload logic partially tested
- Multi-recipient uploads not tested
- Folder creation logic needs coverage

**mailer.py: 78% coverage** ⚠️

- Lines 369-483: Warning/error notifications untested
- Consolidated notification emails not covered

**workflow.py: 66% coverage** ⚠️

- Lines 224-238, 260-266: Error paths untested
- Lines 773-852: Consolidated notifications not covered
- Cookie expiration checks partially tested

#### Action Items

**Add new test files:**

```python
tests/
  ├── test_discovery_sync.py          # NEW - Test publication discovery
  ├── test_onedrive_multi_upload.py   # NEW - Test multi-recipient uploads
  ├── test_notification_emails.py     # NEW - Test all email types
  └── test_workflow_error_paths.py    # ENHANCE - Test failure scenarios
```

**Test scenarios to add:**

- Discovery: Account sync with new/updated/removed publications
- OneDrive: Multi-recipient uploads with custom folders
- Mailer: Warning, error, and consolidated notification emails
- Workflow: Cookie expiration notifications, download failures, partial successes

---

### 3. Code Duplication (Priority: MEDIUM)

#### Problem: Recipient preference resolution duplicated

**Location**: `mongodb.py` lines 268-333

Two nearly identical methods:

- `get_onedrive_folder_for_recipient()`
- `get_organize_by_year_for_recipient()`

**Recommended solution:**

```python
# Generic preference resolver
def get_recipient_preference(
    recipient: dict,
    publication: dict,
    pref_key: str,
    default: Any
) -> Any:
    """
    Generic preference resolver with recipient override.

    Priority:
    1. Recipient's custom preference for this publication
    2. Publication's default setting
    3. Provided default value

    Args:
        recipient: Recipient document with publication_preferences
        publication: Publication document
        pref_key: Key to look up (e.g., 'custom_onedrive_folder')
        default: Default value if not found

    Returns:
        Resolved preference value
    """
    # Check recipient's custom preference
    for pref in recipient.get("publication_preferences", []):
        if pref.get("publication_id") == publication["publication_id"]:
            value = pref.get(pref_key)
            if value is not None:
                logger.debug(
                    f"Using recipient override for {recipient['email']}: "
                    f"{pref_key}={value}"
                )
                return value
            break

    # Fall back to publication default
    pub_value = publication.get(pref_key, default)
    logger.debug(
        f"Using publication default for {recipient['email']}: "
        f"{pref_key}={pub_value}"
    )
    return pub_value

# Usage:
folder = get_recipient_preference(
    recipient, publication, "custom_onedrive_folder", ""
)
organize_by_year = get_recipient_preference(
    recipient, publication, "organize_by_year", True
)
```

---

### 4. Magic Numbers & Constants (Priority: LOW)

#### Problem: Hardcoded configuration values

**Found in codebase:**

- `serverSelectionTimeoutMS=5000` (mongodb.py:55)
- `timeout=30.0` (httpx_client.py)
- `warning_days = 5` (default in multiple places)
- `length=None` (MongoDB cursor limits)

**Recommended solution:**

```python
# Add to settings.py:

class DatabaseSettings(BaseSettings):
    """MongoDB configuration settings."""
    connection_timeout_ms: int = 5000
    query_timeout_ms: int = 10000
    cursor_batch_size: int = 1000

    model_config = SettingsConfigDict(
        env_prefix="MONGODB_",
        case_sensitive=False,
    )

class HttpSettings(BaseSettings):
    """HTTP client configuration settings."""
    request_timeout: float = 30.0
    max_retries: int = 3
    retry_backoff: float = 2.0

    model_config = SettingsConfigDict(
        env_prefix="HTTP_",
        case_sensitive=False,
    )

class NotificationSettings(BaseSettings):
    """Notification and alerting settings."""
    cookie_warning_days: int = 5
    send_summary_emails: bool = True
    admin_notification_enabled: bool = True

    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION_",
        case_sensitive=False,
    )

# Add to Settings class:
class Settings:
    def __init__(self):
        self.boersenmedien = BoersenmedienSettings()
        self.onedrive = OneDriveSettings()
        self.mail = MailSettings()
        self.tracking = TrackingSettings()
        self.mongodb = MongoDBSettings()
        self.discovery = DiscoverySettings()
        self.database = DatabaseSettings()      # NEW
        self.http = HttpSettings()              # NEW
        self.notifications = NotificationSettings()  # NEW
```

---

### 5. Error Handling Improvements (Priority: MEDIUM)

#### Problem: Generic exception handling, no domain exceptions

**Current state**: Generic `except Exception` blocks everywhere

**Issues:**

1. Unclear what kind of errors can occur
2. No distinction between retryable vs permanent failures
3. No custom domain exceptions
4. Difficult to handle errors appropriately at higher levels

**Recommended solution:**

Create domain-specific exceptions:

```python
# src/depotbutler/exceptions.py

class DepotButlerError(Exception):
    """Base exception for all depot-butler errors."""
    pass


class AuthenticationError(DepotButlerError):
    """
    Authentication failed - user action required.

    Examples:
    - Cookie expired
    - Invalid credentials
    - OAuth refresh token invalid
    """
    pass


class TransientError(DepotButlerError):
    """
    Temporary failure - safe to retry.

    Examples:
    - Network timeout
    - Service temporarily unavailable
    - Rate limit exceeded
    """
    pass


class PublicationNotFoundError(DepotButlerError):
    """Publication doesn't exist in account."""
    pass


class EditionNotFoundError(DepotButlerError):
    """No edition available for publication."""
    pass


class DownloadError(DepotButlerError):
    """Failed to download PDF file."""
    pass


class UploadError(DepotButlerError):
    """Failed to upload file to OneDrive."""
    pass


class EmailDeliveryError(DepotButlerError):
    """Failed to send email."""
    pass


class ConfigurationError(DepotButlerError):
    """Invalid or missing configuration."""
    pass
```

**Usage example:**

```python
# In httpx_client.py:
from depotbutler.exceptions import AuthenticationError, TransientError

async def login(self) -> int:
    """Authenticate with boersenmedien.com."""
    try:
        cookie_value = await mongodb.get_auth_cookie()
        if not cookie_value:
            raise AuthenticationError(
                "No authentication cookie found. "
                "Run: uv run python scripts/update_cookie_mongodb.py"
            )

        # ... attempt login ...

        if response.status_code == 401:
            raise AuthenticationError("Cookie expired or invalid")

        if response.status_code >= 500:
            raise TransientError(f"Server error: {response.status_code}")

    except httpx.TimeoutException as e:
        raise TransientError("Login timeout") from e
    except httpx.NetworkError as e:
        raise TransientError("Network error during login") from e

# In workflow.py:
from depotbutler.exceptions import AuthenticationError, TransientError

async def run_full_workflow(self):
    try:
        await self.boersenmedien_client.login()
    except AuthenticationError as e:
        # Clear: User must update cookie
        logger.error(f"Authentication failed: {e}")
        await self.email_service.send_error_notification(
            error_msg=f"Authentication failed:<br>{e}<br><br>"
                     f"Please update your cookie.",
            title="Authentication Required"
        )
        return {"success": False, "error": str(e)}
    except TransientError as e:
        # Clear: Retry logic
        logger.warning(f"Temporary failure: {e}")
        await asyncio.sleep(5)
        return await self.run_full_workflow()  # Retry
```

---

### 6. Function Complexity (Priority: MEDIUM)

#### Problem: Some functions exceed recommended complexity

**Long functions detected:**

1. **workflow.py:_process_single_publication** (~150 lines)
   - Multiple responsibilities
   - Nested try-except blocks
   - Hard to test individual steps

2. **httpx_client.py:login** (~100 lines)
   - Complex cookie validation logic
   - Multiple nested conditionals
   - Mixed concerns (validation, logging, authentication)

#### Recommended approach

**Use McCabe complexity analysis:**

```bash
# Install radon
uv add --dev radon

# Check complexity
uv run radon cc src/depotbutler -a --total-average

# Find functions with complexity > 10
uv run radon cc src/depotbutler -n B
```

**Target**: Keep cyclomatic complexity < 10 per function

---

### 7. Async Context Manager Usage (Priority: LOW)

#### Observation: Some async operations could use context managers more consistently

**Example in httpx_client.py:**

```python
# Current:
self.client = httpx.AsyncClient(
    cookies=cookies,
    headers=headers,
    follow_redirects=True,
    timeout=30.0
)

# Better (if client is short-lived):
async with httpx.AsyncClient(
    cookies=cookies,
    headers=headers,
    follow_redirects=True,
    timeout=30.0
) as client:
    # Use client
    pass
```

**Note**: Current implementation is fine for long-lived clients. This is a minor point.

---

## Action Plan

### Sprint 1: High-Priority Fixes (1-2 weeks)

**Goal**: Address critical quality issues

- [ ] **1. Add domain exceptions** (`src/depotbutler/exceptions.py`)
  - Create exception hierarchy
  - Replace generic `except Exception` in critical paths
  - Update error handling in workflow, httpx_client, onedrive
  - Estimated effort: 4 hours

- [ ] **2. Increase test coverage to 80%+**
  - Add `tests/test_discovery_sync.py` (discovery.py: 39% → 70%)
  - Add `tests/test_onedrive_multi_upload.py` (onedrive.py: 64% → 80%)
  - Add `tests/test_notification_emails.py` (mailer.py: 78% → 85%)
  - Enhance `tests/test_workflow_error_paths.py` (workflow.py: 66% → 75%)
  - Estimated effort: 12 hours

- [ ] **3. Extract constants to settings**
  - Add DatabaseSettings, HttpSettings, NotificationSettings
  - Replace hardcoded values throughout codebase
  - Update .env.example with new variables
  - Estimated effort: 3 hours

- [ ] **4. Break down long functions**
  - Refactor `workflow.py:_process_single_publication` (150 lines → 6 methods of 20-30 lines)
  - Refactor `httpx_client.py:login` (100 lines → 4 methods)
  - Add unit tests for extracted methods
  - Estimated effort: 6 hours

**Total Sprint 1 effort**: ~25 hours (1 week at 50% capacity)

---

### Sprint 2: Architectural Improvements (2-3 weeks)

**Goal**: Reduce module sizes and improve maintainability

- [ ] **5. Split `mongodb.py` into repository pattern**

  ```text
  src/depotbutler/db/
    ├── connection.py (100 lines)
    ├── repositories/
    │   ├── recipients.py (200 lines)
    │   ├── publications.py (150 lines)
    │   └── editions.py (150 lines)
    ├── queries.py (100 lines)
    └── config.py (100 lines)
  ```

  - Create repository classes
  - Move query logic to dedicated module
  - Update imports throughout codebase
  - Ensure all 35 mongodb tests still pass
  - Estimated effort: 16 hours

- [ ] **6. Extract email templates from `mailer.py`**

  ```text
  src/depotbutler/mailer/
    ├── service.py (300 lines - SMTP logic)
    ├── templates.py (200 lines - HTML generation)
    └── composers.py (150 lines - MIME composition)
  ```

  - Create template rendering module
  - Extract MIME composition logic
  - Update mailer tests
  - Estimated effort: 10 hours

- [ ] **7. Refactor `onedrive.py` auth/operations split**

  ```text
  src/depotbutler/onedrive/
    ├── service.py (350 lines - file operations)
    ├── auth.py (200 lines - MSAL)
    └── folder_manager.py (100 lines)
  ```

  - Separate authentication logic
  - Extract folder management
  - Update OneDrive tests
  - Estimated effort: 12 hours

**Total Sprint 2 effort**: ~38 hours (2 weeks at 80% capacity)

---

### Sprint 3: Polish & Tooling (1 week)

**Goal**: Add automated quality checks

- [ ] **8. Add complexity analysis**
  - Install radon, mccabe
  - Add complexity check to CI/CD
  - Fix functions with complexity > 10
  - Estimated effort: 4 hours

- [ ] **9. Add pre-commit hooks**
  - Install pre-commit
  - Configure black, ruff, mypy
  - Add to documentation
  - Estimated effort: 3 hours

- [ ] **10. Code quality documentation**
  - Document coding standards
  - Add contribution guidelines
  - Create architecture diagrams
  - Estimated effort: 5 hours

**Total Sprint 3 effort**: ~12 hours (1 week at 50% capacity)

---

## Quick Wins ✅ COMPLETED

**Status**: ✅ All items completed (December 21, 2025)
**Time Investment**: 4 hours
**Impact**: HIGH - Quality baseline established

### Can implement today (< 2 hours)

### ✅ 1. Add linting and formatting tools - COMPLETED

**Status**: ✅ All tools installed and configured

**Updated `pyproject.toml`:**

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-mock>=3.14.0",
    "pytest-cov>=5.0.0",
    "radon>=6.0.1",        # Complexity analysis
    "ruff>=0.8.0",         # Linting + formatting
    "mypy>=1.13.0",        # Type checking
]

[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
]
ignore = [
    "E501",  # Line too long (handled by formatter)
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports in __init__

[tool.mypy]
python_version = "3.13"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**Commands:**

```bash
# Install dev dependencies
uv sync --extra dev

# Run linter
uv run ruff check src/depotbutler

# Auto-fix issues
uv run ruff check --fix src/depotbutler

# Format code
uv run ruff format src/depotbutler

# Check complexity
uv run radon cc src/depotbutler -a --total-average

# Find complex functions (grade B or worse)
uv run radon cc src/depotbutler -n B
```

#### ✅ 2. Add GitHub Actions workflow - COMPLETED

**Status**: ✅ Workflow created and operational

**Created `.github/workflows/quality.yml`:**

```yaml
name: Code Quality

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Lint with ruff
        run: uv run ruff check src/depotbutler

      - name: Check formatting
        run: uv run ruff format --check src/depotbutler

      - name: Run tests with coverage
        run: uv run pytest --cov=src/depotbutler --cov-report=term --cov-report=xml

      - name: Check complexity
        run: |
          uv run radon cc src/depotbutler -n C
          uv run radon mi src/depotbutler -n B
```

#### ✅ 3. Entry point consolidation - COMPLETE

**Actions taken:**

- ✅ Removed `src/depotbutler/__main__.py` (redundant)
- ✅ Consolidated entry point in `src/depotbutler/main.py`
- ✅ Removed `if __name__ == "__main__"` from `workflow.py`
- ✅ Added `[build-system]` section to pyproject.toml
- ✅ Package now properly installs with `uv sync --extra dev`

**Entry point usage:**
```bash
# Using python -m
python -m depotbutler

# Using uv run
uv run depotbutler

# With arguments
python -m depotbutler --dry-run
```

#### ✅ 4. EditorConfig - COMPLETE

**Created `.editorconfig`:**

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_style = space
indent_size = 4
max_line_length = 88

[*.{yml,yaml,toml}]
indent_style = space
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

**Status:**
- ✅ File created and committed
- ✅ Ensures consistent formatting across editors
- ✅ Works with VS Code, IntelliJ, Sublime, Vim, etc.

---

## References

### Code Quality Guidelines

- **Python PEP 8**: https://peps.python.org/pep-0008/
- **Google Python Style Guide**: https://google.github.io/styleguide/pyguide.html
- **Clean Code Principles**: https://github.com/zedr/clean-code-python

### Metrics & Standards

- **Cyclomatic Complexity**: < 10 per function (McCabe)
- **Function Length**: < 50 lines (Martin Fowler)
- **Module Size**: 200-500 lines optimal, < 1000 maximum
- **Test Coverage**: > 80% for production code
- **Code Duplication**: < 5% (DRY principle)

### Tools

- **ruff**: Modern Python linter and formatter - https://docs.astral.sh/ruff/
- **radon**: Complexity analysis - https://radon.readthedocs.io/
- **pytest-cov**: Coverage reporting - https://pytest-cov.readthedocs.io/
- **mypy**: Static type checking - https://mypy.readthedocs.io/

### Architecture Patterns

- **Repository Pattern**: https://martinfowler.com/eaaCatalog/repository.html
- **Clean Architecture**: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- **Domain-Driven Design**: https://www.domainlanguage.com/ddd/

---

## Maintenance

This document should be reviewed and updated:

- **Quarterly**: Review metrics and progress on action items
- **After major refactorings**: Update module sizes and test coverage
- **When adding new features**: Ensure they follow established patterns
- **Before releases**: Verify quality gates are met

### Change Log

**December 21, 2025**:
- ✅ Completed all Quick Wins (4 hours)
- ✅ Installed quality tooling (ruff, radon, mypy, pre-commit)
- ✅ Created GitHub Actions CI/CD workflow
- ✅ Fixed 137 code style issues
- ✅ Consolidated entry points and configured build system
- ✅ Achieved 176/176 tests passing with 0 warnings
- 📋 Ready to begin Sprint 1: Test Coverage Enhancement

**Last Updated**: December 21, 2025
**Next Review**: March 21, 2026 (Sprint 1 completion)
