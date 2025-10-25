from typing import List

import httpx
from bs4 import BeautifulSoup

from depotbutler.settings import Settings

from .models import Edition

settings = Settings()


class MegatrendClient:
    def __init__(self):
        self.base_url = settings.megatrend.base_url
        self.login_url = settings.megatrend.login_url
        self.content_url = f"{self.base_url}/produkte/abonnements/{settings.megatrend.abo_id}/{settings.megatrend.abo_nummer}/ausgaben"
        self.username = settings.megatrend.username
        self.password = settings.megatrend.password
        self.client = httpx.AsyncClient(follow_redirects=True)

    async def login(self) -> None:

        # Step 1: Get login page to retrieve cookies + hidden fields
        r = await self.client.get(self.login_url)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        token = soup.find("input", {"name": "__RequestVerificationToken"})
        if not token:
            raise ValueError("Could not find __RequestVerificationToken on login page")
        token = token["value"]

        # Step 2: Build form payload (all required hidden + credentials)
        payload = {
            "__RequestVerificationToken": token,
            "Username": self.username.get_secret_value(),
            "Password": self.password.get_secret_value(),
            "UsePassword": "True",
            "EmailEntered": "False",
            "Kmsi": "True",
            "RedirectUri": "",
            "ApiKey": "",
            "CancelUri": "",
        }

        # Step 3: Submit login form
        response = await self.client.post(self.login_url, data=payload)
        response.raise_for_status()

        # Step 4: Verify login success
        if "logout" in response.text.lower() or "abmelden" in response.text.lower():
            print("✅ Login successful!")
        else:
            print("❌ Login may have failed. Check credentials or token.")
            print(response.url)
            print(response.text[:500])  # print first lines for debugging

    async def get_latest_edition(self) -> Edition:
        """Fetch the list of latest edition infos."""
        response = await self.client.get(self.content_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        article = soup.find("article", class_="list-item universal-list-item")

        return Edition(
            title=article.find("h2").find("a").text.strip(),
            details_url=self.base_url + article.find("header").find("a")["href"],
            download_url=self.base_url + article.find("footer").find("a")["href"],
            publication_date="unknown",
        )

    async def get_publication_date(self, edition: Edition) -> Edition:
        """Get the publication date of the latest edition."""
        response = await self.client.get(edition.details_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        publication_date = soup.find("time")["datetime"]
        if not publication_date:
            edition.publication_date = "unknown"
        edition.publication_date = str(publication_date)
        return edition

    async def download_edition(
        self, edition: Edition, dest_path: str
    ) -> httpx.Response:
        """Download the PDF file."""
        response = await self.client.get(edition.download_url)
        response.raise_for_status()

        with open(dest_path, "wb") as f:
            f.write(response.content)
        print(f"✅ PDF downloaded to {dest_path}")
        return response

    async def close(self):
        await self.client.aclose()
