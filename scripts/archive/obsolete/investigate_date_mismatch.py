"""Check for the specific issue #18/2019 and investigate date mismatches."""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    try:
        # Find issue #18/2019
        print("=" * 100)
        print("INVESTIGATING DATE MISMATCH - Issue #18/2019")
        print("=" * 100)
        print()

        editions_2019 = (
            await mongodb.db["processed_editions"]
            .find(
                {
                    "publication_id": "megatrend-folger",
                    "source": "web_historical",
                    "publication_date": {"$regex": "^2019"},
                },
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

        print(f"Found {len(editions_2019)} editions from 2019 in MongoDB\n")

        # Look for issue 18
        issue_18 = [e for e in editions_2019 if "18/2019" in e["title"]]

        if issue_18:
            print("Found issue #18/2019 in MongoDB:")
            for ed in issue_18:
                print(f"  Title: {ed['title']}")
                print(f"  Website date: {ed['publication_date']}")
                print(f"  Edition key: {ed['edition_key']}")
                print(f"  Download URL: {ed['download_url']}")
                print()
                print("  ⚠️  User reports PDF header shows: 2. Mai 2019 (2019-05-02)")
                print(
                    f"  ⚠️  Discrepancy: {ed['publication_date']} (website) vs 2019-05-02 (PDF)"
                )
        else:
            print("❌ Issue #18/2019 NOT found in MongoDB!")
            print("   This might be one of the 'missing' issues we identified earlier.")

        print("\n" + "=" * 100)
        print("CHECKING FOR POTENTIAL DATE ISSUES")
        print("=" * 100)
        print()

        # Check if there are dates around April 25 and May 2
        april_range = [
            e
            for e in editions_2019
            if e["publication_date"] >= "2019-04-20"
            and e["publication_date"] <= "2019-04-30"
        ]
        may_range = [
            e
            for e in editions_2019
            if e["publication_date"] >= "2019-05-01"
            and e["publication_date"] <= "2019-05-10"
        ]

        print("Editions in late April 2019:")
        for ed in april_range:
            print(f"  {ed['publication_date']} - {ed['title']}")

        print("\nEditions in early May 2019:")
        for ed in may_range:
            print(f"  {ed['publication_date']} - {ed['title']}")

        print("\n" + "=" * 100)
        print("IMPLICATIONS OF DATE MISMATCH")
        print("=" * 100)
        print()
        print("🚨 CRITICAL PROBLEM:")
        print("   If the website dates don't match PDF dates, then:")
        print()
        print("   1. Edition keys are WRONG (based on incorrect dates)")
        print("   2. Deduplication may have kept/discarded wrong editions")
        print("   3. Some 'missing' issues might actually be present with wrong dates")
        print("   4. Azure Blob Storage files have incorrect date-based paths")
        print("   5. OneDrive sync will fail to match correctly")
        print()
        print("📋 RECOMMENDED ACTIONS:")
        print()
        print("   Option 1: Trust the PDF dates (most reliable source)")
        print("   - Extract publication dates from PDF headers")
        print("   - Regenerate edition_keys based on PDF dates")
        print("   - Rerun the collection with corrected dates")
        print()
        print("   Option 2: Manual verification")
        print("   - Check a sample of PDFs to see how widespread this issue is")
        print("   - Create a mapping table of website_date -> pdf_date")
        print("   - Apply corrections to MongoDB")
        print()
        print("   Option 3: Use issue numbers + year as the key")
        print("   - Change edition_key format to: {issue_num}_{year}_{publication_id}")
        print("   - This is more reliable than dates")
        print("   - Example: 18_2019_megatrend-folger")
        print()
        print("=" * 100)
        print("NEXT STEPS")
        print("=" * 100)
        print()
        print("1. Check how many PDFs you have locally to verify this issue")
        print("2. Decide on the correct approach (PDF dates vs issue numbers)")
        print(
            "3. Consider if we should halt Step 2 (OneDrive import) until this is resolved"
        )
        print("4. We may need to rebuild the MongoDB data with correct dates")

    finally:
        await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
