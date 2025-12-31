"""Map duplicate ausgabe IDs to their publication dates using MongoDB data."""

import asyncio
import re
from pathlib import Path

from depotbutler.db.mongodb import get_mongodb_service

# List of ausgabe IDs that were fetched multiple times (from log analysis)
DUPLICATE_AUSGABE_IDS = [
    "2920",
    "2921",
    "2922",
    "2923",
    "2924",
    "2925",
    "2927",
    "2937",
    "2938",
    "2939",
    "2940",
    "2943",
    "2944",
    "2945",
    "2946",
    "2947",
    "2948",
    "2949",
    "2950",
    "2951",
    "2952",
    "2953",
    "2954",
    "2955",
    "2959",
    "4876",
    "4879",
    "4884",
    "4887",
    "4890",
    "4891",
    "4893",
    "4894",
]


async def main():
    mongodb = await get_mongodb_service()

    try:
        # Get all editions
        editions = (
            await mongodb.db["processed_editions"]
            .find(
                {"publication_id": "megatrend-folger", "source": "web_historical"},
                {"publication_date": 1, "title": 1, "download_url": 1, "_id": 0},
            )
            .to_list(None)
        )

        # Extract ausgabe ID from download_url and map to edition
        url_pattern = re.compile(r"/ausgabe/(\d+)/")
        ausgabe_to_edition = {}

        for edition in editions:
            url = edition.get("download_url", "")
            match = url_pattern.search(url)
            if match:
                ausgabe_id = match.group(1)
                ausgabe_to_edition[ausgabe_id] = edition

        # Find which duplicate ausgabe IDs we have in MongoDB
        found_duplicates = []
        not_found = []

        for ausgabe_id in DUPLICATE_AUSGABE_IDS:
            if ausgabe_id in ausgabe_to_edition:
                edition = ausgabe_to_edition[ausgabe_id]
                found_duplicates.append(
                    (ausgabe_id, edition["publication_date"], edition["title"])
                )
            else:
                not_found.append(ausgabe_id)

        # Sort by publication date
        found_duplicates.sort(key=lambda x: x[1])

        print("=" * 100)
        print("PUBLICATION DATES WITH DUPLICATE ENTRIES")
        print("=" * 100)
        print(
            f"\nThese {len(found_duplicates)} publication dates had duplicate entries on the website:\n"
        )
        print(f"{'Ausgabe ID':<15} {'Publication Date':<20} {'Title':<50}")
        print("-" * 100)

        for ausgabe_id, pub_date, title in found_duplicates:
            print(f"{ausgabe_id:<15} {pub_date:<20} {title:<50}")

        if not_found:
            print(
                f"\n⚠️  {len(not_found)} ausgabe IDs not found in MongoDB (may have been different duplicates):"
            )
            print(f"   {', '.join(not_found)}")

        print("\n" + "=" * 100)
        print("\n📊 Summary:")
        print(f"   Ausgabe IDs with duplicates: {len(DUPLICATE_AUSGABE_IDS)}")
        print(f"   Mapped to dates: {len(found_duplicates)}")
        print("   Total duplicate requests removed: 78-79")

        # Group by year
        by_year = {}
        for _, pub_date, _ in found_duplicates:
            year = pub_date[:4]
            by_year[year] = by_year.get(year, 0) + 1

        print("\n📅 Duplicates by year:")
        for year in sorted(by_year.keys()):
            print(f"   {year}: {by_year[year]} dates with duplicates")

        # Save to file
        output_path = Path("data/tmp/duplicate_publication_dates.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("PUBLICATION DATES WITH DUPLICATE ENTRIES\n")
            f.write("=" * 100 + "\n\n")
            f.write("These dates had multiple entries on boersenmedien.com website\n")
            f.write(
                "MongoDB deduplicated them using unique edition_key (date_publication_id)\n\n"
            )
            f.write(f"Total: {len(found_duplicates)} dates\n\n")
            f.write("-" * 100 + "\n")
            f.write(f"{'Ausgabe ID':<15} {'Publication Date':<20} {'Title':<50}\n")
            f.write("-" * 100 + "\n")
            for ausgabe_id, pub_date, title in found_duplicates:
                f.write(f"{ausgabe_id:<15} {pub_date:<20} {title:<50}\n")
            f.write("\n" + "=" * 100 + "\n")
            f.write("\nJust the dates (for easy cross-checking):\n")
            f.write("-" * 100 + "\n")
            for _, pub_date, _ in found_duplicates:
                f.write(f"{pub_date}\n")

        print(f"\n✅ Full list saved to: {output_path}")
        print("\n📋 Just the dates:")
        print("   " + "-" * 40)
        for _, pub_date, _ in found_duplicates[:10]:
            print(f"   {pub_date}")
        if len(found_duplicates) > 10:
            print(f"   ... and {len(found_duplicates) - 10} more (see file)")

    finally:
        await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
