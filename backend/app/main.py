import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.db.mongo import close_mongo, connect_mongo
from app.services.cnn_anomaly import CNNAnomalyService
from app.services.clip_service import ClipService
from app.services.db_service import DBService
from app.services.llm_service import LLMService
from app.services.notification_service import NotificationService
from app.services.user_service import UserService
from app.services.video_stream import CameraPipeline, StreamHub
from app.services.yolo_service import YOLOService
from app.services.audio_service import AudioService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = logging.getLogger("app.main")
    db = await connect_mongo()
    db_service = DBService(db)
    user_service = UserService(db)

    for attempt in range(1, 11):
        try:
            await db_service.ensure_indexes()
            await user_service.ensure_indexes()
            logger.info("MongoDB indexes verified successfully")
            break
        except Exception as exc:
            if attempt == 10:
                logger.warning("MongoDB indexes could not be created: %s", exc)
            else:
                logger.info("Waiting for MongoDB connection (attempt %d/10)...", attempt)
                await asyncio.sleep(1)

    stream_hub = StreamHub()
    yolo_service = YOLOService()
    anomaly_service = CNNAnomalyService()
    clip_service = ClipService(settings.clip_output_dir, settings.pre_event_seconds, settings.post_event_seconds)
    llm_service = LLMService()
    notification_service = NotificationService()
    audio_service = AudioService()
    pipeline = CameraPipeline(
        stream_hub,
        db_service,
        yolo_service,
        anomaly_service,
        clip_service,
        llm_service,
        notification_service,
        audio_service,
    )

    app.state.db = db
    app.state.db_service = db_service
    app.state.user_service = user_service
    app.state.stream_hub = stream_hub
    app.state.pipeline = pipeline
    yield
    await pipeline.stop()
    await close_mongo()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

clips_dir = Path(settings.clip_output_dir)
clips_dir.mkdir(parents=True, exist_ok=True)
thumbnails_dir = clips_dir.parent / "thumbnails"
thumbnails_dir.mkdir(parents=True, exist_ok=True)
app.mount("/clips", StaticFiles(directory=str(clips_dir)), name="clips")
app.mount("/thumbnails", StaticFiles(directory=str(thumbnails_dir)), name="thumbnails")


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
