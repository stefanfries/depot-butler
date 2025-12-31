import asyncio
import re
from collections import defaultdict

from depotbutler.db.mongodb import get_mongodb_service


async def analyze_megatrend():
    db = await get_mongodb_service()

    # Get all Megatrend editions
    editions = (
        await db.db["processed_editions"]
        .find({"publication_id": "megatrend-folger"})
        .sort("publication_date", 1)
        .to_list(None)
    )

    print(f"Total Megatrend Folger editions: {len(editions)}\n")

    # Group by year
    by_year = defaultdict(list)
    for edition in editions:
        # Extract year from edition key
        match = re.match(r"(\d{4})_", edition["edition_key"])
        if match:
            year = match.group(1)
            by_year[year].append(edition)

    print("Megatrend Folger by year:")
    for year in sorted(by_year.keys()):
        editions_in_year = by_year[year]
        issue_numbers = []
        for ed in editions_in_year:
            match = re.match(r"\d{4}_(\d+)_", ed["edition_key"])
            if match:
                issue_numbers.append(int(match.group(1)))
        issue_numbers.sort()
        print(
            f"  {year}: {len(editions_in_year)} issues - {issue_numbers[:10]}{'...' if len(issue_numbers) > 10 else ''}"
        )


asyncio.run(analyze_megatrend())
