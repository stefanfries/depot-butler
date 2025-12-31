"""
Analyze terminal output to identify duplicate editions.
Since the log file only has httpx logs, we'll use the terminal output
that was captured showing the tracking phase.
"""

# Based on the terminal output, I observed duplicate tracking entries
# Let me create a comprehensive list from MongoDB and show which dates exist

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    try:
        # Get all megatrend-folger editions
        editions = (
            await mongodb.db["processed_editions"]
            .find(
                {"publication_id": "megatrend-folger", "source": "web_historical"},
                {"publication_date": 1, "title": 1, "blob_path": 1, "_id": 0},
            )
            .sort("publication_date", 1)
            .to_list(None)
        )

        print("=" * 100)
        print("MEGATREND FOLGER EDITIONS IN MONGODB (Web Historical Import)")
        print("=" * 100)
        print(
            f"\nTotal: {len(editions)} unique editions from 2018-01-04 to 2025-12-18\n"
        )
        print(
            "Note: 475 editions were discovered from website, but 79 were duplicates (same publication_date)"
        )
        print(
            "MongoDB deduplicated them using unique edition_key: <date>_<publication_id>\n"
        )
        print("=" * 100)
        print(f"\n{'Date':<15} {'Title':<50} {'File Name':<40}")
        print("-" * 100)

        for edition in editions:
            date = edition["publication_date"]
            title = edition["title"][:48]
            # Extract filename from blob_path
            blob_path = edition.get("blob_path", "")
            filename = blob_path.split("/")[-1] if blob_path else "N/A"

            print(f"{date:<15} {title:<50} {filename:<40}")

        print("\n" + "=" * 100)
        print(
            f"\n✅ These are the {len(editions)} UNIQUE editions you should have in OneDrive"
        )
        print(
            "   Cross-check your local OneDrive files against these publication dates."
        )
        print(
            "   Any editions with different dates but same titles indicate website duplicates.\n"
        )

        # Show some statistics
        years = {}
        for edition in editions:
            year = edition["publication_date"][:4]
            years[year] = years.get(year, 0) + 1

        print("📊 Breakdown by year:")
        for year in sorted(years.keys()):
            print(f"   {year}: {years[year]} editions")

    finally:
        await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
