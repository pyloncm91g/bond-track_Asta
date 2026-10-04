import httpx
import re
import json
import logging
from bs4 import BeautifulSoup
from typing import Optional

logger = logging.getLogger(__name__)

async def fetch_price_from_frankfurt(isin: str) -> Optional[float]:
    """Fetch bond price directly from Börse Frankfurt (Deutsche Börse) API by ISIN."""
    if not isin:
        return None
    url = f"https://api.boerse-frankfurt.de/v1/data/quote_box/single?isin={isin.strip().upper()}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.boerse-frankfurt.de",
        "Referer": "https://www.boerse-frankfurt.de/",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                price = data.get("lastPrice") or data.get("open")
                if price and float(price) > 0:
                    logger.info(f"Börse Frankfurt quote found for {isin}: {price}")
                    return float(price)
    except Exception as e:
        logger.debug(f"Frankfurt API lookup error for {isin}: {e}")
    return None

def extract_price_from_json_ld(html: str) -> Optional[float]:
    """Parse Schema.org JSON-LD scripts (FinancialProduct, Product, Offer) used by TradingView and other financial portals."""
    for m in re.finditer(r'<script type="application/ld\+json">([^<]+)</script>', html):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                offers = data.get('offers')
                if isinstance(offers, dict) and 'price' in offers:
                    val = float(offers['price'])
                    if 10.0 <= val <= 300.0:
                        return val
                if isinstance(offers, list) and len(offers) > 0:
                    first = offers[0]
                    if isinstance(first, dict) and 'price' in first:
                        val = float(first['price'])
                        if 10.0 <= val <= 300.0:
                            return val
                if 'price' in data:
                    val = float(data['price'])
                    if 10.0 <= val <= 300.0:
                        return val
        except Exception:
            pass
    return None

async def fetch_price_from_url(url: str) -> Optional[float]:
    """Scrape bond price from a URL (TradingView, Business Insider, Deutsche Börse, or other pages)."""
    if not url or not url.strip():
        return None

    url = url.strip()

    # If it's a Deutsche Börse / Börse Frankfurt page, extract ISIN and use Frankfurt API
    if "boerse-frankfurt" in url or "deutsche-boerse" in url:
        isin_match = re.search(r'\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b', url, re.IGNORECASE)
        if isin_match:
            price = await fetch_price_from_frankfurt(isin_match.group(1).upper())
            if price:
                return price

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"URL returned non-200 status {resp.status_code}: {url}")
                return None
            html = resp.text

            # 1. TradingView & Standard Schema.org JSON-LD FinancialProduct / Offer
            json_ld_price = extract_price_from_json_ld(html)
            if json_ld_price is not None:
                logger.info(f"Price extracted via JSON-LD from {url}: {json_ld_price}")
                return json_ld_price

            # 2. Business Insider current-value element
            m = re.search(r'<span[^>]*class="[^"]*price-section__current-value[^"]*"[^>]*>([\d\.,]+)</span>', html)
            if m:
                val_str = m.group(1).replace(",", "")
                val = float(val_str)
                if 10.0 <= val <= 300.0:
                    logger.info(f"Price extracted via Business Insider from {url}: {val}")
                    return val

            # 3. Meta tags: og:price:amount, twitter:data1, product:price:amount
            m_meta = re.search(r'<meta[^>]+(?:property|name)=["\'](?:twitter:data1|og:price:amount|product:price:amount)["\'][^>]+content=["\']([0-9\.]+)["\']', html, re.I)
            if m_meta:
                val = float(m_meta.group(1))
                if 10.0 <= val <= 300.0:
                    logger.info(f"Price extracted via Meta tag from {url}: {val}")
                    return val

            # 4. Embedded script JSON regex: currentValue, lastPrice, previousClose, last_price, lp
            m2 = re.search(r'"(?:currentValue|lastPrice|previousClose|last_price|lp)"\s*:\s*"?([0-9\.]+)"?', html)
            if m2:
                val = float(m2.group(1))
                if 10.0 <= val <= 300.0:
                    logger.info(f"Price extracted via state JSON regex from {url}: {val}")
                    return val

            # 5. BeautifulSoup fallback: scan elements with price/quote in class
            soup = BeautifulSoup(html, "html.parser")
            for elem in soup.find_all(attrs={"class": re.compile(r'price|quote', re.I)}):
                text = elem.get_text(strip=True).replace(",", "")
                m_num = re.match(r'^\$?(\d{2,3}\.\d{2,4})%?$', text)
                if m_num:
                    val = float(m_num.group(1))
                    if 10.0 <= val <= 300.0:
                        logger.info(f"Price extracted via BeautifulSoup fallback from {url}: {val}")
                        return val

    except Exception as e:
        logger.warning(f"Failed to scrape bond price from {url}: {e}")

    return None

