"""Quick cookie import - just paste the .AspNetCore.Cookies value"""
import json
from pathlib import Path
from datetime import datetime, timedelta

print("=" * 70)
print("QUICK COOKIE IMPORT")
print("=" * 70)
print()
print("1. Open your normal Edge/Chrome browser")
print("2. Go to https://login.boersenmedien.com/ and login")
print("3. Press F12 → Application → Cookies → .boersenmedien.com")
print("4. Find '.AspNetCore.Cookies'")
print("5. Click on it and copy the entire VALUE")
print()
print("=" * 70)
print()
print("Paste the cookie value below and press Enter:")

cookie_value = input().strip()

if cookie_value:
    # Create cookie structure
    expires = datetime.now() + timedelta(days=14)
    
    cookies = [
        {
            "name": ".AspNetCore.Cookies",
            "value": cookie_value,
            "domain": ".boersenmedien.com",
            "path": "/",
            "expires": int(expires.timestamp()),
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax"
        }
    ]
    
    # Save to file
    cookies_file = Path("data/browser_cookies.json")
    cookies_file.parent.mkdir(exist_ok=True)
    
    with open(cookies_file, 'w') as f:
        json.dump(cookies, f, indent=2)
    
    print()
    print(f"✓ Cookie saved to {cookies_file}")
    print(f"✓ Expires: {expires.strftime('%Y-%m-%d %H:%M')}")
    print()
    print("Now testing the cookie...")
    print()
    
    # Show the file content
    print(f"Cookie length: {len(cookie_value)} characters")
    print(f"Cookie preview: {cookie_value[:50]}...")
    print()
    print("Run this to test: uv run python test_manual_login.py")
else:
    print("No cookie value entered!")
