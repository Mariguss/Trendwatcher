"""
Парсер для сбора публикаций из проверенных RSS-лент.
Извлекает заголовок, дату и очищенный текст статьи.
"""

import asyncio
import logging 
from datetime import datetime, timezone

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from backend.core.database import database
from backend.models.raw_publications import RawPublication
from backend.models.sources import Source, SourceType

logger = logging.getLogger(__name__)

# Константы конфигурации
REQUEST_TIMEOUT: float = 15.0
DELAY_BETWEEN_REQUESTS: float = 1.0
MAX_ARTICLES_PER_SOURCE: int = 100
MIN_CONTENT_LENGTH: int = 150
MAX_CONTENT_LENGTH: int = 4000


async def main() -> None:
    """Основной цикл парсинга RSS-источников."""
    logger.info("Запуск RSS-парсера")
    
    async for session in database.get_session():
        stmt = select(Source).where(Source.source_type == SourceType.RSS)
        sources = (await session.execute(stmt)).scalars().all()
        
        logger.info("Найдено %d RSS-источников для обработки", len(sources))
        
        total_added = 0
        
        async with httpx.AsyncClient(
            verify=False, 
            timeout=REQUEST_TIMEOUT, 
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        ) as client:
            for source in sources:
                logger.info("Обработка источника: %s", source.name)
                
                try:
                    response = await client.get(source.api_url)
                    response.raise_for_status()
                    
                    feed = feedparser.parse(response.text)
                    added_count = 0
                    
                    for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                        title = entry.get("title", "").strip()
                        if not title:
                            continue
                        
                        # Извлечение сырого текста
                        raw_text = entry.get("summary", "")
                        if not raw_text and entry.get("content"):
                            raw_text = entry["content"][0].get("value", "")
                        
                        # Очистка от HTML-разметки
                        soup = BeautifulSoup(raw_text, "html.parser")
                        clean_text = soup.get_text(separator=" ", strip=True)
                        
                        # Фильтрация слишком коротких записей
                        if len(clean_text) < MIN_CONTENT_LENGTH:
                            continue
                        
                        # Определение даты публикации
                        date_tuple = entry.get("published_parsed") or entry.get("updated_parsed")
                        if date_tuple:
                            try:
                                pub_date = datetime(*date_tuple[:6], tzinfo=timezone.utc).replace(tzinfo=None)
                            except (ValueError, TypeError):
                                pub_date = datetime.now(timezone.utc).replace(tzinfo=None)
                        else:
                            pub_date = datetime.now(timezone.utc).replace(tzinfo=None)
                        
                        # Проверка на дубликаты по URL
                        url = entry.get("link", "")[:250]
                        exists_stmt = select(RawPublication).where(RawPublication.url == url)
                        existing = (await session.execute(exists_stmt)).scalar_one_or_none()
                        
                        if existing:
                            continue
                        
                        # Сохранение публикации
                        session.add(RawPublication(
                            source_id=source.id,
                            url=url,
                            title=title,
                            content=clean_text[:MAX_CONTENT_LENGTH],
                            published_at=pub_date,
                        ))
                        added_count += 1
                    
                    total_added += added_count
                    logger.info("Источник '%s' обработан. Добавлено статей: %d", source.name, added_count)
                    
                except httpx.HTTPError as e:
                    logger.error("HTTP ошибка при запросе %s: %s", source.name, e)
                except Exception as e:
                    logger.error("Непредвиденная ошибка при обработке %s: %s", source.name, e, exc_info=True)
                
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
        
        if total_added > 0:
            await session.commit()
            logger.info("Парсинг завершен. Всего добавлено новых статей: %d", total_added)
        else:
            logger.info("Парсинг завершен. Новых статей не найдено.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, 
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    asyncio.run(main())