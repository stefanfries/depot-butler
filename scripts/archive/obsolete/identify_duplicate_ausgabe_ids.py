"""Identify duplicate ausgabe IDs from httpx logs and map to publication dates."""

import re
from collections import Counter
from pathlib import Path


def extract_ausgabe_ids(log_path: Path) -> list[str]:
    """Extract ausgabe IDs from httpx request logs."""
    # Pattern: /ausgabe/XXXX/details
    pattern = re.compile(r"/ausgabe/(\d+)/details")

    ausgabe_ids = []

    with open(log_path, encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                ausgabe_id = match.group(1)
                ausgabe_ids.append(ausgabe_id)

    return ausgabe_ids


def main():
    log_path = Path("data/tmp/historical_pdf_collection.log")

    if not log_path.exists():
        print(f"❌ Log file not found: {log_path}")
        return

    print("Analyzing httpx logs for duplicate ausgabe requests...\n")
    print("=" * 80)

    # Extract all ausgabe IDs that were fetched
    ausgabe_ids = extract_ausgabe_ids(log_path)

    if not ausgabe_ids:
        print("❌ No ausgabe IDs found in log file")
        return

    print(f"Total ausgabe detail requests: {len(ausgabe_ids)}")

    # Count occurrences
    ausgabe_counter = Counter(ausgabe_ids)

    # Find ausgabe IDs that were fetched more than once
    duplicates = {aid: count for aid, count in ausgabe_counter.items() if count > 1}

    if not duplicates:
        print("✓ No duplicate ausgabe requests found")
        return

    # Sort by ausgabe ID (as integer)
    sorted_duplicates = sorted(duplicates.items(), key=lambda x: int(x[0]))

    print(f"Unique ausgabe IDs: {len(ausgabe_counter)}")
    print(f"Ausgabe IDs fetched multiple times: {len(sorted_duplicates)}\n")
    print("=" * 80)
    print(f"{'Ausgabe ID':<15} {'Times Fetched':<15} {'Extra Requests'}")
    print("-" * 80)

    total_extra = 0
    for ausgabe_id, count in sorted_duplicates:
        extra = count - 1
        total_extra += extra
        print(f"{ausgabe_id:<15} {count:<15} +{extra}")

    print("=" * 80)
    print("\n📊 Summary:")
    print(f"   Total requests: {len(ausgabe_ids)}")
    print(f"   Unique ausgabe IDs: {len(ausgabe_counter)}")
    print(f"   Ausgabe IDs with duplicates: {len(sorted_duplicates)}")
    print(f"   Total duplicate requests: {total_extra}")
    print("\n💡 Interpretation:")
    print("   Each ausgabe ID corresponds to one edition (publication date).")
    print(f"   These {len(sorted_duplicates)} ausgabe IDs were fetched multiple times,")
    print(
        f"   resulting in {total_extra} duplicate edition entries that MongoDB deduplicated."
    )

    # Save to file
    output_path = Path("data/tmp/duplicate_ausgabe_ids.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("AUSGABE IDS WITH DUPLICATE FETCH REQUESTS\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total ausgabe IDs with duplicates: {len(sorted_duplicates)}\n")
        f.write(f"Total duplicate requests: {total_extra}\n\n")
        f.write("List of ausgabe IDs:\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'Ausgabe ID':<15} {'Times Fetched':<15} {'Extra Requests'}\n")
        f.write("-" * 80 + "\n")
        for ausgabe_id, count in sorted_duplicates:
            extra = count - 1
            f.write(f"{ausgabe_id:<15} {count:<15} +{extra}\n")
        f.write("\n" + "=" * 80 + "\n")
        f.write("\nNote: Each ausgabe ID maps to a publication date.\n")
        f.write("MongoDB deduplicated these using edition_key (date_publication_id).\n")

    print(f"\n✅ Full list saved to: {output_path}")
    print("\n⚠️  Note: To see the actual publication DATES (not ausgabe IDs),")
    print("   cross-reference these ausgabe IDs with MongoDB's download_url field.")


if __name__ == "__main__":
    main()
