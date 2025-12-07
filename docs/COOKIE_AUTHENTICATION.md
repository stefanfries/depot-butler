# Cookie Authentication Guide

The system uses **HTTPX** with **cookie-based authentication** to access boersenmedien.com. This approach is:

- ✅ **Lightweight**: No browser overhead (~200MB smaller Docker image)
- ✅ **Fast**: Direct HTTP requests (no browser startup delay)
- ✅ **Cost-Effective**: 60-70% lower Azure resource usage
- ✅ **Simple**: Manual cookie export every 3 days

## Why Cookie Authentication?

Cloudflare Turnstile protection prevents automated login, so we use:

1. **Manual login** once in your browser (passes Cloudflare challenge)
2. **Export the cookie** from browser DevTools  
3. **Store it** in MongoDB
4. **HTTPX client** uses the cookie for authenticated HTTP requests

## Cookie Storage

The system uses **MongoDB exclusively** for cookie storage. This provides:

- Easy updates from any environment (local development, Azure)
- Automatic expiration tracking and warnings
- Works consistently everywhere
- No local files needed

## Cookie Lifespan

The `.AspNetCore.Cookies` cookie expires after approximately **3 days**. The system sends email alerts when the cookie is about to expire (configurable via `cookie_warning_days` in MongoDB, default: 5 days).

## MongoDB Cookie Setup

### Initial Setup

1. **Login manually in your browser:**

   - Open https://login.boersenmedien.com/ in Chrome/Edge
   - Enter your email and password
   - Wait for Cloudflare challenge to complete (green checkmark)
   - Verify you can see the subscription page

2. **Export and upload the cookie to MongoDB:**

   ```bash
   $env:PYTHONPATH="src" ; uv run python scripts/update_cookie_mongodb.py
   ```

   Follow the prompts:
   - Press F12 in browser → Application tab → Cookies → konto.boersenmedien.com
   - Click on `.AspNetCore.Cookies`
   - Copy its VALUE (long encrypted string, ~816 characters)
   - Paste into the script
   - Press Enter to use default 30-day expiration (or enter custom date)
   - Optionally enter your name for tracking

3. **Verify it was saved:**

   ```bash
   $env:PYTHONPATH="src" ; uv run python scripts/update_cookie_mongodb.py --verify
   ```

### When Cookie Expires (~30 days)

You'll receive an email alert when the cookie is about to expire. Simply repeat steps 1-2 above:

```bash
$env:PYTHONPATH="src" ; uv run python scripts/update_cookie_mongodb.py
```

The updated cookie is immediately available to:

- ✅ Local development runs
- ✅ Azure Container App production runs
- ✅ All environments (no Azure Portal needed!)

## Cookie Expiration Details

The `.AspNetCore.Cookies` cookie shows "No Expiration" in browser DevTools because it's a **session cookie** (expires when browser closes). However, the server has an expiration encoded inside the encrypted cookie value.

Since we can't decrypt the cookie to read the exact expiration, the update script uses a **30-day default** which is typical for authentication cookies. The system monitors expiration and sends alerts when needed.

## How It Works

### Code Behavior

The `BrowserScraper` class loads cookies from MongoDB:

```python
# Load from MongoDB (works everywhere - local dev and Azure production)
cookies = await mongodb.get_auth_cookie()

if not cookies:
    raise Exception("No authentication cookie found in MongoDB")
```

### File Structure

```
data/
├── browser_profile/           # Playwright browser cache (optional)
└── tmp/                       # Temporary PDF downloads
```

**Note:** Cookie is stored in MongoDB only, no local files.

### Security

- **Cookie Storage**: MongoDB Atlas (encrypted at rest, TLS in transit)
- **Access Control**: Connection string via environment variables only
- **No local storage**: Cookie never stored in local files (except during manual update process in memory)

## Troubleshooting

### "No cookies found" error

Run the update script to upload cookie to MongoDB:

```bash
$env:PYTHONPATH="src" ; uv run python scripts/update_cookie_mongodb.py
```

### "Cookie expired" or login fails

The cookie is older than ~30 days. Refresh it:

1. Login in browser (use incognito/private window for fresh session)
2. Copy cookie from DevTools
3. Upload to MongoDB: `$env:PYTHONPATH="src" ; uv run python scripts/update_cookie_mongodb.py`

### Browser window doesn't open

The workflow doesn't open a browser - it uses the pre-exported cookie from MongoDB. To export a new cookie, use your normal browser (Chrome, Edge, etc.) to login and copy the cookie value from DevTools.

## Why Manual Cookie Export?

**Cloudflare Turnstile** is designed to detect and block all forms of automation:

- ❌ Basic Playwright automation - detected
- ❌ Playwright with stealth mode - detected
- ❌ Undetected Chrome Driver - detected
- ❌ Using real Edge/Chrome via Playwright - detected

The Turnstile challenge fails with "failure_retry" status when automation is detected, preventing login form submission.

**Manual login** in your normal browser bypasses Cloudflare because:

- ✅ Real human interaction patterns
- ✅ Trusted browser fingerprint
- ✅ No automation signals (navigator.webdriver, CDP protocol, etc.)

Once you have a valid cookie from manual login, the automated workflow can reuse it for ~30 days.
