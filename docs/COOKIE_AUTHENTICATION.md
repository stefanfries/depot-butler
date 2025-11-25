# Cookie Authentication Guide

Due to Cloudflare Turnstile protection on boersenmedien.com, we use a **hybrid manual/automated approach** for authentication:

1. **Manual login** once in your normal browser (Cloudflare allows human interaction)
2. **Export the cookie** from browser DevTools
3. **Store it** locally (development) or in Azure Key Vault (production)
4. **Automated workflow** uses the saved cookie for all subsequent runs

## Cookie Lifespan

The `.AspNetCore.Cookies` cookie expires after approximately **14 days**. You'll need to refresh it every 2 weeks.

## Development (Local Machine)

### Initial Setup

1. **Login manually in your browser:**
   ```bash
   # Open in normal Chrome/Edge (not automated)
   https://login.boersenmedien.com/
   ```
   - Enter your email and password
   - Wait for Cloudflare challenge to complete (green checkmark)
   - Verify you can see the subscription page

2. **Export the cookie:**
   ```bash
   uv run python quick_cookie_import.py
   ```
   - Press F12 in browser → Application tab → Cookies → .boersenmedien.com
   - Find `.AspNetCore.Cookies`
   - Copy its VALUE
   - Paste into the script prompt
   
3. **Cookie is saved to:** `data/browser_cookies.json`

4. **Run the workflow:**
   ```bash
   uv run python -m depotbutler full
   ```

### When Cookie Expires (~14 days)

You'll see an error or login failure. Simply repeat steps 1-2 above to refresh the cookie.

## Production (Azure Container Instance)

### Initial Setup

1. **Export cookie locally** (same as development steps 1-2)

2. **Upload to Azure Key Vault:**
   ```bash
   uv run python upload_cookie_to_keyvault.py
   ```
   This stores the cookie as secret `boersenmedien-session-cookie` in your Key Vault.

3. **Deploy to Azure:**
   ```bash
   # Your normal deployment process
   # The container will automatically use the Key Vault cookie
   ```

### When Cookie Expires (~14 days)

1. Login manually in your local browser
2. Export new cookie: `uv run python quick_cookie_import.py`
3. Upload to Key Vault: `uv run python upload_cookie_to_keyvault.py`
4. Next Azure run will use the new cookie automatically (no redeployment needed)

## How It Works

### Code Behavior

The `BrowserScraper` class automatically chooses the right cookie source:

```python
# In production (AZURE_KEY_VAULT_URL is set):
cookies = load_from_keyvault("boersenmedien-session-cookie")

# In development (local file exists):
cookies = load_from_file("data/browser_cookies.json")

# If neither exists:
raise Exception("No authentication cookie found")
```

### File Structure

```
data/
├── browser_cookies.json      # Local cookie storage (development)
├── browser_profile/           # Playwright browser cache (optional)
└── processed_editions.json    # Edition tracking
```

### Security

- **Local development**: Cookie stored in `data/` folder (gitignored)
- **Production**: Cookie stored in Azure Key Vault (encrypted at rest)
- **Never commit** `data/browser_cookies.json` to git

## Troubleshooting

### "No cookies found" error

Run `quick_cookie_import.py` to export cookie from your browser.

### "Cookie expired" or login fails

The cookie is older than ~14 days. Refresh it:
1. Login in browser
2. Run `quick_cookie_import.py`
3. Run `upload_cookie_to_keyvault.py` (if using Azure)

### "Key Vault authentication failed"

Make sure you're logged in: `az login`

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
