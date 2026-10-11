import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from backend.core.database import database
from backend.models.signals import Signal
from backend.models.signal_sources import SignalSource
from backend.models.raw_publications import RawPublication

logger = logging.getLogger(__name__)

class SourceModel(BaseModel):
    title: str
    url: str

class SignalModel(BaseModel):
    id: int
    headline: str
    hotness: float
    why_now: str
    category: str
    summary: str
    draft: str
    confidence: float
    sources: List[SourceModel]

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Fintech Trendwatcher API")
    yield
    logger.info("Shutting down Fintech Trendwatcher API")

app = FastAPI(
    title="Финтех Трендвотчер",
    description="Прототип сервиса для мониторинга финтех-публикаций",
    version="1.0.0",
    lifespan=lifespan
)

# Указываем путь к папке с шаблонами
templates = Jinja2Templates(directory="backend/api/templates")

async def get_signals_with_sources() -> List[SignalModel]:
    """Получает сигналы с их источниками из базы данных."""
    async for session in database.get_session():
        # Сортируем по важности (hotness) по убыванию
        stmt = select(Signal).order_by(Signal.hotness.desc()).limit(10)
        signals = (await session.execute(stmt)).scalars().all()
        
        result = []
        for sig in signals:
            sources_stmt = select(SignalSource, RawPublication).join(
                RawPublication, SignalSource.publication_id == RawPublication.id
            ).where(SignalSource.signal_id == sig.id)
            sources_data = (await session.execute(sources_stmt)).all()
            
            sources_list = [
                SourceModel(
                    title=row.RawPublication.title,
                    url=row.RawPublication.url
                )
                for row in sources_data
            ]
            
            result.append(SignalModel(
                id=sig.id,
                headline=sig.headline,
                hotness=sig.hotness,
                why_now=sig.why_now,
                category=sig.category.value if sig.category else "N/A",
                summary=sig.summary,
                draft=sig.draft,
                confidence=sig.confidence_score,
                sources=sources_list
            ))
        
        return result

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Главная страница с дайджестом сигналов."""
    signals = await get_signals_with_sources()
    
    # ВАЖНО: в новых версиях FastAPI/Starlette request идет первым аргументом!
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"signals": signals}
    )

@app.get("/api/signals", response_model=List[SignalModel])
async def get_signals_api():
    """API эндпоинт для получения сигналов в JSON формате."""
    return await get_signals_with_sources()