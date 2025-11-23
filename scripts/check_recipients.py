"""Quick script to check recipient statistics in MongoDB."""

import asyncio

from depotbutler.db.mongodb import get_mongodb_service


async def check():
    service = await get_mongodb_service()
    recipients = (
        await service.db.recipients.find(
            {},
            {"email": 1, "first_name": 1, "last_sent_at": 1, "send_count": 1, "_id": 0},
        )
        .sort("email", 1)
        .to_list(None)
    )

    print("\nRecipient Statistics:")
    print("=" * 90)
    print(f"{'Email':<40} | {'First Name':<15} | {'Count':>5} | Last Sent")
    print("-" * 90)

    for r in recipients:
        last_sent = str(r["last_sent_at"])[:19] if r["last_sent_at"] else "Never"
        print(
            f"{r['email']:<40} | {r['first_name']:<15} | {r['send_count']:>5} | {last_sent}"
        )

    print("=" * 90)
    await service.close()


if __name__ == "__main__":
    asyncio.run(check())
