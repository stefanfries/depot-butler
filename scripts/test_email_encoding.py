"""Test script to verify UTF-8 encoding in emails with emojis."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from depotbutler.mailer.composers import (
    create_error_notification_message,
    create_success_notification_message,
)
from depotbutler.models import Edition


def test_charset_encoding() -> bool:
    """Test that emails with emojis have proper UTF-8 charset."""

    # Create test edition with emojis
    edition = Edition(
        title="DER AKTIONÄR 09/26",
        publication_date="2026-02-18",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
    )

    # Create HTML summary with emojis (like daily report)
    html_summary = """<h2>📊 DepotButler Daily Report</h2>
<p>Processed: 2 publication(s)<br>
✅ Success: 1 | ℹ️ Skipped: 1 | ❌ Failed: 0</p>
<div style='margin: 10px 0; padding: 10px; background: #f0fff0; border-left: 4px solid #00cc00;'>
<strong>DER AKTIONÄR 09/26</strong><br>
📧 Email: ⏭️ Disabled<br>
📎 Uploaded to OneDrive<br>
☁️ Archival: ✅ Archived
</div>"""

    # Test 1: Success notification (Daily Report style)
    print("Testing Daily Report email with emojis...")
    msg = create_success_notification_message(
        edition=edition,
        onedrive_url=html_summary,
        recipient="test@example.com",
        firstname="Stefan",
        sender_email="depot-butler@example.com",
    )

    # Check charset in both parts
    for part in msg.walk():
        if part.get_content_type() in ["text/plain", "text/html"]:
            charset = part.get_content_charset()
            content_type = part.get_content_type()
            print(f"  ✓ {content_type}: charset={charset}")

            if charset != "utf-8":
                print(f"    ❌ ERROR: Expected utf-8, got {charset}")
                return False

    # Test 2: Error notification with emoji in subject
    print("\nTesting error notification email with emojis...")
    error_msg = create_error_notification_message(
        error_msg="Test error ❌",
        edition_title="Test ✅",
        recipient="test@example.com",
        firstname="Stefan",
        sender_email="depot-butler@example.com",
    )

    for part in error_msg.walk():
        if part.get_content_type() in ["text/plain", "text/html"]:
            charset = part.get_content_charset()
            content_type = part.get_content_type()
            print(f"  ✓ {content_type}: charset={charset}")

            if charset != "utf-8":
                print(f"    ❌ ERROR: Expected utf-8, got {charset}")
                return False

    print("\n✅ All email parts have UTF-8 charset encoding!")
    print("📱 Emails should now render correctly on iPhone Mail app.")
    return True


if __name__ == "__main__":
    success = test_charset_encoding()
    sys.exit(0 if success else 1)
