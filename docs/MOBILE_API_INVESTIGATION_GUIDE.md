# Mobile API Investigation Guide - DER AKTIONÄR iOS App

**Status**: Investigation Phase
**App**: DER AKTIONÄR (iOS)
**Goal**: Reverse engineer mobile API for automated authentication
**Expected Outcome**: 30+ day token lifetime, fully automated workflow

⚠️ **CRITICAL FINDING** (2026-01-13): Mobile app uses "Laden" (Load) → "Lesen" (Read) workflow, NOT direct PDF download. Investigation needed to determine if:

1. PDF downloads are available via API (even if not exposed in UI)
2. Content is stored in proprietary format (not PDF)
3. Mobile API is incompatible with our PDF delivery requirements

---

## Table of Contents

1. [Setup Traffic Interception](#setup-traffic-interception)
2. [Capture Authentication Flow](#capture-authentication-flow)
3. [Analyze API Structure](#analyze-api-structure)
4. [Implement Python Client](#implement-python-client)
5. [Integration & Testing](#integration--testing)
6. [Troubleshooting](#troubleshooting)

---

## Setup Traffic Interception

### Option A: mitmproxy (Free, Recommended)

#### Install mitmproxy

```bash
# macOS
brew install mitmproxy

# Windows (via Python)
pip install mitmproxy

# Linux
apt-get install mitmproxy
```

#### Start mitmproxy Web Interface

```bash
mitmweb --listen-host 0.0.0.0 --listen-port 8080

# Output:
# Web server listening at http://127.0.0.1:8081/
# Proxy server listening at http://0.0.0.0:8080/
```

### Option B: Charles Proxy ($50, Trial Available)

- Download: <https://www.charlesproxy.com>
- More user-friendly GUI
- Excellent filtering and export capabilities
- Better for beginners

### Option C: Burp Suite Community (Free)

- Download: <https://portswigger.net>
- Security-focused
- More advanced features
- Steeper learning curve

---

## Configure iOS Device

### Step 1: Find Your Computer's Local IP

```bash
# macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# Windows
ipconfig | findstr IPv4

# Example output: 192.168.1.100
```

### Step 2: Configure iPhone Proxy

1. iPhone → **Settings** → **Wi-Fi**
2. Tap **(i)** next to your connected network
3. Scroll down to **HTTP Proxy**
4. Select **Manual**
5. Enter:
   - **Server**: `192.168.1.100` (your computer's IP)
   - **Port**: `8080`
   - **Authentication**: Off
6. Tap **Save**

### Step 3: Install mitmproxy Certificate (Required for HTTPS)

**On iPhone:**

1. Open **Safari** (not Chrome/other browsers)
2. Navigate to: <http://mitm.it>
3. Tap the **Apple** icon
4. Download Configuration Profile
5. Close Safari
6. **Settings** → **Profile Downloaded** → **Install**
7. Enter your passcode
8. Tap **Install** (top right) → **Install** → **Done**

**Enable Certificate Trust:**

1. **Settings** → **General** → **About**
2. Scroll to bottom → **Certificate Trust Settings**
3. Enable **mitmproxy** certificate (toggle on)
4. Tap **Continue** in warning dialog

**⚠️ Important**: Remove certificate and proxy after testing!

---

## Capture Authentication Flow

### Prepare for Capture

**Delete and Reinstall App** (ensures fresh login):

1. Long-press "DER AKTIONÄR" app on iPhone
2. Delete app
3. App Store → Download "DER AKTIONÄR" again
4. Do NOT open yet

**Start Capture**:

1. Open mitmproxy web interface: <http://127.0.0.1:8081>
2. Clear any existing traffic (refresh page)
3. Ready to capture!

### Perform Login Sequence

**Capture the full flow:**

1. Open "DER AKTIONÄR" app on iPhone
2. Enter email and password
3. Tap login button
4. Wait for app to load (subscriptions page)
5. Navigate to one of your publications
6. **Tap "Laden" (Load) button** next to an edition
7. **Wait for button to change to "Lesen" (Read)**
8. **Tap "Lesen" (Read)** to open the viewer
9. **Observe what network calls happen** during steps 6-8
10. Return to mitmproxy interface

⚠️ **CRITICAL**: The app doesn't show a "Download" button. Investigation must determine:

- Does "Laden" step download a PDF file? (Check for `.pdf` or `application/pdf` in traffic)
- What format is the content? (PDF, images, JSON with page data, proprietary format)
- Is there a hidden PDF download endpoint the UI doesn't expose?
- Does the viewer use chunked/streaming content instead of single file?

### What to Look For

In mitmproxy web interface, filter/search for:**

1. **Login Request**

    ```http
    POST https://???/login
    POST https://???/auth/login
    POST https://???/api/v1/auth
    POST https://???/oauth/token

    Look for:
    - Domain containing: "boersenmedien", "aktionaer", "api", "auth"
    - Method: POST
    - Status: 200 OK
    - Content-Type: application/json
    ```

2. **Authentication Headers**

    ```http
    # In subsequent requests after login:
    Authorization: Bearer eyJhbGci...
    X-API-Key: abc123...
    X-Auth-Token: ...
    X-Session-Token: ...
    ```

3. **Login Request Body**

    ```json
    {
    "email": "your@email.com",
    "password": "your_password",
    "device_id": "UUID-HERE",
    "platform": "ios",
    "app_version": "3.0.1"
    }
    ```

4. **Login Response**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "def50200abc...",
  "token_type": "Bearer",
  "expires_in": 2592000,  // 30 days in seconds
  "user": {
    "id": 12345,
    "email": "your@email.com",
    "subscription_ids": [2477462, 2664610]
  }
}
```

### Export Captured Traffic

**mitmproxy:**

```bash
# In mitmweb interface:
# 1. Select the login request
# 2. Click "Export" → "cURL" (to see exact command)
# 3. Or click "Export" → "HAR" (for full session)
```

**Document Everything:**

- Full login URL
- All request headers
- Request body structure
- Response structure
- Any subsequent API calls
- Token locations in responses

**Most Importantly - Content Format Investigation:**

During "Laden" and "Lesen" steps, look for:

1. **PDF Downloads** (IDEAL - Strategy 1 viable):

   ```http
   GET /api/editions/13801/download
   Content-Type: application/pdf
   Content-Length: 15234567

   Response: Binary PDF data starting with %PDF
   ```

2. **Image-Based Content** (PROBLEMATIC - would need conversion):

   ```http
   GET /api/editions/13801/pages
   Response: {
     "pages": [
       {"url": "https://cdn.../page1.jpg"},
       {"url": "https://cdn.../page2.jpg"},
       ...
     ]
   }
   ```

3. **Proprietary Format** (MAJOR PROBLEM - Strategy 1 not viable):

   ```http
   GET /api/editions/13801/content
   Response: Custom binary format or encrypted data
   ```

4. **Streaming/Chunked Content** (PROBLEMATIC):

   ```http
   Multiple requests for page chunks
   No single download endpoint
   ```

**Key Questions to Answer:**

- Does ANY request return `Content-Type: application/pdf`?
- Are there image URLs that could be assembled into PDF?
- Is there a `/download` endpoint even if UI doesn't expose it?
- Can we access the web version's PDF download URL with mobile API token?

### Hybrid Approach: Mobile API Auth + Web API Downloads

**Even if mobile app doesn't provide PDF downloads**, the mobile API token might still be valuable:

**Scenario**: Mobile API for authentication, Web API for downloads

```python
# Step 1: Get long-lived token from mobile API
mobile_client = MobileApiClient(email, password)
token = await mobile_client.login()  # 30-day token

# Step 2: Use token with web API download endpoints
async with httpx.AsyncClient() as client:
    response = await client.get(
        "https://konto.boersenmedien.com/produkte/content/13801/download",
        headers={"Authorization": f"Bearer {token.access_token}"},
        # Or: cookies={".AspNetCore.Cookies": token.access_token}
    )
```

**This would still be valuable if:**

- ✅ Mobile token works for 30+ days
- ✅ Web API accepts mobile token in Authorization header
- ✅ Web API still returns PDF files
- ✅ Avoids manual cookie refresh every <7 days

**Investigation needed:**

1. Try mobile token with web API endpoints
2. Test if web API accepts Bearer token instead of cookie
3. Test if mobile token has same permissions as web cookie

---

## Analyze API Structure

### Decode JWT Tokens (If Applicable)

If token looks like `eyJhbGci...`, it's likely JWT:

**Online Tool**: <https://jwt.io>

**Command Line**:

```bash
# Extract payload (middle part between two dots)
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxMjM0NSwiZW1haWwiOiJ0ZXN0QHRlc3QuY29tIiwiZXhwIjoxNzM4NDI1NjAwfQ.signature"

# Get payload part
echo $TOKEN | cut -d'.' -f2 | base64 -d | jq

# Output:
{
  "user_id": 12345,
  "email": "test@test.com",
  "exp": 1738425600,  # Unix timestamp: 2026-02-01 00:00:00
  "iat": 1735833600,  # Issued at: 2026-01-02 00:00:00
  "subscription_ids": [2477462, 2664610]
}
```

**Calculate Token Lifetime**:

```python
from datetime import datetime

exp_timestamp = 1738425600  # from JWT
iat_timestamp = 1735833600

expiration = datetime.fromtimestamp(exp_timestamp)
issued = datetime.fromtimestamp(iat_timestamp)
lifetime_days = (expiration - issued).days

print(f"Token lifetime: {lifetime_days} days")  # 30 days
```

### Map All API Endpoints

**Document these patterns:**

| Endpoint Purpose | URL Pattern | Method | Auth Required |
| ---------------- | ----------- | ------ | ------------- |
| Login | `POST /auth/login` | POST | No |
| Refresh Token | `POST /auth/refresh` | POST | Refresh Token |
| List Subscriptions | `GET /subscriptions` | GET | Bearer Token |
| List Editions | `GET /subscriptions/{id}/editions` | GET | Bearer Token |
| Edition Details | `GET /editions/{id}` | GET | Bearer Token |
| Download PDF | `GET /editions/{id}/download` | GET | Bearer Token |

### Test Token Validity

**Quick Python Test**:

```python
import httpx
import asyncio

async def test_token():
    token = "PASTE_YOUR_CAPTURED_TOKEN_HERE"

    # Try accessing protected endpoint
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.boersenmedien.com/subscriptions",  # Adjust URL
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "DerAktionaer/3.0 iOS"
            },
            timeout=10.0
        )

        print(f"Status: {response.status_code}")
        print(f"Headers: {response.headers}")
        print(f"Response: {response.text[:500]}")

asyncio.run(test_token())
```

**Test Token Lifetime**:

- Day 1: Token works ✅
- Day 7: Test again
- Day 14: Test again
- Day 30: Test again
- Record when it stops working

---

## Implement Python Client

### Create MobileApiClient Class

```python
# src/depotbutler/mobile_api_client.py
"""
Mobile API client for Börsenmedien authentication.
Provides token-based authentication with 30+ day lifetime.
"""

from datetime import datetime, timedelta
from typing import Optional
import httpx
from pydantic import BaseModel, Field

from depotbutler.exceptions import AuthenticationError, TransientError
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class AuthToken(BaseModel):
    """Mobile API authentication token."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: datetime
    token_type: str = "Bearer"
    issued_at: datetime = Field(default_factory=datetime.utcnow)


class MobileApiClient:
    """
    Client for Börsenmedien mobile API.

    Handles authentication via mobile app API endpoints,
    providing longer token lifetimes than web cookie approach.
    """

    # Adjust these based on your captured traffic!
    BASE_URL = "https://api.boersenmedien.com/v2"  # EXAMPLE - UPDATE THIS
    APP_VERSION = "3.0.1"  # Check app version in mitmproxy
    USER_AGENT = f"DerAktionaer/{APP_VERSION} (iOS 17.0)"

    def __init__(self, email: str, password: str, device_id: Optional[str] = None):
        self.email = email
        self.password = password
        self.device_id = device_id or "depot-butler-automation"
        self.token: Optional[AuthToken] = None

    async def login(self) -> AuthToken:
        """
        Authenticate via mobile API.

        Returns:
            AuthToken with 30+ day lifetime

        Raises:
            AuthenticationError: If login fails
        """
        logger.info(f"Authenticating via mobile API for {self.email}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/auth/login",  # Adjust based on capture
                    json={
                        "email": self.email,
                        "password": self.password,
                        "device_id": self.device_id,
                        "platform": "ios"
                    },
                    headers={
                        "User-Agent": self.USER_AGENT,
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                )

                if response.status_code != 200:
                    error_msg = f"Mobile API login failed: {response.status_code}"
                    try:
                        error_detail = response.json()
                        error_msg += f" - {error_detail}"
                    except:
                        error_msg += f" - {response.text[:200]}"

                    raise AuthenticationError(error_msg)

                data = response.json()
                logger.debug(f"Login response keys: {data.keys()}")

                # Parse token from response
                access_token = data.get("access_token") or data.get("token")
                if not access_token:
                    raise AuthenticationError("No access_token in login response")

                refresh_token = data.get("refresh_token")

                # Calculate expiration
                expires_in = data.get("expires_in", 2592000)  # Default 30 days
                expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                token_type = data.get("token_type", "Bearer")

                self.token = AuthToken(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    token_type=token_type
                )

                logger.info(
                    f"✅ Mobile API login successful. "
                    f"Token expires: {expires_at.isoformat()} "
                    f"({(expires_at - datetime.utcnow()).days} days)"
                )

                return self.token

        except httpx.RequestError as e:
            raise TransientError(f"Network error during mobile API login: {e}")

    async def refresh_token(self) -> AuthToken:
        """
        Refresh access token using refresh token.
        Falls back to full login if refresh fails.
        """
        if not self.token or not self.token.refresh_token:
            logger.warning("No refresh token available, performing full login")
            return await self.login()

        logger.info("Refreshing mobile API token")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/auth/refresh",  # Adjust based on capture
                    json={"refresh_token": self.token.refresh_token},
                    headers={
                        "User-Agent": self.USER_AGENT,
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    logger.warning("Token refresh failed, performing full login")
                    return await self.login()

                data = response.json()

                access_token = data.get("access_token") or data.get("token")
                refresh_token = data.get("refresh_token", self.token.refresh_token)
                expires_in = data.get("expires_in", 2592000)
                expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                token_type = data.get("token_type", self.token.token_type)

                self.token = AuthToken(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    token_type=token_type
                )

                logger.info(f"✅ Token refreshed, expires: {expires_at.isoformat()}")
                return self.token

        except httpx.RequestError as e:
            logger.warning(f"Network error during refresh: {e}, performing full login")
            return await self.login()

    async def ensure_authenticated(self):
        """Ensure we have a valid token, refreshing if necessary."""
        if not self.token:
            await self.login()
            return

        time_until_expiry = self.token.expires_at - datetime.utcnow()

        # Refresh if less than 24 hours remaining
        if time_until_expiry < timedelta(hours=24):
            logger.info(
                f"Token expires in {time_until_expiry.total_seconds() / 3600:.1f} hours, "
                "refreshing..."
            )
            await self.refresh_token()
        else:
            logger.debug(
                f"Token still valid ({time_until_expiry.days} days remaining)"
            )

    async def get_subscriptions(self) -> list[dict]:
        """Get list of active subscriptions."""
        await self.ensure_authenticated()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/subscriptions",  # Adjust based on capture
                headers=self._auth_headers()
            )
            response.raise_for_status()
            return response.json()

    async def get_editions(self, subscription_id: int) -> list[dict]:
        """Get available editions for a subscription."""
        await self.ensure_authenticated()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/subscriptions/{subscription_id}/editions",
                headers=self._auth_headers()
            )
            response.raise_for_status()
            return response.json()

    async def download_pdf(self, edition_id: int) -> bytes:
        """
        Download PDF for an edition.

        Args:
            edition_id: Edition ID to download

        Returns:
            PDF file content as bytes
        """
        await self.ensure_authenticated()

        async with httpx.AsyncClient(timeout=120.0) as client:
            # First, get download URL (might be presigned)
            response = await client.get(
                f"{self.BASE_URL}/editions/{edition_id}/download",
                headers=self._auth_headers(),
                follow_redirects=True
            )

            content_type = response.headers.get("content-type", "")

            if "application/pdf" in content_type:
                # Direct PDF download
                logger.debug(f"Direct PDF download ({len(response.content)} bytes)")
                return response.content
            else:
                # Presigned URL in JSON response
                data = response.json()
                pdf_url = data.get("url") or data.get("download_url")

                if not pdf_url:
                    raise DownloadError("No download URL in response")

                logger.debug(f"Downloading from presigned URL: {pdf_url[:100]}...")

                # Download from presigned URL (no auth needed for presigned URLs)
                pdf_response = await client.get(pdf_url, timeout=120.0)
                pdf_response.raise_for_status()

                return pdf_response.content

    def _auth_headers(self) -> dict[str, str]:
        """Get authorization headers for API requests."""
        if not self.token:
            raise AuthenticationError("Not authenticated")

        return {
            "Authorization": f"{self.token.token_type} {self.token.access_token}",
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json"
        }
```

### MongoDB Integration

```python
# src/depotbutler/db/repositories/config.py

async def save_mobile_api_token(self, token: AuthToken) -> None:
    """Save mobile API token to MongoDB."""
    await self.collection.update_one(
        {"_id": "auth"},
        {
            "$set": {
                "auth_method": "mobile_api",
                "mobile_api_token": token.access_token,
                "mobile_api_refresh_token": token.refresh_token,
                "mobile_api_expires_at": token.expires_at,
                "mobile_api_issued_at": token.issued_at,
                "mobile_api_last_refresh": datetime.utcnow()
            }
        },
        upsert=True
    )
    logger.info(
        f"Saved mobile API token to MongoDB "
        f"[expires={token.expires_at.isoformat()}]"
    )

async def get_mobile_api_token(self) -> Optional[AuthToken]:
    """Retrieve mobile API token from MongoDB."""
    doc = await self.collection.find_one({"_id": "auth"})

    if not doc or doc.get("auth_method") != "mobile_api":
        return None

    if "mobile_api_token" not in doc:
        return None

    return AuthToken(
        access_token=doc["mobile_api_token"],
        refresh_token=doc.get("mobile_api_refresh_token"),
        expires_at=doc["mobile_api_expires_at"],
        token_type="Bearer",
        issued_at=doc.get("mobile_api_issued_at", datetime.utcnow())
    )
```

---

## Integration & Testing

### Update Settings

```python
# src/depotbutler/settings.py
class AuthSettings(BaseSettings):
    """Authentication settings."""

    # Mobile API (preferred method)
    use_mobile_api: bool = False  # Feature flag
    mobile_api_base_url: str = "https://api.boersenmedien.com/v2"

    # Credentials (shared for both methods)
    email: str = Field(..., alias="BOERSENMEDIEN_EMAIL")
    password: str = Field(..., alias="BOERSENMEDIEN_PASSWORD")

    model_config = SettingsConfigDict(
        env_prefix="BOERSENMEDIEN_",
        env_file=".env"
    )
```

### Update Workflow

```python
# src/depotbutler/workflow.py

async def run_workflow(dry_run: bool = False):
    """Main workflow execution."""

    logger.info("🚀 Starting DepotButler")

    # Authentication
    if settings.auth.use_mobile_api:
        logger.info("Using mobile API authentication")

        # Try to load existing token from MongoDB
        token = await mongodb.config.get_mobile_api_token()

        client = MobileApiClient(
            email=settings.auth.email,
            password=settings.auth.password
        )

        if token:
            client.token = token
            logger.info("Loaded existing mobile API token from MongoDB")

        # Ensure token is valid (will refresh/login if needed)
        await client.ensure_authenticated()

        # Save updated token to MongoDB
        await mongodb.config.save_mobile_api_token(client.token)

        # Use mobile API client methods for subscriptions/downloads
        subscriptions = await client.get_subscriptions()
        # ... rest of workflow using client methods

    else:
        logger.info("Using cookie-based authentication")
        client = HttpxBoersenmedienClient()
        await client.authenticate()
        # ... existing workflow
```

### Testing

```python
# tests/test_mobile_api_integration.py
import pytest
from depotbutler.mobile_api_client import MobileApiClient
from depotbutler.settings import get_settings

settings = get_settings()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_mobile_api_login():
    """Test mobile API login flow."""
    client = MobileApiClient(
        email=settings.auth.email,
        password=settings.auth.password
    )

    token = await client.login()

    assert token.access_token
    assert token.expires_at > datetime.utcnow()
    assert (token.expires_at - datetime.utcnow()).days >= 25

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_subscriptions():
    """Test retrieving subscriptions via mobile API."""
    client = MobileApiClient(
        email=settings.auth.email,
        password=settings.auth.password
    )

    await client.login()
    subscriptions = await client.get_subscriptions()

    assert len(subscriptions) > 0
    assert "id" in subscriptions[0]
    assert "name" in subscriptions[0]

@pytest.mark.integration
@pytest.mark.asyncio
async def test_download_pdf():
    """Test PDF download via mobile API."""
    client = MobileApiClient(
        email=settings.auth.email,
        password=settings.auth.password
    )

    await client.login()
    subscriptions = await client.get_subscriptions()
    editions = await client.get_editions(subscriptions[0]["id"])

    if editions:
        pdf_data = await client.download_pdf(editions[0]["id"])
        assert pdf_data.startswith(b"%PDF")
        assert len(pdf_data) > 100000  # At least 100KB
```

---

## Troubleshooting

### Issue 1: Certificate Pinning

**Symptom**: App won't connect when proxy is configured

**Solution A**: Use Jailbroken Device

- Disable certificate pinning with tools like `SSL Kill Switch 2`

**Solution B**: Use Objection (No Jailbreak Required)

```bash
# Install objection
pip3 install objection

# Patch app to disable pinning
objection patchipa --source DerAktionaer.ipa --output DerAktionaer-patched.ipa

# Install patched IPA
# Requires signing certificate or sideloading
```

**Solution C**: Use Android Emulator

- Easier to intercept traffic
- Can use rooted emulator
- If Android app available

### Issue 2: Device Registration Required

**Symptom**: API returns "device not registered" error

**Solution**:

- Capture `device_id` from first successful login
- Store in MongoDB alongside token
- Reuse same `device_id` for all requests

```python
# In MongoDB auth document:
{
    "_id": "auth",
    "mobile_api_device_id": "A1B2C3D4-E5F6-G7H8-I9J0-K1L2M3N4O5P6",
    ...
}
```

### Issue 3: No Refresh Endpoint

**Symptom**: No `/auth/refresh` endpoint found

**Solution**:

- Perform full re-login every 25 days (automated)
- Still much better than <7 day cookie expiration
- Schedule Azure job to run login every 25 days

```yaml
# Azure Container Apps Job: token-refresh
schedule: "0 0 */25 * *"  # Every 25 days
command: "python -m depotbutler.jobs.refresh_mobile_token"
```

### Issue 4: Token Expires Sooner Than Expected

**Symptom**: Token stops working after 7 days (same as cookie)

**Impact Assessment**:

- If 7 days: No better than cookie ❌
- If 14+ days: Modest improvement ✅
- If 30+ days: Significant improvement ⭐

**Action**: Document actual lifetime and decide if worth implementing

### Issue 5: Mobile App Doesn't Provide PDF Downloads ⚠️ CRITICAL

**Symptom**: App uses "Laden" → "Lesen" workflow with viewer, no direct PDF download

**Investigation Required**:

1. **Check what "Laden" actually downloads**:
   - Look for PDF files in mitmproxy traffic
   - Check for `Content-Type: application/pdf`
   - Monitor file size and format

2. **Test different content formats**:
   - PDF files (IDEAL)
   - Image sequences (could convert to PDF)
   - Proprietary format (BLOCKER)
   - Streaming content (BLOCKER)

3. **Try hybrid approach**:
   - Get mobile API token (long-lived)
   - Use token with web API endpoints
   - Test: `GET https://konto.boersenmedien.com/produkte/content/{id}/download`
   - With header: `Authorization: Bearer {mobile_token}`

**Possible Outcomes**:

**A. Mobile API provides PDF downloads** ✅

- Full Strategy 1 implementation viable
- Use mobile API for both auth and downloads

**B. Hybrid approach works** ✅

- Mobile API for authentication (30+ day token)
- Web API for PDF downloads (using mobile token)
- Still solves the <7 day cookie problem

**C. Mobile API incompatible with PDF downloads** ❌

- Strategy 1 NOT viable
- Fall back to Strategy 2 (Browser Extension)
- Or Strategy 3 (Enhanced Alerting)

**D. Images available, conversion needed** ⚠️

- Possible but complex
- Would need image-to-PDF conversion
- Increased complexity and storage requirements
- Only pursue if token lifetime is 30+ days

---

## Success Criteria

✅ **Full Success (Scenario A or B)**:

- Mobile API endpoints identified
- Token lifetime ≥14 days (ideally 30+ days)
- Automatic refresh possible
- **EITHER**: PDF downloads available via mobile API
- **OR**: Mobile token works with web API download endpoints

✅ **Partial Success (Hybrid Approach)**:

- Mobile API provides 30+ day token
- Token doesn't work for downloads directly
- BUT: Can still use web API with short-lived cookie
- Benefit: Reduces manual cookie updates from weekly to monthly

❌ **Investigation Failed - Not Worth Implementing If**:

- Token lifetime ≤7 days (no better than cookie)
- Certificate pinning blocks all interception attempts
- API requires complex device attestation
- No token refresh mechanism and frequent re-login needed
- **Mobile app provides no PDF access** (viewer only, proprietary format)
- **Mobile token incompatible with web API** (separate auth systems)

⚠️ **Conditional (Requires Decision)**:

- Images available but need conversion to PDF
- Token lifetime 14-20 days (modest improvement)
- Hybrid approach partially works but complex

- Token lifetime ≤7 days (no better than cookie)
- Certificate pinning blocks all interception attempts
- API requires complex device attestation
- No token refresh mechanism and frequent re-login needed

---

## Next Steps After Investigation

1. **Document findings** in this file
2. **Test token lifetime** (wait 7-14 days and retest)
3. **If successful**: Implement full MobileApiClient
4. **If not successful**: Fall back to Strategy 2 (Browser Extension)

---

**Investigation Started**: [DATE]
**Investigation Completed**: [DATE]
**Result**: [SUCCESS / PARTIAL / FAILED]
**Token Lifetime**: [X days]
**Recommended**: [YES / NO]
