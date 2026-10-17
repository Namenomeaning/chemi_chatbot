import base64
import logging
import re

logger = logging.getLogger(__name__)
AUDIO_ID = re.compile(r"^audio/[0-9a-f]{32}$")


async def load_audio(bucket, audio_id: str | None) -> str | None:
    """Read only application-generated keys. Missing optional audio does not fail a chat."""
    if bucket is None or not audio_id or not AUDIO_ID.fullmatch(audio_id):
        return None
    try:
        obj = await bucket.get(audio_id)
        if obj is None:
            return None
        return base64.b64encode(bytes(await obj.arrayBuffer())).decode()
    except Exception as exc:
        logger.warning("audio_unavailable exception_type=%s", type(exc).__name__)
        return None
