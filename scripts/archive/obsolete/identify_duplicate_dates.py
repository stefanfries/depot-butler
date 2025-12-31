"""Identify publication dates with duplicate entries from the collection log."""

import re
from collections import Counter
from pathlib import Path


def extract_edition_keys_from_log(log_path: Path) -> list[tuple[str, str]]:
    """Extract edition_key and title from repository log entries."""
    # Pattern: "Marked edition as processed [key=YYYY-MM-DD_megatrend-folger, ..."
    pattern = re.compile(
        r"Marked edition as processed \[key=([0-9-]+_megatrend-folger)"
    )

    edition_keys = []

    with open(log_path, encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                edition_key = match.group(1)
                # Extract date from edition_key (format: YYYY-MM-DD_megatrend-folger)
                date = edition_key.split("_")[0]
                edition_keys.append((date, edition_key))

    return edition_keys


def main():
    log_path = Path("data/tmp/historical_pdf_collection.log")

    if not log_path.exists():
        print(f"❌ Log file not found: {log_path}")
        return

    print("Analyzing collection log for duplicate publication dates...\n")
    print("=" * 80)

    # Extract all edition keys that were processed
    edition_keys = extract_edition_keys_from_log(log_path)

    if not edition_keys:
        print("❌ No edition keys found in log file")
        return

    print(f"Total processing attempts found in log: {len(edition_keys)}")

    # Count occurrences of each date
    dates = [date for date, _ in edition_keys]
    date_counter = Counter(dates)

    # Find dates that appear more than once (duplicates)
    duplicates = {date: count for date, count in date_counter.items() if count > 1}

    if not duplicates:
        print("✓ No duplicate dates found in processing log")
        return

    # Sort by date
    sorted_duplicates = sorted(duplicates.items())

    print(f"Found {len(sorted_duplicates)} dates with duplicate processing attempts\n")
    print("=" * 80)
    print(f"{'Publication Date':<20} {'Attempts':<10} {'Note'}")
    print("-" * 80)

    total_extra = 0
    for date, count in sorted_duplicates:
        extra = count - 1
        total_extra += extra
        print(f"{date:<20} {count:<10} (+{extra} duplicate{'s' if extra > 1 else ''})")

    print("=" * 80)
    print("\n📊 Summary:")
    print(f"   Unique dates: {len(date_counter)}")
    print(f"   Dates with duplicates: {len(sorted_duplicates)}")
    print(f"   Total duplicate attempts: {total_extra}")
    print(f"   Total processing attempts: {len(edition_keys)}")
    print(f"   Expected in MongoDB: {len(date_counter)} (one per unique date)")

    # Save to file
    output_path = Path("data/tmp/duplicate_dates_list.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("PUBLICATION DATES WITH DUPLICATE ENTRIES\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total dates with duplicates: {len(sorted_duplicates)}\n")
        f.write(f"Total duplicate attempts: {total_extra}\n\n")
        f.write("List of dates:\n")
        f.write("-" * 80 + "\n")
        for date, count in sorted_duplicates:
            extra = count - 1
            f.write(f"{date}  (attempted {count} times, +{extra} duplicate)\n")

    print(f"\n✅ Full list saved to: {output_path}")


if __name__ == "__main__":
    main()