async def fetch_bond_price(isin: Optional[str] = None, url: Optional[str] = None) -> Optional[float]:
    """Fetch bond price with multi-source fallback:
    1. Custom URL Scraping (TradingView, Business Insider, etc.) if provided
    2. Börse Frankfurt API by ISIN
    """
    # 1. Custom URL if specified by user
    if url and url.strip():
        price = await fetch_price_from_url(url.strip())
        if price is not None and price > 0:
            return round(price, 3)

    # 2. Priority / Fallback: Börse Frankfurt by ISIN
    if isin and isin.strip():
        price = await fetch_price_from_frankfurt(isin.strip())
        if price is not None and price > 0:
            return round(price, 3)

    return None


async def lookup_bond_by_isin(isin: str) -> dict:
    """Auto-discover bond details (Name, Live Price, Price Source, Source URL) by ISIN.
    1. Query TradingView Symbol Search API
    2. Fallback to OpenFIGI API for official instrument name
    3. Query Frankfurt API for fallback price
    """
    if not isin or not isin.strip():
        return {}

    isin = isin.strip().upper()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Origin': 'https://www.tradingview.com',
        'Referer': 'https://www.tradingview.com/'
    }

    result = {
        "isin": isin,
        "name": None,
        "latest_price": None,
        "price_source": None,
        "price_source_url": None,
        "lendable_ratio": 0.80,
        "actual_borrow_ratio": 0.50,
        "face_value": 200000.0
    }

    # 1. TradingView Symbol Search (Direct mapping & real-time quotes)
    try:
        search_url = f"https://symbol-search.tradingview.com/symbol_search/v3/?text={isin}&hl=1&lang=zh_TW&search_type=undefined"
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(search_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                symbols = data.get('symbols', [])
                if symbols:
                    # Prefer FINRA if available, else first symbol
                    finra_sym = next((s for s in symbols if s.get('exchange') == 'FINRA'), symbols[0])
                    exch = finra_sym.get('exchange', 'FINRA')
                    sym = re.sub(r'<[^>]+>', '', finra_sym.get('symbol', ''))
                    desc = finra_sym.get('description') or finra_sym.get('name')

                    tv_url = f"https://tw.tradingview.com/symbols/{exch}-{sym}/"
                    result["name"] = desc
                    result["price_source"] = "TradingView"
                    result["price_source_url"] = tv_url

                    # Fetch live price from the discovered TradingView page
                    live_price = await fetch_price_from_url(tv_url)
                    if live_price:
                        result["latest_price"] = round(float(live_price), 3)
    except Exception as e:
        logger.warning(f"TradingView lookup failed for {isin}: {e}")

    # 2. If name is still missing, fallback to OpenFIGI API
    if not result["name"]:
        try:
            figi_url = "https://api.openfigi.com/v3/mapping"
            payload = [{"idType": "ID_ISIN", "idValue": isin}]
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(figi_url, json=payload)
                if resp.status_code == 200:
                    figi_data = resp.json()
                    if figi_data and "data" in figi_data[0]:
                        item = figi_data[0]["data"][0]
                        issuer = item.get("name", "").title()
                        desc = item.get("securityDescription", "")
                        result["name"] = f"{issuer} {desc}".strip()
        except Exception as e:
            logger.warning(f"OpenFIGI lookup failed for {isin}: {e}")

    # 3. If price is still missing, try Börse Frankfurt by ISIN
    if not result["latest_price"]:
        try:
            fk_price = await fetch_price_from_frankfurt(isin)
            if fk_price:
                result["latest_price"] = round(float(fk_price), 3)
                if not result["price_source"]:
                    result["price_source"] = "Deutsche Börse"
                    result["price_source_url"] = f"https://www.boerse-frankfurt.de/bond/{isin.lower()}"
        except Exception as e:
            logger.debug(f"Frankfurt price fallback failed for {isin}: {e}")

    # 4. Fallback name if none found
    if not result["name"]:
        result["name"] = f"債券 {isin}"

    return result


