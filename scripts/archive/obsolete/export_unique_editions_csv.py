"""Export unique editions to CSV for cross-checking with OneDrive files."""

import asyncio
import csv
from pathlib import Path

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    try:
        # Get all megatrend-folger editions
        editions = (
            await mongodb.db["processed_editions"]
            .find(
                {"publication_id": "megatrend-folger", "source": "web_historical"},
                {
                    "publication_date": 1,
                    "title": 1,
                    "blob_path": 1,
                    "blob_url": 1,
                    "file_size_bytes": 1,
                    "_id": 0,
                },
            )
            .sort("publication_date", 1)
            .to_list(None)
        )

        # Write to CSV
        output_file = Path("data/tmp/unique_editions_396.csv")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Publication Date",
                    "Title",
                    "File Name",
                    "Year",
                    "File Size (KB)",
                    "Blob URL",
                ]
            )

            for edition in editions:
                date = edition["publication_date"]
                title = edition["title"]
                blob_path = edition.get("blob_path", "")
                filename = blob_path.split("/")[-1] if blob_path else "N/A"
                year = date[:4]
                size_kb = round(edition.get("file_size_bytes", 0) / 1024, 1)
                blob_url = edition.get("blob_url", "")

                writer.writerow([date, title, filename, year, size_kb, blob_url])

        print(f"Exported {len(editions)} unique editions to: {output_file}")
        print("\nSummary:")
        print("  Total discovered from website: 475")
        print("  Unique editions (after deduplication): 396")
        print("  Duplicates removed: 79")
        print("\nYou can open this CSV file to cross-check with your OneDrive files.")
        print(
            "Look for files with the same publication_date to identify the duplicates."
        )

    finally:
        await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
