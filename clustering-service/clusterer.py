import logging

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import database
from backend.models import RawPublication, ClusterItem, PublicationCluster

# Порог косинусного сходства для определения дублей/перепечаток (0.85 = 85% схожести)
SIMILARITY_THRESHOLD = 0.85

logger = logging.getLogger(__name__)

class ClusteringService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_and_create_clusters(self) -> int:
        """
        Ищет похожие публикации и объединяет их в кластеры.
        Это реализует требование ТЗ: 'борьба с дублями, перепечатками и нерелевантным шумом'.
        """
        clusters_created = 0
        try:            # Получаем все публикации, для которых уже рассчитаны векторы
            stmt = select(RawPublication).where(RawPublication.embedded.isnot(None))
            publications = (await self.session.execute(stmt)).scalars().all()

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
                self.session.add(cluster)
                await self.session.flush()  # Получаем сгенерированный cluster.id

                # Добавляем первичную публикацию в элементы кластера
                session.add(ClusterItem(
                    cluster_id=cluster.id,
                    publication_id=pub1.id,
                    is_primary=True
                ))
                clustered_pub_ids.add(pub1.id)

                # Сравниваем с остальными публикациями
                vec1 = np.array(pub1.embedded)
                for pub2 in publications[i + 1:]:
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

            await self.session.commit()
            logger.info("Clustering completed. Created %d clusters.", clusters_created)

        return clusters_created
