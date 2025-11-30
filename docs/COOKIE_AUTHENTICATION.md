# Cookie Authentication Guide

Due to Cloudflare Turnstile protection on boersenmedien.com, we use a **hybrid manual/automated approach** for authentication:

1. **Manual login** once in your normal browser (Cloudflare allows human interaction)
2. **Export the cookie** from browser DevTools
3. **Store it** in MongoDB
4. **Automated workflow** uses the saved cookie for all subsequent runs

## Cookie Storage

The system uses **MongoDB** for cookie storage. This provides:
- Easy updates from any environment (local development, Azure)
- Automatic expiration tracking and warnings
- Works consistently everywhere

Note: Local file (`data/browser_cookies.json`) is only used by helper scripts during the update process, not at runtime.

## Cookie Lifespan

The `.AspNetCore.Cookies` cookie expires after approximately **14 days**. You'll need to refresh it every 2 weeks.

## MongoDB Cookie Setup

### Initial Setup

1. **Login manually in your browser:**
   - Open https://login.boersenmedien.com/ in Chrome/Edge
   - Enter your email and password
   - Wait for Cloudflare challenge to complete (green checkmark)
   - Verify you can see the subscription page

2. **Export and upload the cookie to MongoDB:**
   ```bash
   uv run python scripts/update_cookie_mongodb.py
   ```
   
   Follow the prompts:
   - Press F12 in browser → Application tab → Cookies → .boersenmedien.com
   - Find `.AspNetCore.Cookies`
   - Copy its VALUE (long string)
   - Paste into the script
   - Optionally enter your name for tracking

3. **Verify it was saved:**
   ```bash
   uv run python scripts/update_cookie_mongodb.py --verify
   ```

### When Cookie Expires (~14 days)

Simply repeat steps 1-2 above. The update script makes it easy:
```bash
uv run python scripts/update_cookie_mongodb.py
```

The updated cookie is immediately available to:
- ✅ Local development runs
- ✅ Azure Container App production runs
- ✅ All environments (no Azure Portal needed!)

## Alternative: Development (Local File)

**Note:** The local file is now only used as an intermediate step when updating cookies. The workflow no longer reads from this file at runtime.

### Helper Script Workflow

1. **Export cookie to local file:**
   ```bash
   uv run python quick_cookie_import.py
   ```
   - Opens browser, paste cookie value
   - Saves to `data/browser_cookies.json`

2. **Upload to MongoDB:**
   ```bash
   uv run python scripts/update_cookie_mongodb.py
   ```
   - Reads local file (including expiration)
   - Uploads to MongoDB
   - Now available for all environments

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
├── browser_cookies.json      # Temporary file used by helper scripts only
├── browser_profile/           # Playwright browser cache (optional)
└── tmp/                       # Temporary PDF downloads
```

**Note:** Cookie is stored in MongoDB, not locally. Local file only used during the update process.

### Security

- **Cookie Storage**: MongoDB Atlas (encrypted at rest, TLS in transit)
- **Helper Scripts**: Temporarily use `data/browser_cookies.json` (gitignored)
- **Never commit** `data/browser_cookies.json` to git

## Troubleshooting

### "No cookies found" error

Run the update script to upload cookie to MongoDB:
```bash
uv run python scripts/update_cookie_mongodb.py
```

### "Cookie expired" or login fails

The cookie is older than ~14 days. Refresh it:
1. Login in browser and export: `uv run python quick_cookie_import.py`
2. Upload to MongoDB: `uv run python scripts/update_cookie_mongodb.py`

### Browser window doesn't open

The workflow doesn't open a browser - it uses the pre-exported cookie. To export a new cookie, use your normal browser (not automated).

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

Once you have a valid cookie from manual login, the automated workflow can reuse it for ~14 days.
