"""
Setup script to retrieve prerequisites for validation tests.

This script helps you:
1. Get authentication cookie from MongoDB config collection
2. Check Azure Storage setup
3. Download sample PDFs for testing

Run: uv run python scripts/validation/setup_prerequisites.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import os

from motor.motor_asyncio import AsyncIOMotorClient

from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

settings = Settings()
logger = get_logger(__name__)


async def get_cookie_from_mongodb():
    """Retrieve authentication cookie from MongoDB config collection."""
    logger.info("=" * 60)
    logger.info("STEP 1: Get Authentication Cookie from MongoDB")
    logger.info("=" * 60)

    client = None
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.mongodb.connection_string)
        db = client[settings.mongodb.name]
        config_collection = db["config"]

        # Get auth config document
        config = await config_collection.find_one({"_id": "auth_cookie"})

        if not config:
            logger.error("❌ No auth cookie found in MongoDB")
            logger.info("\nTo create auth cookie, run:")
            logger.info("  python scripts/update_cookie_mongodb.py")
            return None

        cookie = config.get("cookie_value", "")

        if not cookie:
            logger.error("❌ Cookie field is empty in config")
            logger.info("\nTo update cookie, run:")
            logger.info("  python scripts/update_cookie_mongodb.py")
            return None

        # Write to .env file
        env_path = Path(".env")
        env_lines = []

        if env_path.exists():
            with open(env_path) as f:
                env_lines = f.readlines()

        # Remove existing BOERSENMEDIEN_COOKIE line
        env_lines = [
            line for line in env_lines if not line.startswith("BOERSENMEDIEN_COOKIE=")
        ]

        # Add new cookie
        env_lines.append(f"BOERSENMEDIEN_COOKIE={cookie}\n")

        with open(env_path, "w") as f:
            f.writelines(env_lines)

        logger.info("✅ Cookie retrieved from MongoDB")
        logger.info("✅ Saved to .env file")
        logger.info(f"   Cookie length: {len(cookie)} characters")

        # Set in current environment for immediate use
        os.environ["BOERSENMEDIEN_COOKIE"] = cookie

        return cookie

    except Exception as e:
        logger.error(f"❌ Failed to get cookie: {e}")
        logger.info("\nTroubleshooting:")
        logger.info("1. Check MongoDB is running and accessible")
        logger.info("2. Verify DB_CONNECTION_STRING in .env")
        logger.info("3. Run: python scripts/init_app_config.py")
        return None
    finally:
        if client:
            client.close()


def check_azure_storage():
    """Check if Azure Storage connection string is set."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 2: Check Azure Storage Setup")
    logger.info("=" * 60)

    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

    if conn_str:
        logger.info("✅ AZURE_STORAGE_CONNECTION_STRING is set")
        logger.info(f"   Length: {len(conn_str)} characters")
        return True
    else:
        logger.warning("⚠️ AZURE_STORAGE_CONNECTION_STRING not set")
        logger.info("\nTo set up Azure Storage:")
        logger.info("1. Go to Azure Portal: https://portal.azure.com")
        logger.info("2. Create Storage Account (or use existing):")
        logger.info("   - Resource Group: depot-butler")
        logger.info("   - Storage Account Name: depotbutler<unique>")
        logger.info("   - Performance: Standard")
        logger.info("   - Replication: LRS (cheapest)")
        logger.info("3. Get connection string:")
        logger.info("   - Navigate to: Access Keys")
        logger.info("   - Copy 'Connection string' from Key1")
        logger.info("4. Add to .env file:")
        logger.info(
            '   AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."'
        )
        return False


def check_sample_pdfs():
    """Check if sample PDFs are available for testing."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 3: Check Sample PDFs")
    logger.info("=" * 60)

    data_dir = Path("data/tmp")
    data_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(data_dir.glob("*.pdf"))

    if pdf_files:
        logger.info(f"✅ Found {len(pdf_files)} PDF files:")
        for pdf in pdf_files[:5]:
            logger.info(f"   - {pdf.name}")
        if len(pdf_files) > 5:
            logger.info(f"   ... and {len(pdf_files) - 5} more")
        return True
    else:
        logger.warning("⚠️ No PDF files found in data/tmp/")
        logger.info("\nTo get sample PDFs:")
        logger.info("1. Log in to: https://konto.boersenmedien.com")
        logger.info("2. Navigate to Megatrend-Folger ausgaben")
        logger.info("3. Download 2-3 PDFs from different years:")
        logger.info("   - One recent (2025)")
        logger.info("   - One mid-range (2020)")
        logger.info("   - One old (2015)")
        logger.info("4. Save to: data/tmp/")
        logger.info("\nAlternatively, copy from OneDrive if you have them there.")
        return False


async def main():
    """Run all prerequisite checks and setup."""
    logger.info("VALIDATION PREREQUISITES SETUP")
    logger.info(
        "This script helps you set up everything needed for validation tests.\n"
    )

    results = {
        "cookie": False,
        "azure_storage": False,
        "sample_pdfs": False,
    }

    # Step 1: Get cookie
    cookie = await get_cookie_from_mongodb()
    results["cookie"] = bool(cookie)

    # Step 2: Check Azure Storage
    results["azure_storage"] = check_azure_storage()

    # Step 3: Check sample PDFs
    results["sample_pdfs"] = check_sample_pdfs()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SETUP SUMMARY")
    logger.info("=" * 60)

    status_icon = {True: "✅", False: "❌"}

    logger.info(
        f"{status_icon[results['cookie']]} Authentication Cookie: {'Ready' if results['cookie'] else 'Not set'}"
    )
    logger.info(
        f"{status_icon[results['azure_storage']]} Azure Storage: {'Ready' if results['azure_storage'] else 'Not configured'}"
    )
    logger.info(
        f"{status_icon[results['sample_pdfs']]} Sample PDFs: {len(list(Path('data/tmp').glob('*.pdf'))) if results['sample_pdfs'] else 0} files"
    )

    all_ready = all(results.values())

    if all_ready:
        logger.info("\n🎉 All prerequisites are ready!")
        logger.info("\nNext steps:")
        logger.info("1. Run validation tests:")
        logger.info("   uv run python scripts/validation/test_website_crawl.py")
        logger.info("   uv run python scripts/validation/test_pdf_parsing.py")
        logger.info("   uv run python scripts/validation/test_blob_storage.py")
        logger.info("2. Review results and proceed to Phase 0 implementation")
    else:
        logger.info("\n⚠️ Some prerequisites are missing")
        logger.info("Follow the instructions above to complete setup.")
        logger.info("\nYou can run this script again after setup to verify.")


if __name__ == "__main__":
    asyncio.run(main())
