"""Check status of specific edition by date."""

import asyncio

from depotbutler.db.mongodb import close_mongodb_connection, get_mongodb_service


async def check_edition_by_date(date_str: str) -> None:
    """Check if edition from specific date was processed."""
    mongodb = await get_mongodb_service()

    print(f"🔍 Checking for editions from {date_str}...\n")

    # Check processed_editions
    editions = await mongodb.db.processed_editions.find(
        {"publication_date": {"$regex": f"^{date_str}"}}
    ).to_list(None)

    print(f"📄 Processed Editions from {date_str}: {len(editions)}")
    for edition in editions:
        edition_key = edition.get("edition_key")
        pub_date = edition.get("publication_date")
        processed_at = edition.get("processed_at")
        downloaded_at = edition.get("downloaded_at")
        source = edition.get("source", "scheduled_job")

        print(f"\n   Edition: {edition_key}")
        print(f"   Publication Date: {pub_date}")
        print(f"   Source: {source}")
        print(f"   Processed at: {processed_at}")
        print(f"   Downloaded at: {downloaded_at}")

    if not editions:
        print(f"   ❌ No editions found for {date_str}")
        print("\n   This could mean:")
        print("   - Edition wasn't available on the website when job ran")
        print("   - Edition was already processed earlier (check with full date+time)")
        print("   - Job failed during processing")

    print("\n" + "=" * 100)
    print("\n🔍 Checking recent workflow runs...")

    # Check recent metrics
    metrics = (
        await mongodb.db.workflow_metrics.find()
        .sort("timestamp", -1)
        .limit(5)
        .to_list(None)
    )

    for m in metrics:
        timestamp = m.get("timestamp")
        editions_processed = m.get("editions_processed", 0)
        run_id = m.get("run_id")
        print(f"   [{run_id}] {timestamp}: {editions_processed} editions processed")

    await close_mongodb_connection()


if __name__ == "__main__":
    import sys

    date_str = sys.argv[1] if len(sys.argv) > 1 else "2025-12-18"
    asyncio.run(check_edition_by_date(date_str))
