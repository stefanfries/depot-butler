"""Extract download URLs for the ausgabe IDs that had duplicates."""

import asyncio
import re

from depotbutler.db.mongodb import get_mongodb_service

# Ausgabe IDs that were fetched multiple times (from log analysis)
DUPLICATE_AUSGABE_IDS = {
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
}


async def main():
    mongodb = await get_mongodb_service()

    try:
        # Get all editions with download_url
        editions = (
            await mongodb.db["processed_editions"]
            .find(
                {"publication_id": "megatrend-folger", "source": "web_historical"},
                {
                    "publication_date": 1,
                    "title": 1,
                    "download_url": 1,
                    "edition_key": 1,
                    "_id": 0,
                },
            )
            .sort("publication_date", 1)
            .to_list(None)
        )

        print("=" * 120)
        print("EDITIONS WITH DUPLICATE AUSGABE IDs")
        print("=" * 120)
        print(
            f"\nSearching {len(editions)} MongoDB editions for ausgabe IDs that had duplicates...\n"
        )

        # Extract ausgabe ID from download_url
        # Pattern could be /ausgabe/XXXX/ or /content/XXXX or similar
        pattern = re.compile(r"/(?:ausgabe|content)/(\d+)")

        matches = []
        for edition in editions:
            url = edition.get("download_url", "")
            match = pattern.search(url)
            if match:
                ausgabe_id = match.group(1)
                if ausgabe_id in DUPLICATE_AUSGABE_IDS:
                    matches.append(
                        {
                            "ausgabe_id": ausgabe_id,
                            "publication_date": edition["publication_date"],
                            "title": edition["title"],
                            "download_url": url,
                            "edition_key": edition["edition_key"],
                        }
                    )

        if not matches:
            print("No matches found. Let's check the download_url format:")
            for edition in editions[:5]:
                print(f"  Sample URL: {edition.get('download_url', 'N/A')}")
            return

        # Sort by publication date
        matches.sort(key=lambda x: x["publication_date"])

        print(
            f"Found {len(matches)} editions in MongoDB that correspond to ausgabe IDs with duplicates:"
        )
        print()
        print(f"{'Date':<15} {'Ausgabe ID':<12} {'Title':<45} {'Edition Key'}")
        print("-" * 120)

        for match in matches:
            print(
                f"{match['publication_date']:<15} {match['ausgabe_id']:<12} {match['title'][:43]:<45} {match['edition_key']}"
            )

        print()
        print("=" * 120)
        print("DOWNLOAD URLs:")
        print("=" * 120)
        print()

        for match in matches:
            print(f"Date: {match['publication_date']}")
            print(f"Ausgabe: {match['ausgabe_id']}")
            print(f"URL: {match['download_url']}")
            print()

        print("=" * 120)
        print("\nSUMMARY:")
        print(f"  Total duplicate ausgabe IDs from log: {len(DUPLICATE_AUSGABE_IDS)}")
        print(f"  Found in MongoDB: {len(matches)}")
        print(
            f"  Not found (were filtered out): {len(DUPLICATE_AUSGABE_IDS) - len(matches)}"
        )
        print()
        print("CONCLUSION:")
        print(
            f"  These {len(matches)} publication dates had duplicate entries on the website."
        )
        print("  MongoDB kept one entry per date and filtered out the duplicates.")
        print(
            "  The ausgabe IDs not found were the duplicates that didn't make it into MongoDB."
        )

        # Save to file
        with open(
            "data/tmp/duplicate_editions_with_urls.txt", "w", encoding="utf-8"
        ) as f:
            f.write("PUBLICATION DATES WITH DUPLICATE ENTRIES\n")
            f.write("=" * 120 + "\n\n")
            f.write(
                f"These {len(matches)} dates correspond to ausgabe IDs that were fetched multiple times:\n\n"
            )
            f.write(f"{'Date':<15} {'Ausgabe ID':<12} {'Title':<45} {'Download URL'}\n")
            f.write("-" * 120 + "\n")
            for match in matches:
                f.write(
                    f"{match['publication_date']:<15} {match['ausgabe_id']:<12} {match['title'][:43]:<45} {match['download_url']}\n"
                )
            f.write("\n" + "=" * 120 + "\n")
            f.write("\nJust the publication dates:\n")
            f.write("-" * 50 + "\n")
            for match in matches:
                f.write(f"{match['publication_date']}\n")

        print("\nFull list saved to: data/tmp/duplicate_editions_with_urls.txt")

    finally:
        await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
