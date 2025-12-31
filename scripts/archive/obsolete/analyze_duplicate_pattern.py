"""Find publication dates with duplicates by analyzing what MongoDB has vs what was attempted."""

import asyncio
import re

from depotbutler.db.mongodb import get_mongodb_service

# From log analysis: These ausgabe IDs were fetched multiple times
DUPLICATE_AUSGABE_IDS_WITH_COUNTS = {
    "2920": 2,
    "2921": 2,
    "2922": 2,
    "2923": 2,
    "2924": 2,
    "2925": 2,
    "2927": 2,
    "2937": 4,
    "2938": 4,
    "2939": 4,
    "2940": 4,
    "2943": 2,
    "2944": 4,
    "2945": 4,
    "2946": 4,
    "2947": 4,
    "2948": 4,
    "2949": 4,
    "2950": 4,
    "2951": 4,
    "2952": 4,
    "2953": 2,
    "2954": 2,
    "2955": 2,
    "2959": 4,
    "4876": 4,
    "4879": 4,
    "4884": 3,
    "4887": 4,
    "4890": 4,
    "4891": 4,
    "4893": 5,
    "4894": 5,
}


async def main():
    mongodb = await get_mongodb_service()

    try:
        # Get all editions with their ausgabe IDs
        editions = (
            await mongodb.db["processed_editions"]
            .find(
                {"publication_id": "megatrend-folger", "source": "web_historical"},
                {"publication_date": 1, "title": 1, "download_url": 1, "_id": 0},
            )
            .sort("publication_date", 1)
            .to_list(None)
        )

        print("=" * 100)
        print("ANALYSIS: Identifying Duplicate Publication Dates")
        print("=" * 100)
        print(f"\nMongoDB has {len(editions)} unique editions")
        print("Log shows 475 requests were made")
        print(f"Difference: {475 - len(editions)} duplicates\n")

        # Extract all ausgabe IDs from MongoDB
        url_pattern = re.compile(r"/ausgabe/(\d+)/")
        mongodb_ausgabe_ids = set()

        for edition in editions:
            url = edition.get("download_url", "")
            match = url_pattern.search(url)
            if match:
                ausgabe_id = match.group(1)
                mongodb_ausgabe_ids.add(ausgabe_id)

        print(f"Unique ausgabe IDs in MongoDB: {len(mongodb_ausgabe_ids)}")
        print(
            f"Ausgabe IDs with duplicates in log: {len(DUPLICATE_AUSGABE_IDS_WITH_COUNTS)}\n"
        )

        # Calculate total duplicates
        total_extra = sum(
            count - 1 for count in DUPLICATE_AUSGABE_IDS_WITH_COUNTS.values()
        )
        print(f"Total duplicate requests: {total_extra}")
        print(f"Expected unique entries: 475 - {total_extra} = {475 - total_extra}")
        print(f"Actual MongoDB entries: {len(editions)}\n")

        # The issue: MongoDB has 396, but 475 - 78 = 397
        # This means there's 1 ausgabe ID that appears in duplicates but also exists in MongoDB

        # Find overlap
        overlap = mongodb_ausgabe_ids.intersection(
            set(DUPLICATE_AUSGABE_IDS_WITH_COUNTS.keys())
        )
        if overlap:
            print(
                f"⚠️  {len(overlap)} ausgabe ID(s) appear both in duplicates list AND MongoDB:"
            )
            for aid in sorted(overlap):
                print(
                    f"   - Ausgabe {aid}: fetched {DUPLICATE_AUSGABE_IDS_WITH_COUNTS[aid]} times"
                )

        print("\n" + "=" * 100)
        print("CONCLUSION:")
        print("=" * 100)
        print("""
Since MongoDB deduplicates by publication_date (edition_key), and we know:
- 475 editions were discovered/fetched
- 396 unique entries in MongoDB
- 79 duplicates were removed

The 79 duplicate entries correspond to editions that shared the same publication_date
with other editions. MongoDB kept ONE edition per date and discarded the rest.

Unfortunately, without the full terminal output showing the publication_date for each
of the 475 requests, we cannot definitively list which exact dates had duplicates.

However, we know that 33 unique ausgabe IDs were fetched multiple times:
""")

        # List the ausgabe IDs
        sorted_ids = sorted(
            DUPLICATE_AUSGABE_IDS_WITH_COUNTS.items(), key=lambda x: (int(x[0]), x[1])
        )

        print(f"\n{'Ausgabe ID':<15} {'Times Fetched':<15} {'Result'}")
        print("-" * 60)
        for ausgabe_id, count in sorted_ids:
            status = (
                "Kept in MongoDB"
                if ausgabe_id in mongodb_ausgabe_ids
                else "Filtered out"
            )
            print(f"{ausgabe_id:<15} {count:<15} {status}")

        # Group ausgabe IDs by range to identify patterns
        print("\n📊 Ausgabe ID ranges with duplicates:")
        print(
            f"   2920-2959: {sum(1 for aid in DUPLICATE_AUSGABE_IDS_WITH_COUNTS if 2920 <= int(aid) <= 2959)} IDs"
        )
        print(
            f"   4876-4894: {sum(1 for aid in DUPLICATE_AUSGABE_IDS_WITH_COUNTS if 4876 <= int(aid) <= 4894)} IDs"
        )

        # Estimate dates based on ausgabe ID ranges (rough approximation)
        print(
            "\n📅 Estimated date ranges for duplicates (based on ausgabe ID patterns):"
        )
        print("   Ausgabe 2920-2959 likely corresponds to: 2018 editions")
        print("   Ausgabe 4876-4894 likely corresponds to: 2019-2020 editions")
        print(
            "\n⚠️  These are estimates. The exact publication dates cannot be determined"
        )
        print(
            "   without the detailed terminal output or by re-running the collection with"
        )
        print("   verbose logging that captures publication_date for each request.")

    finally:
        await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
