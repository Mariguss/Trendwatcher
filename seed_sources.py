import asyncio
import logging

from sqlalchemy import select

from backend.core.database import database
from backend.models.sources import Source, SourceType

logger = logging.getLogger(__name__)

# Список источников для первичного наполнения базы данных
SOURCES_DATA = [
    {
        "name": "ЦБ РФ (Финтех)",
        "url": "https://www.cbr.ru/fintech/",
        "source_type": SourceType.WEB,
        "reliability_score": 10.0,
    },
    {
        "name": "НСПК",
        "url": "https://www.nspk.ru/press-center/news/",
        "source_type": SourceType.WEB,
        "reliability_score": 9.5,
    },
    {
        "name": "Frank Media (Теги)",
        "url": "https://frankmedia.ru/tags",
        "source_type": SourceType.WEB,
        "reliability_score": 8.5,
    },
    {
        "name": "Frank Research Group",
        "url": "https://frankrg.com/research",
        "source_type": SourceType.WEB,
        "reliability_score": 8.5,
    },
    {
        "name": "VC.ru (Финтех)",
        "url": "https://vc.ru/finance",
        "source_type": SourceType.WEB,
        "reliability_score": 7.5,
    },
    {
        "name": "TAdviser",
        "url": "https://www.tadviser.ru/index.php/Новости",
        "source_type": SourceType.WEB,
        "reliability_score": 8.0,
    },
]


async def seed_sources():
    """Добавляет начальные источники в базу данных, если их там еще нет."""
    logger.info("Starting database seeding for sources...")
    
    async for session in database.get_session():
        added_count = 0
        for data in SOURCES_DATA:
            # Проверяем, существует ли уже источник с таким URL
            stmt = select(Source).where(Source.url == data["url"])
            existing_source = (await session.execute(stmt)).scalar_one_or_none()
            
            if not existing_source:
                source = Source(**data)
                session.add(source)
                added_count += 1
                logger.info("Added source: %s", data["name"])
            else:
                logger.debug("Source already exists: %s", data["name"])
        
        if added_count > 0:
            await session.commit()
            logger.info("Successfully added %d new sources to the database.", added_count)
        else:
            logger.info("All sources are already present in the database.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(seed_sources())