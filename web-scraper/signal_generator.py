import logging
import random
from typing import List, Dict, Any

from sqlalchemy import select

from backend.core.database import database
from backend.models.cluster_items import ClusterItem
from backend.models.publication_clusters import PublicationCluster
from backend.models.raw_publications import RawPublication
from backend.models.signals import Signal, Category
from backend.models.signal_sources import SignalSource

logger = logging.getLogger(__name__)


class SignalGeneratorService:
    """
    Сервис для генерации структурированных сигналов на основе кластеров публикаций.
    Реализует логику: Кластер -> Анализ текста -> Карточка сигнала (Summary, Hotness, Why now, Draft).
    """

    def _generate_mock_llm_response(self, primary_text: str, title: str) -> Dict[str, Any]:
        """
        Генерирует структурированный ответ, имитирующий работу LLM.
        В продакшене здесь будет вызов YandexGPT / GigaChat / Ollama с промптом.
        """
        # Простая эвристика для определения категории по ключевым словам
        text_lower = primary_text.lower()
        if "сбп" in text_lower or "платеж" in text_lower or "qr" in text_lower:
            category = Category.PAYMENT_SERVICE
        elif "регулятор" in text_lower or "цб" in text_lower or "указание" in text_lower:
            category = Category.REGULATION
        elif "партнер" in text_lower or "совместн" in text_lower:
            category = Category.PARTNERSHIP
        else:
            category = Category.MARKET

        # Генерация "умных" полей на основе заголовка и начала текста
        first_sentences = primary_text.split('.')[:2]
        summary_text = ". ".join(first_sentences).strip() + "."
        
        return {
            "headline": title if len(title) < 80 else title[:77] + "...",
            "hotness": random.uniform(7.0, 9.5),  # Для прототипа ставим высокую релевантность
            "why_now": "Растущий тренд на импортозамещение и цифровизацию финансовых сервисов делает эту тему актуальной для стратегического планирования.",
            "category": category,
            "summary": summary_text,
            "draft": f"Коллеги, обратите внимание на сигнал по категории {category.value}.\n\n"
                     f"Суть: {summary_text}\n\n"
                     f"Рекомендация: обсудить на ближайшем продуктовом комитете влияние на наши текущие roadmap."
        }

    async def process_clusters(self) -> int:
        """Обрабатывает все кластеры и создает для них сигналы."""
        signals_created = 0
        
        async for session in database.get_session():
            # Получаем все кластеры
            stmt = select(PublicationCluster)
            clusters = (await session.execute(stmt)).scalars().all()

            if not clusters:
                logger.info("No clusters found to process.")
                return 0

            logger.info("Found %d clusters to process into signals.", len(clusters))

            for cluster in clusters:
                # Проверяем, не создан ли уже сигнал для этого кластера
                existing_signal = (await session.execute(
                    select(Signal).where(Signal.cluster_id == cluster.id)
                )).scalar_one_or_none()
                
                if existing_signal:
                    logger.debug("Signal already exists for cluster %d", cluster.id)
                    continue

                # Находим первичную публикацию в кластере для генерации выжимки
                primary_item_stmt = select(ClusterItem).where(
                    ClusterItem.cluster_id == cluster.id,
                    ClusterItem.is_primary == True
                )
                primary_item = (await session.execute(primary_item_stmt)).scalar_one_or_none()
                
                if not primary_item:
                    logger.warning("No primary item found for cluster %d", cluster.id)
                    continue

                pub = (await session.execute(
                    select(RawPublication).where(RawPublication.id == primary_item.publication_id)
                )).scalar_one_or_none()

                if not pub:
                    continue

                logger.info("Generating signal for cluster %d (Primary pub: %s)", cluster.id, pub.title[:40])

                # Генерируем карточку сигнала
                signal_data = self._generate_mock_llm_response(pub.content, pub.title)

                # Создаем запись сигнала
                new_signal = Signal(
                    cluster_id=cluster.id,
                    category=signal_data["category"],
                    headline=signal_data["headline"],
                    hotness=signal_data["hotness"],
                    why_now=signal_data["why_now"],
                    summary=signal_data["summary"],
                    draft=signal_data["draft"],
                    confidence_score=0.85  # Уверенность в качестве кластеризации
                )
                session.add(new_signal)
                await session.flush()  # Получаем new_signal.id

                # Связываем сигнал со всеми публикациями в этом кластере как источники
                all_items_stmt = select(ClusterItem).where(ClusterItem.cluster_id == cluster.id)
                all_items = (await session.execute(all_items_stmt)).scalars().all()
                
                for item in all_items:
                    session.add(SignalSource(
                        signal_id=new_signal.id,
                        publication_id=item.publication_id
                    ))

                signals_created += 1

            await session.commit()
            logger.info("Successfully created %d new signals.", signals_created)
            
        return signals_created

    async def run(self):
        logger.info("Starting signal generation pipeline.")
        await self.process_clusters()
        logger.info("Signal generation pipeline finished.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    import asyncio
    service = SignalGeneratorService()
    asyncio.run(service.run())