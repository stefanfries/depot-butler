"""
Upload authentication cookie to Azure Key Vault for production use.

This script reads the cookie from data/browser_cookies.json (created by quick_cookie_import.py)
and uploads it to Azure Key Vault as the secret 'boersenmedien-session-cookie'.

Usage:
1. Run: uv run python quick_cookie_import.py  (to get cookie from browser)
2. Run: uv run python upload_cookie_to_keyvault.py  (to upload to Key Vault)
3. Cookie will be available for Azure Container Instance to use

You need to have Azure CLI logged in or appropriate credentials set up.
"""

import json
import os
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main():
    print("=" * 70)
    print("UPLOAD COOKIE TO AZURE KEY VAULT")
    print("=" * 70)
    print()
    
    # Check for local cookie file
    cookies_file = Path("data/browser_cookies.json")
    if not cookies_file.exists():
        print("❌ ERROR: Cookie file not found!")
        print()
        print("Please run 'uv run python quick_cookie_import.py' first to")
        print("export your authentication cookie from the browser.")
        return 1
    
    # Read cookie value from file
    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    
    # Find the AspNetCore.Cookies cookie
    auth_cookie = next((c for c in cookies if c.get('name') == '.AspNetCore.Cookies'), None)
    
    if not auth_cookie:
        print("❌ ERROR: No .AspNetCore.Cookies found in file!")
        print(f"Found cookies: {[c.get('name') for c in cookies]}")
        return 1
    
    cookie_value = auth_cookie.get('value')
    if not cookie_value:
        print("❌ ERROR: Cookie has no value!")
        return 1
    
    print(f"✓ Found authentication cookie")
    print(f"  Length: {len(cookie_value)} characters")
    print(f"  Preview: {cookie_value[:50]}...")
    print()
    
    # Get Key Vault URL from environment
    key_vault_url = os.getenv("AZURE_KEY_VAULT_URL")
    if not key_vault_url:
        print("❌ ERROR: AZURE_KEY_VAULT_URL environment variable not set!")
        print()
        print("Please set it in your .env file:")
        print("AZURE_KEY_VAULT_URL=https://your-keyvault.vault.azure.net/")
        return 1
    
    print(f"Key Vault URL: {key_vault_url}")
    print()
    
    # Authenticate with Azure
    try:
        print("Authenticating with Azure...")
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=key_vault_url, credential=credential)
        print("✓ Authenticated with Azure")
        print()
    except Exception as e:
        print(f"❌ ERROR: Failed to authenticate with Azure: {e}")
        print()
        print("Make sure you're logged in with Azure CLI:")
        print("  az login")
        return 1
    
    # Upload cookie to Key Vault
    try:
        print("Uploading cookie to Key Vault as 'boersenmedien-session-cookie'...")
        secret = client.set_secret("boersenmedien-session-cookie", cookie_value)
        print("✓ Cookie uploaded successfully!")
        print()
        print(f"Secret name: {secret.name}")
        print(f"Secret version: {secret.properties.version}")
        if secret.properties.expires_on:
            print(f"Expires: {secret.properties.expires_on}")
        print()
        print("=" * 70)
        print("SUCCESS!")
        print("=" * 70)
        print()
        print("The authentication cookie is now stored in Azure Key Vault.")
        print("Your Azure Container Instance will automatically use it.")
        print()
        print("Remember to refresh this cookie every ~14 days:")
        print("1. Run: uv run python quick_cookie_import.py")
        print("2. Run: uv run python upload_cookie_to_keyvault.py")
        print()
        
        return 0
        
    except Exception as e:
        print(f"❌ ERROR: Failed to upload to Key Vault: {e}")
        print()
        print("Make sure:")
        print("1. Your Key Vault exists")
        print("2. You have 'Secret Officer' permissions on the Key Vault")
        print("3. The Key Vault URL is correct in .env")
        return 1

if __name__ == "__main__":
    exit(main())
