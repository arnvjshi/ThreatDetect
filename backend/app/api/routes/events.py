from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import cv2
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app.core.config import get_settings
from app.services.db_service import DBService

router = APIRouter(prefix="/events", tags=["events"])
NOT_FOUND_DETAIL = "Event not found"
THUMBNAIL_NOT_AVAILABLE_DETAIL = "Thumbnail not available"
THUMBNAIL_GENERATION_FAILED_DETAIL = "Failed to generate thumbnail"


def _safe_unlink(target_path: Path, allowed_root: Path) -> None:
    try:
        resolved_target = target_path.resolve()
        resolved_root = allowed_root.resolve()
    except OSError:
        return
    if resolved_root in resolved_target.parents and resolved_target.is_file():
        resolved_target.unlink(missing_ok=True)


def _resolve_storage_file(path_value: str, base_dir: Path) -> Path | None:
    if not path_value:
        return None
    parsed = urlparse(path_value)
    path_name = Path(parsed.path if parsed.scheme or parsed.netloc else path_value).name
    if not path_name:
        return None
    return base_dir / path_name


def get_db_service(request: Request) -> DBService:
    return request.app.state.db_service


@router.get("")
async def list_events(
    db_service: Annotated[DBService, Depends(get_db_service)],
    threat_level: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    return await db_service.list_events(threat_level=threat_level, limit=limit)


@router.get("/{event_id}", responses={404: {"description": NOT_FOUND_DETAIL}})
async def get_event(event_id: str, db_service: Annotated[DBService, Depends(get_db_service)]):
    event = await db_service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    return event


@router.delete("/{event_id}", responses={404: {"description": NOT_FOUND_DETAIL}})
async def delete_event(event_id: str, db_service: Annotated[DBService, Depends(get_db_service)]):
    event = await db_service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

    deleted = await db_service.delete_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

    settings = get_settings()
    clip_root = Path(settings.clip_output_dir)
    thumbnail_root = clip_root.parent / "thumbnails"

    clip_path = _resolve_storage_file(event.get("clip_path", ""), clip_root)
    if clip_path is None:
        clip_path = _resolve_storage_file(event.get("video_url", ""), clip_root)

    thumbnail_path = _resolve_storage_file(event.get("thumbnail_url", ""), thumbnail_root)

    if clip_path is not None:
        _safe_unlink(clip_path, clip_root)
    if thumbnail_path is not None:
        _safe_unlink(thumbnail_path, thumbnail_root)

    return {"status": "deleted", "event_id": event_id}


@router.get(
    "/{event_id}/thumbnail",
    responses={
        404: {"description": THUMBNAIL_NOT_AVAILABLE_DETAIL},
        500: {"description": THUMBNAIL_GENERATION_FAILED_DETAIL},
    },
)
async def get_event_thumbnail(event_id: str, db_service: Annotated[DBService, Depends(get_db_service)]):
    event = await db_service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

    settings = get_settings()
    thumbnail_name = Path(event.get("thumbnail_url", "")).name if event.get("thumbnail_url") else ""
    thumbnail_path = Path(settings.clip_output_dir).parent / "thumbnails" / thumbnail_name if thumbnail_name else None
    if thumbnail_path and thumbnail_path.exists():
        return Response(content=thumbnail_path.read_bytes(), media_type="image/jpeg")

    clip_source = event.get("clip_path") or event.get("video_url", "")
    if not clip_source:
        raise HTTPException(status_code=404, detail=THUMBNAIL_NOT_AVAILABLE_DETAIL)

    clip_path = Path(clip_source)
    if not clip_path.is_absolute():
        clip_path = Path(settings.clip_output_dir) / clip_path.name

    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        raise HTTPException(status_code=404, detail=THUMBNAIL_NOT_AVAILABLE_DETAIL)

    success, frame = capture.read()
    capture.release()
    if not success:
        raise HTTPException(status_code=404, detail=THUMBNAIL_NOT_AVAILABLE_DETAIL)

    success, buffer = cv2.imencode('.jpg', frame)
    if not success:
        raise HTTPException(status_code=500, detail=THUMBNAIL_GENERATION_FAILED_DETAIL)

    return Response(content=buffer.tobytes(), media_type="image/jpeg")
