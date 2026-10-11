import logging
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import select

from backend.core.database import database
from backend.models.cluster_items import ClusterItem
from backend.models.publication_clusters import PublicationCluster
from backend.models.raw_publications import RawPublication

logger = logging.getLogger(__name__)

# Легкая и быстрая модель, поддерживающая русский язык (384 измерения)
EMBEDDING_MODEL_NAME = "cointegrated/rubert-tiny2"
# Порог косинусного сходства для определения дублей/перепечаток (0.85 = 85% схожести)
SIMILARITY_THRESHOLD = 0.85


class EmbeddingClusterService:
    def __init__(self):
        logger.info("Initializing embedding model: %s", EMBEDDING_MODEL_NAME)
        # При первом запуске модель скачается автоматически (это займет ~1 минуту)
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
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
        async for session in database.get_session():
            stmt = (
                select(RawPublication)
                .where(RawPublication.embedded.is_(None))
                .limit(50) # Ограничиваем батч для стабильности прототипа
            )
            publications = (await session.execute(stmt)).scalars().all()

            if not publications:
                logger.info("No new publications to embed.")
                return 0

            logger.info("Starting embedding for %d publications...", len(publications))
            for pub in publications:
                pub.embedded = self._get_embedding(pub.content)
                processed_count += 1
            
            await session.commit()
            logger.info("Successfully saved embeddings for %d publications.", processed_count)
            
        return processed_count

    async def find_and_create_clusters(self) -> int:
        """
        Ищет похожие публикации и объединяет их в кластеры.
        Это реализует требование ТЗ: 'борьба с дублями, перепечатками и нерелевантным шумом'.
        """
        clusters_created = 0
        async for session in database.get_session():
            # Получаем все публикации, для которых уже рассчитаны векторы
            stmt = select(RawPublication).where(RawPublication.embedded.isnot(None))
            publications = (await session.execute(stmt)).scalars().all()

            if len(publications) < 2:
                logger.info("At least 2 embedded publications are required for clustering.")
                return 0

            logger.info("Analyzing %d publications for duplicates and reprints...", len(publications))
            
            # Множество ID публикаций, которые уже распределены по кластерам
            clustered_pub_ids = set()

            for i, pub1 in enumerate(publications):
                if pub1.id in clustered_pub_ids:
                    continue

                # Создаем новый кластер, где текущая публикация является первичной (первоисточником)
                cluster = PublicationCluster(
                    primary_publication_id=pub1.id
                )
                session.add(cluster)
                await session.flush() # Получаем сгенерированный cluster.id

                # Добавляем первичную публикацию в элементы кластера
                session.add(ClusterItem(
                    cluster_id=cluster.id,
                    publication_id=pub1.id,
                    is_primary=True
                ))
                clustered_pub_ids.add(pub1.id)

                # Сравниваем с остальными публикациями
                vec1 = np.array(pub1.embedded)
                for pub2 in publications[i+1:]:
                    if pub2.id in clustered_pub_ids:
                        continue
                    
                    vec2 = np.array(pub2.embedded)
                    
                    # Расчет косинусного сходства
                    similarity = float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))
                    
                    if similarity >= SIMILARITY_THRESHOLD:
                        logger.debug(
                            "Duplicate/reprint detected (similarity: %.2f): '%s' and '%s'",
                            similarity, pub1.title[:40], pub2.title[:40]
                        )
                        session.add(ClusterItem(
                            cluster_id=cluster.id,
                            publication_id=pub2.id,
                            is_primary=False
                        ))
                        clustered_pub_ids.add(pub2.id)
                
                clusters_created += 1

            await session.commit()
            logger.info("Clustering completed. Created %d clusters.", clusters_created)
            
        return clusters_created

    async def run_full_pipeline(self):
        """Запускает полный пайплайн: векторизация -> кластеризация."""
        logger.info("Starting embedding and clustering pipeline.")
        embedded_count = await self.process_new_publications()
        if embedded_count > 0 or True: # Всегда пытаемся кластеризовать, если есть данные
            await self.find_and_create_clusters()
        logger.info("Pipeline execution finished.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    import asyncio
    service = EmbeddingClusterService()

    asyncio.run(service.run_full_pipeline())