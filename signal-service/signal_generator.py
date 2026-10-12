import logging
import random
from typing import List, Dict, Any

from sqlalchemy import select

from asyncio import Semaphore

from json import loads

from gigachat import GigaChat
from gigachat.models import ChatCompletionRequest, ChatMessage

from backend.core.database import database
from backend.models.cluster_items import ClusterItem
from backend.models.publication_clusters import PublicationCluster
from backend.models.raw_publications import RawPublication
from backend.models.signals import Signal, Category
from backend.models.signal_sources import SignalSource

logger = logging.getLogger(__name__)


class SignalGeneratorService:
    SYSTEM_PROMPT:str
    semaphore = Semaphore(10)
    """
    Сервис для генерации структурированных сигналов на основе кластеров публикаций.
    Реализует логику: Кластер -> Анализ текста -> Карточка сигнала (Summary, Hotness, Why now, Draft).
    """

    async def _generate_mock_llm_response(self, primary_text: str, title: str, client) -> Dict[str, Any]:
        """
        Генерирует структурированный ответ.
        """
        async with self.semaphore:
            messages = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=f"Проанализируй следующую статью.\nНазвание:\n{title}\nТекст статьи:\n{primary_text}",
                )]
            try:
                response = await client.achat.create(
                    ChatCompletionRequest(model="GigaChat-2", messages=messages)
                )
                response = response.messages[0].content[0].text
                #Отобрали только нужную часть ответа и возвращаем словарь
                return loads(response)
            except Exception as e:
                """Ошибки пусть обрабатываются как словарь с ошибкой по ключу 'exception'"""
                return {"exception": e}

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
            async with GigaChat(
                credentials="<the key>",
                ca_bundle_file="Russian_Trusted_Root_CA.cer",
                scope="GIGACHAT_API_PERS"
            ) as client:
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
                    signal_data = await self._generate_mock_llm_response(pub.content, pub.title, client)

                    # Проверяем получилось ли обработать
                    if signal_data.get("exception"):
                        logger.warning("Smts wrong in process cluster %d", cluster.id)
                        continue

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
    service.SYSTEM_PROMPT = """Ты — критический аналитик в сфере финтеха.  
    Твоя задача — прочитать предоставленную статью (заголовок, аннотацию, полный текст) и дать короткую оценку, отделив действительно перспективные технологии и идеи от тех, которые в ближайшие‑среднесрочные годы вряд ли принесут ценность. Выполняй каждый пункт последовательно:

    1. **Извлечение контекста**  
       - Определи основную технологию/решение, целевой рынок и проблему, которую оно решает.  
       - Учти любые регуляторные, географические или макроэкономические факторы, упомянутые в статье.

    2. **Проверка релевантности**  
       - Решает ли технология реальную боль финансовых институтов или потребителей?  
       - Есть ли чётко измеримый эффект (сокращение затрат, ускорение процессов, повышение безопасности, инклюзивность, соблюдение нормативов и т.п.)?

    3. **Оценка зрелости**  
       - Классифицируй стадию развития решения: *концепция / прототип / пилот / коммерческий запуск / масштабирование*.  
       - Приведи доказательства: демонстрации продукта, пилотные проекты, партнёрства, патенты, раунды финансирования, одобрения регуляторов.

    4. **Конкурентный ландшафт**  
       - Перечисли существующие альтернативы (крупные вендоры, open‑source‑проекты, стартапы).  
       - Укажи, чем рассматриваемое решение отличается (цена, производительность, интеграция, регуляторная совместимость).

    5. **Анализ рисков и недостатков**  
       - Технические риски (масштабируемость, безопасность, совместимость).  
       - Рыночные риски (скорость принятия, фиксированные позиции incumbents, сетевые эффекты).  
       - Регуляторные риски (лицензирование, конфиденциальность данных, требования AML/KYC).  
       - Финансовые риски (burn‑rate, финансовая устойчивость, юнит‑экономика).

    6. **Перспективность**  
       - Соответствует ли подход известным отраслевым трендам (AI/ML, блокчейн, открытое банковское деле, облако‑нативные решения, встраиваемые финансы, устойчивость, импортозамещение, цифровизация)?  
       - Насколько решение гибко и готово адаптироваться к будущим стандартам (ISO20022, PSD2, фреймворки центральных банков по цифровой валюте и т.д.)?

    ### Формат ответа (Строго JSON И НИЧЕГО БОЛЕЕ, СТРОГО ПО ФОРМАТУ):
    {
      "headline": "Название технологии/решения",
      "why_now": "Опиши насколько проблема актуальна и причины актуальности/неактуальности",
      "summary": "Основной предмет изучения статьи, её суть",
      "draft_top": "Предложи нужно или не нужно изучать данную статью для внедрения, расскажи почему"
    }
    ### Если текст статьи отсутствует или состоит только из пробелов, ответь ровно так: {}
    ### Не добавляй к {} пояснений, текста или Markdown.
    ### Если текст статьи есть, даже если в нём мало деталей, проанализируй доступную информацию и верни JSON с полями ниже. Не возвращай {} только из-за нехватки деталей.
    """
    asyncio.run(service.run())