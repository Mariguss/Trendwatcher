"""
Оркестратор пайплайна: очищает базу данных и запускает все этапы с нуля.
Использование: poetry run python run_pipeline.py
"""

import asyncio
import logging
import os

from sqlalchemy import text

from backend.core.database import database

logger = logging.getLogger(__name__)

TABLES_TO_TRUNCATE = [
    "digest_signals",
    "signal_sources",
    "signals",
    "cluster_items",
    "publication_clusters",
    "raw_publications",
    "digests",
    "sources",
    "target_roles",
    "categories",
]


async def database_is_empty() -> bool:
    """Проверяет, есть ли уже данные в базе."""
    async for session in database.get_session():
        try:
            count = (await session.execute(text("SELECT COUNT(*) FROM sources"))).scalar()
            return count == 0
        except Exception:
            return True  # Если таблицы нет — считаем базу пустой


async def reset_database():
    """Очищает все таблицы базы данных."""
    logger.info("Очистка базы данных...")
    async for session in database.get_session():
        await session.execute(text("SET session_replication_role = 'replica';"))
        for table in TABLES_TO_TRUNCATE:
            try:
                await session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
            except Exception:
                pass
        await session.execute(text("SET session_replication_role = 'origin';"))
        await session.commit()
    logger.info("База данных очищена.")


async def run_full_pipeline():
    # Если FORCE_RUN не установлен и база не пустая — пропускаем
    force_run = os.environ.get("FORCE_RUN", "").lower() in ("1", "true", "yes")
    if not force_run and not await database_is_empty():
        logger.info("База уже наполнена. Пропускаем пайплайн (установите FORCE_RUN=1 для принудительного запуска).")
        return

    logger.info("=" * 60)
    logger.info("ЗАПУСК ПОЛНОГО ПАЙПЛАЙНА")
    logger.info("=" * 60)

    await reset_database()

    logger.info("Этап 1: Добавление источников...")
    from seed_sources import seed_sources
    await seed_sources()

    logger.info("Этап 2: Парсинг публикаций...")
    from backend.services.scraper import FintechScraper
    await FintechScraper().run()

    logger.info("Этап 3: Векторизация и кластеризация...")
    from backend.services.embedder import EmbeddingClusterService
    await EmbeddingClusterService().run_full_pipeline()

    logger.info("Этап 4: Генерация карточек сигналов...")
    from backend.services.signal_generator import SignalGeneratorService
    await SignalGeneratorService().run()

    logger.info("=" * 60)
    logger.info("ПАЙПЛАЙН ЗАВЕРШЁН УСПЕШНО")
    logger.info("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(run_full_pipeline())