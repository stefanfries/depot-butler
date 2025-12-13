"""Inspect subscription details including Laufzeit (duration)."""

import asyncio
from depotbutler.httpx_client import HttpxBoersenmedienClient
from bs4 import BeautifulSoup


async def inspect_subscription_details():
    """Check what information is available on subscriptions page."""
    client = HttpxBoersenmedienClient()
    await client.login()

    subscriptions_url = f"{client.base_url}/produkte/abonnements"
    
    if not client.client:
        print("Client not initialized")
        return
        
    response = await client.client.get(subscriptions_url)
    soup = BeautifulSoup(response.text, "html.parser")
    
    subscription_items = soup.find_all("div", class_="subscription-item")
    
    print(f"Found {len(subscription_items)} subscriptions\n")
    print("=" * 80)
    
    for idx, item in enumerate(subscription_items, 1):
        print(f"\n### SUBSCRIPTION {idx} ###\n")
        
        # Basic info
        sub_id = item.get("data-subscription-id", "")
        sub_number = item.get("data-subscription-number", "")
        
        h2 = item.find("h2")
        name = h2.get_text(strip=True) if h2 else "Unknown"
        name = name.replace("Aktiv", "").replace("Inaktiv", "").strip()
        
        print(f"Name: {name}")
        print(f"ID: {sub_id}")
        print(f"Number: {sub_number}")
        
        # Look for Laufzeit or other metadata
        print("\n--- All text content in item: ---")
        all_text = item.get_text("\n", strip=True)
        print(all_text)
        
        print("\n--- HTML structure: ---")
        print(item.prettify()[:1000])  # First 1000 chars
        
        print("\n" + "=" * 80)
    
    await client.close()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, 'src')
    asyncio.run(inspect_subscription_details())
