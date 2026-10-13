"""
Модуль для инициализации справочника источников данных.
Читает конфигурацию из JSON, валидирует её и сохраняет в БД.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import database
from backend.models.sources import Source, SourceType

logger = logging.getLogger(__name__)

# Путь к файлу конфигурации относительно этого скрипта
CONFIG_PATH = Path(__file__).parent / "sources.json"


class SourceConfig(BaseModel):
    """Модель валидации источника из JSON."""
    name: str = Field(..., min_length=2, description="Название источника")
    url: HttpUrl = Field(..., description="Основной URL сайта")
    api_url: str | None = Field(default=None, description="URL RSS-ленты или API")
    api_key: str | None = Field(default=None, description="Ключ доступа к API")
    source_type: str = Field(default="web", description="web, rss или api")
    reliability_score: float = Field(default=7.0, ge=0.0, le=10.0, description="Оценка надежности (0-10)")
    category: str | None = Field(default=None, description="Категория источника")


def load_and_validate_sources(file_path: Path) -> list[SourceConfig]:
    """Читает JSON и валидирует данные через Pydantic."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Конфигурационный файл не найден: {file_path}")

    try:
        with file_path.open("r", encoding="utf-8") as f:
            raw_data: list[dict[str, Any]] = json.load(f)
        
        return [SourceConfig(**item) for item in raw_data]
    
    except json.JSONDecodeError as e:
        logger.error("Ошибка парсинга JSON файла %s: %s", file_path, e)
        raise
    except ValidationError as e:
        logger.error("Ошибка валидации данных источников: %s", e.errors())
        raise


async def upsert_sources(sources: list[SourceConfig], session: AsyncSession) -> tuple[int, int]:
    """
    Добавляет источники в БД, пропуская дубликаты по URL.
    Возвращает кортеж: (количество добавленных, количество пропущенных).
    """
    added_count = 0
    skipped_count = 0

    for config in sources:
        # Проверяем наличие по URL
        stmt = select(Source).where(Source.url == str(config.url))
        result = await session.execute(stmt)
        existing_source = result.scalar_one_or_none()

        if existing_source:
            logger.debug("Пропущен (уже существует): %s", config.name)
            skipped_count += 1
            continue

        # Определяем тип источника из JSON (по умолчанию WEB)
        try:
            source_type = SourceType(config.source_type.lower())
        except ValueError:
            logger.warning("Неизвестный тип источника '%s' для %s, используем WEB", config.source_type, config.name)
            source_type = SourceType.WEB

        # Создаем новый объект со ВСЕМИ полями
        new_source = Source(
            name=config.name,
            url=str(config.url),
            source_type=source_type,
            reliability_score=config.reliability_score,
            api_url=config.api_url,
        )
        session.add(new_source)
        added_count += 1
        logger.info("Добавлен источник: %s (тип: %s)", config.name, source_type.value)

    if added_count > 0:
        await session.commit()
        
    return added_count, skipped_count


async def main() -> None:
    """Точка входа для инициализации источников."""
    logger.info("Начало инициализации источников из %s", CONFIG_PATH)
    
    try:
        # 1. Чтение и валидация
        validated_sources = load_and_validate_sources(CONFIG_PATH)
        logger.info("Успешно загружено и валидировано %d источников", len(validated_sources))
        
        # 2. Запись в БД
        session_manager = asynccontextmanager(database.get_session)
        async with session_manager() as session:
            added, skipped = await upsert_sources(validated_sources, session)

        logger.info(
            "Операция завершена. Добавлено: %d, Пропущено: %d",
            added, skipped
        )
            
    except FileNotFoundError as e:
        logger.critical("Критическая ошибка: %s", e)
    except Exception as e:
        logger.exception("Непредвиденная ошибка при инициализации источников: %s", e)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    asyncio.run(main())