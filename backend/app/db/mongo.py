import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings

_client: AsyncIOMotorClient | None = None
logger = logging.getLogger("app.db")


async def connect_mongo() -> AsyncIOMotorDatabase:
    global _client
    settings = get_settings()
    if _client is not None:
        return _client[settings.mongodb_db]

    # Try configured URI first
    try:
        client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=4000)
        await client.admin.command("ping")
        _client = client
        logger.info("Connected to MongoDB with configured credentials")
        return _client[settings.mongodb_db]
    except Exception as exc:
        err_msg = str(exc).lower()
        # If credentials failed or database is running without auth, attempt without credentials
        if "auth" in err_msg or "credential" in err_msg or "authenticating" in err_msg:
            try:
                parts = settings.mongodb_uri.split("@")
                if len(parts) > 1:
                    unauth_uri = "mongodb://" + parts[-1].split("?")[0]
                    logger.warning(
                        "Authentication rejected by MongoDB. Attempting fallback to unauthenticated URI: %s",
                        unauth_uri,
                    )
                    client = AsyncIOMotorClient(unauth_uri, serverSelectionTimeoutMS=4000)
                    await client.admin.command("ping")
                    _client = client
                    logger.info("Connected to MongoDB via unauthenticated fallback")
                    return _client[settings.mongodb_db]
            except Exception as fallback_exc:
                logger.warning("Unauthenticated fallback also failed: %s", fallback_exc)

        # Fall back to standard client instance and let caller retry
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        return _client[settings.mongodb_db]


async def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
