import asyncio
import logging
from typing import List

from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import database
from backend.models.raw_publications import RawPublication

logger = logging.getLogger(__name__)

# Легкая и быстрая модель, поддерживающая русский язык (312 измерения)
EMBEDDING_MODEL_NAME = "cointegrated/rubert-tiny2"


class EmbeddingService:
    def __init__(self, session: AsyncSession):
        logger.info("Initializing embedding model: %s", EMBEDDING_MODEL_NAME)
        # При первом запуске модель скачается автоматически (это займет ~1 минуту)
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self.session = session
        logger.info("Model loaded successfully.")

    def _get_embedding(self, text: str) -> List[float]:
        """Генерирует векторное представление для текста."""
        # Ограничиваем длину текста для оптимизации производительности 
        # (первые 1000 символов обычно содержат ключевую суть новости)
        truncated_text = text[:1000] if text else ""
        embedding = self.model.encode(truncated_text, convert_to_numpy=True)
        return embedding.tolist()

    async def process_new_publications(self) -> int:
        """Векторизует новые публикации, у которых еще нет эмбеддинга."""
        processed_count = 0
        try:
            stmt = (
                select(RawPublication)
                .where(RawPublication.embedded.is_(None))
                .limit(50) # Ограничиваем батч для стабильности прототипа
            )
            publications = (await self.session.execute(stmt)).scalars().all()

            if not publications:
                logger.info("No new publications to embed.")
                return 0

            logger.info("Starting embedding for %d publications...", len(publications))
            for pub in publications:
                pub.embedded = self._get_embedding(pub.content)
                processed_count += 1
            
            await self.session.commit()
            logger.info("Successfully saved embeddings for %d publications.", processed_count)
            
            return processed_count
        except Exception as e:
            logger.exception("Failed to save embedding for %d publications. Exception text: %s", processed_count, e)


async def main():
    async with database.get_session() as session:
        service = EmbeddingService(session)

        await service.process_new_publications()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Запускаем единственный цикл событий, в котором выполнится вся цепочка
    asyncio.run(main())

    # from transformers import AutoConfig
    # # Загружаем только конфигурацию модели без скачивания самих весов
    # config = AutoConfig.from_pretrained("cointegrated/rubert-tiny2")
    # # Выводим размер скрытого слоя (количество измерений)
    # print(config.hidden_size)  # Выведет: 312
