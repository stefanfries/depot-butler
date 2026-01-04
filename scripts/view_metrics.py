"""
View workflow metrics and errors from MongoDB.

Usage:
    uv run python scripts/view_metrics.py --last 10
    uv run python scripts/view_metrics.py --hours 24
    uv run python scripts/view_metrics.py --errors-only
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from depotbutler.db.mongodb import close_mongodb_connection, get_mongodb_service


async def view_recent_runs(limit: int = 10) -> None:
    """Display most recent workflow runs with metrics."""
    mongodb = await get_mongodb_service()
    if not mongodb:
        print("❌ Failed to connect to MongoDB")
        return

    print(f"📊 Last {limit} Workflow Runs\n")
    print("=" * 100)

    cursor = mongodb.db["workflow_metrics"].find().sort("timestamp", -1).limit(limit)

    async for metrics in cursor:
        duration = metrics.get("duration_seconds", 0)
        editions = metrics.get("editions_processed", 0)
        errors = metrics.get("errors_count", 0)
        run_id = metrics.get("run_id", "unknown")
        timestamp = metrics.get("timestamp")

        # Format timestamp
        if isinstance(timestamp, datetime):
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "Unknown"

        # Status emoji
        status = "✅" if errors == 0 else "❌"

        print(f"\n{status} Run ID: {run_id}")
        print(f"   Time: {time_str}")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Editions: {editions}")
        print(f"   Errors: {errors}")

        # Show operation breakdown
        operations = metrics.get("operations", {})
        if operations:
            print("   Operations:")
            for op_name, op_duration in operations.items():
                print(f"     - {op_name}: {op_duration:.2f}s")

    print("\n" + "=" * 100)

    await close_mongodb_connection()


async def view_recent_errors(hours: int = 24) -> None:
    """Display errors from recent workflow runs."""
    mongodb = await get_mongodb_service()
    if not mongodb:
        print("❌ Failed to connect to MongoDB")
        return

    since = datetime.now(UTC) - timedelta(hours=hours)

    print(f"🚨 Errors from Last {hours} Hours\n")
    print("=" * 100)

    cursor = (
        mongodb.db["workflow_errors"]
        .find({"timestamp": {"$gte": since}})
        .sort("timestamp", -1)
    )

    error_count = 0
    async for error in cursor:
        error_count += 1
        run_id = error.get("run_id", "unknown")
        error_type = error.get("error_type", "Unknown")
        error_message = error.get("error_message", "No message")
        operation = error.get("operation", "unknown")
        timestamp = error.get("timestamp")
        publication = error.get("publication_id", "N/A")

        # Format timestamp
        if isinstance(timestamp, datetime):
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "Unknown"

        print(f"\n❌ Error #{error_count}")
        print(f"   Time: {time_str}")
        print(f"   Run ID: {run_id}")
        print(f"   Type: {error_type}")
        print(f"   Operation: {operation}")
        print(f"   Publication: {publication}")
        print(f"   Message: {error_message}")

        context = error.get("context", {})
        if context:
            print(f"   Context: {context}")

    if error_count == 0:
        print("\n✅ No errors found")
    else:
        print(f"\n\nTotal errors: {error_count}")

    print("=" * 100)

    await close_mongodb_connection()


async def view_statistics(days: int = 7) -> None:
    """Display workflow statistics."""
    mongodb = await get_mongodb_service()
    if not mongodb:
        print("❌ Failed to connect to MongoDB")
        return

    since = datetime.now(UTC) - timedelta(days=days)

    print(f"📈 Workflow Statistics (Last {days} Days)\n")
    print("=" * 100)

    # Get all metrics since date
    cursor = mongodb.db["workflow_metrics"].find({"timestamp": {"$gte": since}})

    total_runs = 0
    total_duration = 0.0
    total_editions = 0
    total_errors = 0
    durations = []

    async for metrics in cursor:
        total_runs += 1
        duration = metrics.get("duration_seconds", 0)
        total_duration += duration
        durations.append(duration)
        total_editions += metrics.get("editions_processed", 0)
        total_errors += metrics.get("errors_count", 0)

    if total_runs == 0:
        print("\n⚠️  No workflow runs found in this period")
    else:
        avg_duration = total_duration / total_runs
        min_duration = min(durations)
        max_duration = max(durations)
        avg_editions = total_editions / total_runs if total_runs > 0 else 0

        print(f"\nTotal Runs: {total_runs}")
        print(f"Total Editions Processed: {total_editions}")
        print(f"Average Editions per Run: {avg_editions:.1f}")
        print("\nDuration Statistics:")
        print(f"  Average: {avg_duration:.2f}s")
        print(f"  Minimum: {min_duration:.2f}s")
        print(f"  Maximum: {max_duration:.2f}s")
        print(f"\nError Count: {total_errors}")
        print(f"Success Rate: {((total_runs - total_errors) / total_runs * 100):.1f}%")

    print("=" * 100)

    await close_mongodb_connection()


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="View DepotButler workflow metrics")
    parser.add_argument(
        "--last",
        type=int,
        default=10,
        help="Show last N workflow runs (default: 10)",
    )
    parser.add_argument(
        "--errors-only",
        action="store_true",
        help="Show only errors from recent runs",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Show errors from last N hours (default: 24)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show workflow statistics",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Calculate statistics for last N days (default: 7)",
    )

    args = parser.parse_args()

    if args.stats:
        await view_statistics(args.days)
    elif args.errors_only:
        await view_recent_errors(args.hours)
    else:
        await view_recent_runs(args.last)


if __name__ == "__main__":
    asyncio.run(main())
