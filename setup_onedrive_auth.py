#!/usr/bin/env python3
"""
OneDrive OAuth Setup Script
Run this locally to generate refresh token for Azure Container deployment.

Usage:
1. Register app in Azure Portal
2. Update .env with CLIENT_ID, CLIENT_SECRET, TENANT_ID
3. Run: python setup_onedrive_auth.py
4. Follow browser prompts to authorize
5. Copy refresh token to Azure Container environment variables
"""

import asyncio
import sys
from urllib.parse import parse_qs, urlparse

from depotbutler.onedrive import OneDriveAuthenticator
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def main():
    """Interactive OAuth setup for OneDrive integration."""

    print("🔧 OneDrive OAuth Setup for Azure Container")
    print("=" * 50)

    try:
        authenticator = OneDriveAuthenticator()

        # Step 1: Get authorization URL
        auth_url = authenticator.get_authorization_url()

        print("\n📋 Setup Steps:")
        print("1. Open the following URL in your browser:")
        print(f"\n{auth_url}\n")
        print("2. Log in with your Microsoft account")
        print("3. Grant permissions to the application")
        print("4. You'll be redirected to localhost:8080 (may show error page)")
        print("5. Copy the FULL redirect URL from your browser address bar")
        print("\nThe URL will look like:")
        print("http://localhost:8080/?code=AUTHORIZATION_CODE&state=...")

        # Step 2: Get authorization code from user
        redirect_url = input("\n📥 Paste the full redirect URL here: ").strip()

        if not redirect_url:
            print("❌ No URL provided. Exiting.")
            return 1

        # Step 3: Parse authorization code
        try:
            parsed_url = urlparse(redirect_url)
            query_params = parse_qs(parsed_url.query)

            if "code" not in query_params:
                print("❌ No authorization code found in URL. Please try again.")
                return 1

            auth_code = query_params["code"][0]
            print(f"✅ Found authorization code: {auth_code[:20]}...")

        except Exception as e:
            print(f"❌ Error parsing URL: {e}")
            return 1

        # Step 4: Exchange code for tokens
        print("\n🔄 Exchanging authorization code for tokens...")
        result = authenticator.exchange_code_for_tokens(auth_code)

        if "refresh_token" in result:
            print("\n🎉 SUCCESS! OneDrive authentication configured.")
            print("\n" + "=" * 60)
            print("📋 NEXT STEPS FOR AZURE CONTAINER DEPLOYMENT:")
            print("=" * 60)
            print("\n1. Save this refresh token as environment variable in Azure:")
            print(f"   ONEDRIVE_REFRESH_TOKEN={result['refresh_token']}")
            print("\n2. Also set these environment variables in Azure Container:")
            print(f"   ONEDRIVE_CLIENT_ID={authenticator.client_id}")
            print(f"   ONEDRIVE_CLIENT_SECRET=<your_client_secret>")
            print(f"   ONEDRIVE_TENANT_ID={authenticator.tenant_id}")
            print("   ONEDRIVE_FOLDER=DepotButler")
            print("   ONEDRIVE_OVERWRITE_FILES=true")
            print("\n3. Your container will now be able to authenticate automatically!")
            print("\n⚠️  SECURITY: Keep the refresh token secure and don't share it.")

            return 0
        else:
            print(
                f"❌ Token exchange failed: {result.get('error_description', 'Unknown error')}"
            )
            return 1

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
