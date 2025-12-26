"""
Test yfinance with German warrants and stocks.

This script validates that we can:
1. Import and use yfinance
2. Fetch data for German stocks (DAX components)
3. Try fetching warrant data (if available)
4. Identify if WKN->ISIN->ticker mapping is needed

Run: uv run python scripts/validation/test_yfinance.py

Note: This is for Phase 2 (intraday prices), can be deferred.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import yfinance as yf

from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


def test_german_stock(ticker: str, name: str):
    """Test fetching data for a German stock."""
    logger.info(f"\nTesting: {name} ({ticker})")

    try:
        stock = yf.Ticker(ticker)

        # Get basic info
        info = stock.info
        logger.info(f"  Name: {info.get('longName', 'N/A')}")
        logger.info(f"  Currency: {info.get('currency', 'N/A')}")
        logger.info(f"  Exchange: {info.get('exchange', 'N/A')}")

        # Get recent price
        hist = stock.history(period="1d")
        if not hist.empty:
            latest_close = hist["Close"].iloc[-1]
            logger.info(f"  Latest close: {latest_close:.2f}")
            logger.info(f"✅ Successfully fetched data for {ticker}")
            return True
        else:
            logger.warning(f"⚠️ No price data available for {ticker}")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to fetch {ticker}: {e}")
        return False


def test_warrant_by_wkn(wkn: str):
    """Attempt to fetch warrant data by WKN."""
    logger.info(f"\nTesting warrant by WKN: {wkn}")

    # Try direct WKN lookup (unlikely to work)
    try:
        ticker = yf.Ticker(wkn)
        info = ticker.info

        if info.get("regularMarketPrice"):
            logger.info(f"✅ Found data for WKN {wkn} directly!")
            logger.info(f"  Name: {info.get('longName', 'N/A')}")
            return True
        else:
            logger.info(f"⚠️ WKN {wkn} not recognized by yfinance")
            return False

    except Exception as e:
        logger.info(f"⚠️ Direct WKN lookup failed: {e}")
        return False


def test_warrant_by_isin(isin: str):
    """Attempt to fetch warrant data by ISIN."""
    logger.info(f"\nTesting warrant by ISIN: {isin}")

    # Try ISIN with common exchanges
    exchanges = ["", ".F", ".DE", ".XETRA"]

    for exchange in exchanges:
        ticker_symbol = f"{isin}{exchange}"
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info

            if info.get("regularMarketPrice"):
                logger.info(f"✅ Found data for {ticker_symbol}!")
                logger.info(f"  Name: {info.get('longName', 'N/A')}")
                logger.info(f"  Price: {info.get('regularMarketPrice')}")
                return True

        except Exception:
            continue

    logger.info(f"⚠️ ISIN {isin} not found in any exchange")
    return False


def main():
    """Run yfinance validation."""
    logger.info("=" * 60)
    logger.info("YFINANCE VALIDATION")
    logger.info("=" * 60)

    # Test 1: German blue-chip stocks (should work reliably)
    logger.info("\n1. Testing German stocks (DAX components):")

    test_stocks = [
        ("SAP.DE", "SAP SE"),
        ("SIE.DE", "Siemens AG"),
        ("BMW.DE", "BMW AG"),
    ]

    stock_success = 0
    for ticker, name in test_stocks:
        if test_german_stock(ticker, name):
            stock_success += 1

    logger.info(f"\nStocks tested: {stock_success}/{len(test_stocks)} successful")

    # Test 2: Warrants (likely to fail - educational test)
    logger.info("\n2. Testing warrants (experimental):")
    logger.info("Note: Most warrants are NOT available on yfinance")
    logger.info("This test explores what's possible.\n")

    # Real WKNs from Megatrend-Folger warrants
    test_warrant_wkns = [
        "MJ85T6",
        "JU5YHH",
        "MK210Y",
        "MK2EWJ",
        "MG7BYX",
        "JF339D",
        "MG7LPY",
        "HS4P7G",
        "JH63HB",
        "JT2GHE",
        "JH4WD6",
        "HS765P",
        "MK3LNW",
        "MK74CT",
        "JU3YAP",
        "HT5D3H",
        "MM2DRR",
        "MK9CUG",
        "MK51LR",
        "JK9Z20",
        "MG9VYR",
        "JK9V0Y",
        "JH8UPZ",
        "JH5VLN",
    ]

    # Test a sample of warrants (first 5 to avoid excessive requests)
    warrant_success = 0
    total_tested = 0

    for wkn in test_warrant_wkns[:5]:  # Test first 5
        total_tested += 1
        if test_warrant_by_wkn(wkn):
            warrant_success += 1

    logger.info(f"\nWarrants tested: {total_tested}, successful: {warrant_success}")

    # Summary
    logger.info("=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 60)

    if stock_success > 0:
        logger.info("✅ yfinance works for German stocks")
    else:
        logger.warning("⚠️ Issues with yfinance for German stocks")

    if warrant_success == 0:
        logger.info("⚠️ Warrants not available on yfinance (EXPECTED)")
        logger.info("\nAlternatives for warrant prices:")
        logger.info("1. Use underlying stock price as proxy")
        logger.info("2. Use paid APIs (e.g., Börse Frankfurt API)")
        logger.info("3. Scrape warrant issuer websites")
        logger.info("4. Focus on portfolio performance vs. individual prices")

    logger.info("\n📝 Recommendation:")
    logger.info("- Phase 2 can start with underlying stock prices")
    logger.info("- Add warrant-specific prices later if needed")
    logger.info("- Historical performance analysis doesn't require live prices")


if __name__ == "__main__":
    main()
