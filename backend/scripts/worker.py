"""Durable Redis worker: pops note_ids off the job queue and runs the pipeline.

Usage:
    python scripts/worker.py              # blocking loop (Docker `worker` service)
    python scripts/worker.py --once       # pop and process a single job, then exit

When REDIS_URL is unset, exits with an error — use the API's in-process
BackgroundTasks fallback for zero-infra local dev instead.
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings  # noqa: E402
from app.database import init_db  # noqa: E402
from app.services.job_runner import process_audio_note_job  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("audio_notes.worker")


async def run_once(timeout: int = 30) -> bool:
    """Block up to `timeout`s for one job, process it, return True if work was done."""
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.error("redis package not installed. Run: pip install -r requirements.txt")
        return False

    if not (settings.REDIS_URL or "").strip():
        logger.error("REDIS_URL is not configured. Worker has nothing to consume.")
        return False

    client = aioredis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=5,
        # Must exceed the BLPOP blocking timeout or the client gives up
        # waiting while the server is still (correctly) blocked.
        socket_timeout=timeout + 10,
    )
    try:
        item = await client.blpop(settings.JOB_QUEUE_NAME, timeout=timeout)
    except Exception as e:
        logger.warning(f"Redis BLPOP failed ({e}); will retry on next loop.")
        return False
    finally:
        try:
            await client.aclose()
        except Exception:
            pass

    if not item:
        return False

    _, payload = item
    try:
        data = json.loads(payload)
        note_id = data.get("note_id") if isinstance(data, dict) else None
    except Exception:
        note_id = None
    if not note_id and isinstance(payload, (bytes, str)):
        note_id = payload.decode() if isinstance(payload, bytes) else payload

    if not note_id:
        logger.error(f"Dropping malformed job payload: {payload!r}")
        return True

    logger.info(f"Worker picked up note {note_id}")
    await process_audio_note_job(note_id)
    return True


async def main() -> None:
    once = "--once" in sys.argv
    await init_db()
    logger.info(f"Worker listening on Redis queue '{settings.JOB_QUEUE_NAME}' (once={once})")
    if once:
        await run_once(timeout=5)
        return
    while True:
        try:
            worked = await run_once(timeout=30)
            if not worked:
                continue
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
