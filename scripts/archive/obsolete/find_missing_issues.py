"""Identify missing issue numbers per year from MongoDB."""

import asyncio
import re
from collections import defaultdict

from depotbutler.db.mongodb import get_mongodb_service


async def main():
    mongodb = await get_mongodb_service()

    try:
        # Get all editions
        editions = (
            await mongodb.db["processed_editions"]
            .find(
                {"publication_id": "megatrend-folger", "source": "web_historical"},
                {"publication_date": 1, "title": 1, "_id": 0},
            )
            .sort("publication_date", 1)
            .to_list(None)
        )

        print("=" * 100)
        print("MISSING ISSUE NUMBERS ANALYSIS")
        print("=" * 100)
        print(f"\nAnalyzing {len(editions)} editions from MongoDB...\n")

        # Extract issue numbers by year
        # Title format: "800% Strategie 28/2018" or "Megatrend Folger 51/2025"
        pattern = re.compile(r"(\d+)/(\d{4})")

        issues_by_year = defaultdict(set)

        for edition in editions:
            title = edition["title"]
            match = pattern.search(title)
            if match:
                issue_num = int(match.group(1))
                year = match.group(2)
                issues_by_year[year].add(issue_num)

        # Sort years
        years = sorted(issues_by_year.keys())

        print("Issues found per year:")
        print("-" * 100)
        for year in years:
            issues = sorted(issues_by_year[year])
            print(
                f"{year}: {len(issues)} issues - Range: {min(issues)} to {max(issues)}"
            )

        print("\n" + "=" * 100)
        print("MISSING ISSUES BY YEAR")
        print("=" * 100)
        print()

        total_missing = 0
        all_missing = {}

        for year in years:
            issues = sorted(issues_by_year[year])
            min_issue = min(issues)
            max_issue = max(issues)

            # Find missing issues in the range
            expected = set(range(min_issue, max_issue + 1))
            missing = sorted(expected - issues_by_year[year])

            # Also check if we're missing issues at the end (51-52 range)
            if max_issue < 51:
                # Check if we should expect more issues
                potential_missing_end = list(range(max_issue + 1, 53))
            else:
                potential_missing_end = []

            all_missing[year] = {
                "in_range": missing,
                "after_max": potential_missing_end,
            }

            if missing or potential_missing_end:
                total_missing += len(missing)
                print(f"📅 {year}:")
                print(f"   Found: {len(issues)} issues")
                if missing:
                    print(
                        f"   Missing in range ({min_issue}-{max_issue}): {', '.join(f'{i:02d}' for i in missing)}"
                    )
                    print(f"      Total: {len(missing)} missing")
                else:
                    print(f"   No gaps in range {min_issue}-{max_issue}")

                if potential_missing_end:
                    print(
                        f"   Potentially missing after {max_issue}: {', '.join(f'{i:02d}' for i in potential_missing_end)}"
                    )
                    print("      (These may not exist if year ended early)")
                print()
            else:
                print(
                    f"✓ {year}: Complete range {min_issue:02d}-{max_issue:02d} (no gaps)"
                )
                print()

        print("=" * 100)
        print("SUMMARY")
        print("=" * 100)
        print()

        # Create comprehensive missing list
        all_missing_flat = {}
        for year in years:
            issues = sorted(issues_by_year[year])
            min_issue = min(issues)
            max_issue = max(issues)

            # Check full range 1-52
            expected_full = set(range(1, 53))
            found = issues_by_year[year]
            missing_full = sorted(expected_full - found)

            if missing_full:
                all_missing_flat[year] = missing_full

        # Print comprehensive missing list
        for year in years:
            if year in all_missing_flat:
                missing = all_missing_flat[year]
                print(
                    f"{year}: Missing issues {', '.join(f'{i:02d}' for i in missing)} ({len(missing)} issues)"
                )

        print()
        print(f"Total years analyzed: {len(years)}")
        print(f"Total issues in MongoDB: {len(editions)}")
        print(f"Years with missing issues: {len(all_missing_flat)}")

        # Save to file
        with open("data/tmp/missing_issues_per_year.txt", "w", encoding="utf-8") as f:
            f.write("MISSING ISSUE NUMBERS PER YEAR\n")
            f.write("=" * 100 + "\n\n")
            f.write(
                "These issues are missing from MongoDB (available in your OneDrive):\n\n"
            )

            for year in years:
                if year in all_missing_flat:
                    missing = all_missing_flat[year]
                    issues = sorted(issues_by_year[year])
                    f.write(f"\n{year}:\n")
                    f.write(f"  Found in MongoDB: {len(issues)} issues\n")
                    f.write(f"  Missing: {len(missing)} issues\n")
                    f.write(
                        f"  Missing issue numbers: {', '.join(f'{i:02d}' for i in missing)}\n"
                    )
                else:
                    f.write(f"\n{year}: Complete (no missing issues)\n")

            f.write("\n" + "=" * 100 + "\n")
            f.write("\nFORMATTED FOR COPY-PASTE:\n")
            f.write("-" * 100 + "\n\n")
            for year in years:
                if year in all_missing_flat:
                    missing = all_missing_flat[year]
                    f.write(f"{year}: {', '.join(f'{i:02d}' for i in missing)}\n")

        print("\nFull list saved to: data/tmp/missing_issues_per_year.txt")

    finally:
        await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
