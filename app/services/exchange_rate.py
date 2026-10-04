import httpx
from bs4 import BeautifulSoup
import datetime
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

class ExchangeRateService:
    _rate: float = 32.0
    _last_updated: datetime.datetime = None

    @classmethod
    async def get_rate(cls, force_refresh: bool = False) -> float:
        now = datetime.datetime.now()
        if not force_refresh and cls._last_updated and (now - cls._last_updated).total_seconds() < 1800:
            return cls._rate

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # 1. Google Finance 即時爬取 (優先)
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.get("https://www.google.com/finance/quote/USD-TWD", headers=headers)
                if response.status_code == 200:
                    html = response.text
                    
                    # 模式 1: Google 知識圖譜實體 ID /g/11bvvyhtlb
                    m1 = re.search(r'\["/g/11bvvyhtlb".{0,80}?\[([0-9]{2}\.[0-9]{2,8})', html)
                    if m1:
                        val = float(m1.group(1))
                        if 20.0 <= val <= 50.0:
                            cls._rate = round(val, 2)
                            cls._last_updated = now
                            logger.info(f"成功自 Google Finance (Entity ID) 取得即時匯率: {cls._rate}")
                            return cls._rate

                    # 模式 2: 主標題 USD / TWD 後接續的數值 span
                    m2 = re.search(r'USD\s*/\s*TWD.*?<span>([0-9]{2}\.[0-9]{2,4})</span>', html, re.S)
                    if m2:
                        val = float(m2.group(1))
                        if 20.0 <= val <= 50.0:
                            cls._rate = round(val, 2)
                            cls._last_updated = now
                            logger.info(f"成功自 Google Finance (Header Span) 取得即時匯率: {cls._rate}")
                            return cls._rate

                    # 模式 3: 傳統 class (相容部分語系或舊版 DOM)
                    soup = BeautifulSoup(html, "html.parser")
                    rate_element = soup.find("div", class_="YMlKec fxKbKc")
                    if rate_element:
                        val = float(rate_element.text.replace(",", ""))
                        if 20.0 <= val <= 50.0:
                            cls._rate = round(val, 2)
                            cls._last_updated = now
                            logger.info(f"成功自 Google Finance (YMlKec) 取得即時匯率: {cls._rate}")
                            return cls._rate
        except Exception as e:
            logger.warning(f"Google Finance 匯率取得失敗: {e}")

        # 2. Yahoo Finance 即時行情 API (備援一)
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/USDTWD=X", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    if price and 20.0 <= float(price) <= 50.0:
                        cls._rate = round(float(price), 2)
                        cls._last_updated = now
                        logger.info(f"成功自 Yahoo Finance 取得即時匯率: {cls._rate}")
                        return cls._rate
        except Exception as e:
            logger.warning(f"Yahoo Finance 匯率取得失敗: {e}")

        # 3. open.er-api.com API (備援二)
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.get("https://open.er-api.com/v6/latest/USD", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    val = float(data.get("rates", {}).get("TWD", 0))
                    if 20.0 <= val <= 50.0:
                        cls._rate = round(val, 2)
                        cls._last_updated = now
                        logger.info(f"自 open.er-api.com 取得匯率: {cls._rate}")
                        return cls._rate
        except Exception as e:
            logger.warning(f"open.er-api.com 匯率取得失敗: {e}")

        # 4. exchangerate-api.com (備援三)
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get("https://api.exchangerate-api.com/v4/latest/USD")
                if response.status_code == 200:
                    data = response.json()
                    val = float(data.get("rates", {}).get("TWD", 0))
                    if 20.0 <= val <= 50.0:
                        cls._rate = round(val, 2)
                        cls._last_updated = now
                        logger.info(f"自 exchangerate-api 取得匯率: {cls._rate}")
                        return cls._rate
        except Exception as e:
            logger.error(f"所有匯率來源皆獲取失敗: {e}")

        return cls._rate

