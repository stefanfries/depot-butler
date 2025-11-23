"""Check SMTP configuration and test connection."""

import asyncio
import smtplib

from depotbutler.settings import Settings


async def test_smtp():
    settings = Settings()
    mail = settings.mail

    print("\nSMTP Configuration:")
    print("=" * 60)
    print(f"Server: {mail.server}")
    print(f"Port: {mail.port}")
    print(f"Username: {mail.username}")
    print(f"Password: {'*' * len(mail.password.get_secret_value())}")
    print(f"Admin Address: {mail.admin_address}")
    print("=" * 60)

    print("\nTesting SMTP connection...")
    try:
        with smtplib.SMTP(mail.server, mail.port, timeout=10) as server:
            print("✓ Connected to SMTP server")
            server.starttls()
            print("✓ TLS encryption enabled")
            server.login(mail.username, mail.password.get_secret_value())
            print("✓ Authentication successful")
            print("\n✅ SMTP configuration is working correctly!")
    except smtplib.SMTPAuthenticationError as e:
        print(f"\n❌ Authentication failed: {e}")
    except smtplib.SMTPException as e:
        print(f"\n❌ SMTP error: {e}")
    except Exception as e:
        print(f"\n❌ Connection error: {e}")


if __name__ == "__main__":
    asyncio.run(test_smtp())
