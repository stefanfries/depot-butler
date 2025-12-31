"""Find duplicate publication dates in MongoDB to identify which editions were deduplicated."""

import asyncio
from collections import Counter

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    try:
        # Get all megatrend-folger editions from web_historical
        editions = (
            await mongodb.db["processed_editions"]
            .find(
                {"publication_id": "megatrend-folger", "source": "web_historical"},
                {
                    "edition_key": 1,
                    "publication_date": 1,
                    "title": 1,
                    "download_url": 1,
                    "_id": 0,
                },
            )
            .to_list(None)
        )

        print(f"Total unique editions in MongoDB: {len(editions)}\n")

        # Count by date
        dates = [e["publication_date"] for e in editions]
        date_counter = Counter(dates)

        # All should be unique (1 per date) since edition_key is unique
        duplicates_in_db = {
            date: count for date, count in date_counter.items() if count > 1
        }

        if duplicates_in_db:
            print(
                f"⚠️  Found {len(duplicates_in_db)} dates with multiple entries in MongoDB:"
            )
            for date, count in sorted(duplicates_in_db.items()):
                print(f"   {date}: {count} entries")
        else:
            print("✅ All dates are unique in MongoDB (no duplicates)\n")

        # Now let's check the ausgabe URLs to see if different ausgabe IDs map to same dates
        print("=" * 80)
        print("Analyzing download URLs for duplicate ausgabe IDs...\n")

        # Extract ausgabe ID from download_url
        import re

        url_pattern = re.compile(r"/ausgabe/(\d+)/")

        ausgabe_to_editions = {}
        for edition in editions:
            url = edition.get("download_url", "")
            match = url_pattern.search(url)
            if match:
                ausgabe_id = match.group(1)
                if ausgabe_id not in ausgabe_to_editions:
                    ausgabe_to_editions[ausgabe_id] = []
                ausgabe_to_editions[ausgabe_id].append(edition)

        # Show stats
        print(f"Total unique ausgabe IDs in MongoDB: {len(ausgabe_to_editions)}")
        print(f"Total editions: {len(editions)}")
        print(f"Difference (editions discovered but not in DB): {475 - len(editions)}")

        # The difference tells us how many duplicates were on the website
        duplicates_found = 475 - len(editions)
        print(
            f"\n📊 Result: {duplicates_found} duplicate entries were present in the website data"
        )
        print(
            "   These were deduplicated by MongoDB using unique edition_key (date_publication_id)"
        )

        # Sort editions by date to see date range
        sorted_editions = sorted(editions, key=lambda e: e["publication_date"])
        print("\n📅 Date range:")
        print(
            f"   Earliest: {sorted_editions[0]['publication_date']} - {sorted_editions[0]['title']}"
        )
        print(
            f"   Latest:   {sorted_editions[-1]['publication_date']} - {sorted_editions[-1]['title']}"
        )

    finally:
        await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
