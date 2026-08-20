from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.event import EventCreate


class DBService:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.collection = db["events"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("timestamp", -1)])
        await self.collection.create_index([("threat_level", 1), ("timestamp", -1)])

    async def insert_event(self, event: EventCreate) -> str:
        payload = event.model_dump(exclude={"id"}, by_alias=True)
        result = await self.collection.insert_one(payload)
        return str(result.inserted_id)

    async def get_event(self, event_id: str) -> dict[str, Any] | None:
        try:
            object_id = ObjectId(event_id)
        except Exception:
            return None
        document = await self.collection.find_one({"_id": object_id})
        return self._serialize(document) if document else None

    async def list_events(self, threat_level: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if threat_level:
            query["threat_level"] = threat_level
        cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)
        return [self._serialize(document) async for document in cursor]

    async def delete_event(self, event_id: str) -> bool:
        try:
            object_id = ObjectId(event_id)
        except Exception:
            return False
        result = await self.collection.delete_one({"_id": object_id})
        return result.deleted_count > 0

    @staticmethod
    def _serialize(document: dict[str, Any] | None) -> dict[str, Any]:
        if not document:
            return {}
        document["_id"] = str(document["_id"])

        timestamp = document.get("timestamp")
        if isinstance(timestamp, datetime):
            # MongoDB often returns naive UTC datetimes unless tz-aware options are enabled.
            normalized = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)
            document["timestamp"] = normalized.isoformat()

        return document
