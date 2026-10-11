import asyncio
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
import trafilatura
from bs4 import BeautifulSoup
from sqlalchemy import select

from backend.core.database import database
from backend.models.raw_publications import RawPublication
from backend.models.sources import Source

logger = logging.getLogger(__name__)

KEYWORDS = [
    "сбп", "цифровой рубль", "ебс", "биометрия", "финтех", 
    "эквайринг", "маркетплейс", "банк", "партнерство", "платеж", "сервис"
]


class FintechScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }

    async def fetch_html(self, url: str) -> str:
        async with httpx.AsyncClient(headers=self.headers, timeout=15.0) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as e:
                logger.error("Failed to fetch URL %s: %s", url, e)
                return ""

    def extract_clean_text(self, html: str, url: str) -> dict | None:
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        if not text or len(text) < 150:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title else "Без заголовка"
        
        text_lower = text.lower()
        if not any(kw in text_lower for kw in KEYWORDS):
            return None

        return {
            "title": title,
            "content": text,
            "url": url,
            "published_at": datetime.now(timezone.utc)
        }

    async def scrape_vc_ru(self, source_id: int):
        logger.info("Starting scrape for VC.ru (Finance)")
        url = "https://vc.ru/finance"
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        
        articles = soup.find_all("a", href=True)
        links_to_parse = []
        
        # Более гибкое условие: ссылка должна содержать vc.ru/finance/ и не быть просто главной страницей раздела
        for a in articles:
            href = a["href"]
            if href.startswith("https://vc.ru/finance/") and len(href) > 30:
                links_to_parse.append(href)
        
        # Убираем дубликаты и берем первые 5
        unique_links = list(set(links_to_parse))[:5]
        logger.info("Found %d potential article links on VC.ru", len(unique_links))
        
        for link in unique_links:
            logger.debug("Fetching article: %s", link)
            article_html = await self.fetch_html(link)
            data = self.extract_clean_text(article_html, link)
            if data:
                await self.save_publication(source_id, data)
            else:
                logger.debug("Skipped (no keywords or too short): %s", link)
            await asyncio.sleep(1)

    async def scrape_tadviser(self, source_id: int):
        logger.info("Starting scrape for TAdviser")
        url = "https://www.tadviser.ru/index.php/Новости"
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        
        articles = soup.find_all("a", href=True)
        links_to_parse = []
        
        for a in articles:
            href = a["href"]
            # Ищем ссылки на конкретные новости (они обычно содержат /index.php/ и имеют достаточную длину)
            if "/index.php/" in href and len(href) > 40:
                full_url = urljoin("https://www.tadviser.ru", href)
                links_to_parse.append(full_url)
        
        unique_links = list(set(links_to_parse))[:3] # Берем 3 для теста
        logger.info("Found %d potential article links on TAdviser", len(unique_links))
        
        for link in unique_links:
            logger.debug("Fetching article: %s", link)
            article_html = await self.fetch_html(link)
            data = self.extract_clean_text(article_html, link)
            if data:
                await self.save_publication(source_id, data)
            else:
                logger.debug("Skipped (no keywords or too short): %s", link)
            await asyncio.sleep(1)

    async def save_publication(self, source_id: int, data: dict):
        async for session in database.get_session():
            stmt = select(RawPublication).where(RawPublication.url == data["url"])
            if (await session.execute(stmt)).scalar_one_or_none():
                logger.debug("Publication already exists: %s", data["url"])
                return

            pub = RawPublication(
                source_id=source_id,
                title=data["title"],
                content=data["content"],
                url=data["url"],
                published_at=data["published_at"],
                embedded=None
            )
            session.add(pub)
            await session.commit()
            logger.info("Saved publication: %s", data["title"][:60])

    async def run(self):
        async for session in database.get_session():
            sources = (await session.execute(select(Source))).scalars().all()
            
            tasks = []
            for src in sources:
                if "vc.ru" in src.url:
                    tasks.append(self.scrape_vc_ru(src.id))
                elif "tadviser.ru" in src.url:
                    tasks.append(self.scrape_tadviser(src.id))
            
            if tasks:
                await asyncio.gather(*tasks)
            else:
                logger.warning("No configured sources found. Please run seed_sources.py first.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, # Включаем DEBUG, чтобы видеть все шаги
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    scraper = FintechScraper()
    asyncio.run(scraper.run())