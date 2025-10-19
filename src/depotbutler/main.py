from depotbutler.settings import Settings

settings = Settings()


def main():
    print("DepotButler starting...")
    print("Loaded configuration:")
    print(f"Megatrend Auth URL: {settings.megatrend.auth_url}")
    print(f"OneDrive Base Folder: {settings.onedrive.basefolder}")
    print(f"Mail Recipients: {settings.mail.recipients}")
