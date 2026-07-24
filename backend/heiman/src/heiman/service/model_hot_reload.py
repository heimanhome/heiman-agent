import asyncio
import logging
import time
from typing import Optional, Dict

from heiman.database.connector import get_db_connector

logger = logging.getLogger(__name__)


class ModelHotReloadService:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._poll_interval = 30
        self._last_check_time = 0
        self._known_models: Dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._on_model_change = None

    @property
    def is_running(self) -> bool:
        return self._running and (self._task is not None and not self._task.done())

    def set_callback(self, callback):
        self._on_model_change = callback
        logger.info("[ModelHotReload] Callback registered for model changes")

    def start(self, interval: int = 30):
        if self.is_running:
            logger.info("[ModelHotReload] Service already running")
            return

        self._poll_interval = interval
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("[ModelHotReload] Service started, polling interval=%ds", interval)

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("[ModelHotReload] Service stopped")

    async def _run(self):
        await self._load_current_models()

        while self._running:
            try:
                await asyncio.sleep(self._poll_interval)

                if not self._running:
                    break

                await self._check_for_changes()

            except asyncio.CancelledError:
                logger.info("[ModelHotReload] Task cancelled")
                break
            except Exception as e:
                logger.error("[ModelHotReload] Unexpected error: %s", e, exc_info=True)
                await asyncio.sleep(60)

    async def _load_current_models(self):
        try:
            db = get_db_connector()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, version, type, status, model_path, last_deployed, updated_at
                    FROM models
                    WHERE status = 'deployed'
                """)
                rows = cursor.fetchall()

                for row in rows:
                    model_info = {
                        "id": row["id"],
                        "name": row["name"],
                        "version": row["version"],
                        "type": row["type"],
                        "status": row["status"],
                        "model_path": row["model_path"],
                        "last_deployed": row["last_deployed"],
                        "updated_at": row["updated_at"],
                    }
                    self._known_models[row["id"]] = model_info

            logger.info("[ModelHotReload] Loaded %d deployed models", len(self._known_models))
        except Exception as e:
            logger.error("[ModelHotReload] Failed to load current models: %s", e)

    async def _check_for_changes(self):
        async with self._lock:
            try:
                db = get_db_connector()
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, name, version, type, status, model_path, last_deployed, updated_at
                        FROM models
                    """)
                    rows = cursor.fetchall()

                current_models: Dict[str, dict] = {}
                for row in rows:
                    model_info = {
                        "id": row["id"],
                        "name": row["name"],
                        "version": row["version"],
                        "type": row["type"],
                        "status": row["status"],
                        "model_path": row["model_path"],
                        "last_deployed": row["last_deployed"],
                        "updated_at": row["updated_at"],
                    }
                    current_models[row["id"]] = model_info

                added = []
                removed = []
                changed = []

                for model_id, model_info in current_models.items():
                    if model_id not in self._known_models:
                        if model_info["status"] == "deployed":
                            added.append(model_id)
                    else:
                        known = self._known_models[model_id]
                        if (
                            known["version"] != model_info["version"]
                            or known["status"] != model_info["status"]
                            or known["model_path"] != model_info["model_path"]
                            or known["updated_at"] != model_info["updated_at"]
                        ):
                            changed.append((model_id, known, model_info))

                for model_id in self._known_models:
                    if model_id not in current_models:
                        removed.append(model_id)

                if added:
                    logger.info("[ModelHotReload] New models detected: %s", added)
                    for model_id in added:
                        await self._handle_model_added(current_models[model_id])

                if removed:
                    logger.info("[ModelHotReload] Models removed: %s", removed)
                    for model_id in removed:
                        await self._handle_model_removed(self._known_models[model_id])

                if changed:
                    logger.info("[ModelHotReload] Models changed: %s", [m[0] for m in changed])
                    for model_id, old_info, new_info in changed:
                        await self._handle_model_changed(old_info, new_info)

                self._known_models = current_models
                self._last_check_time = int(time.time() * 1000)

            except Exception as e:
                logger.error("[ModelHotReload] Error checking for changes: %s", e)

    async def _handle_model_added(self, model_info: dict):
        if self._on_model_change:
            try:
                await self._on_model_change("added", model_info)
            except Exception as e:
                logger.error("[ModelHotReload] Failed to handle model added: %s", e)

    async def _handle_model_removed(self, model_info: dict):
        if self._on_model_change:
            try:
                await self._on_model_change("removed", model_info)
            except Exception as e:
                logger.error("[ModelHotReload] Failed to handle model removed: %s", e)

    async def _handle_model_changed(self, old_info: dict, new_info: dict):
        if self._on_model_change:
            try:
                await self._on_model_change("changed", {
                    "old": old_info,
                    "new": new_info,
                })
            except Exception as e:
                logger.error("[ModelHotReload] Failed to handle model changed: %s", e)

    def get_models(self) -> dict:
        return dict(self._known_models)

    def get_model(self, model_id: str) -> Optional[dict]:
        return self._known_models.get(model_id)


_model_hot_reload_service = None


def get_model_hot_reload_service() -> ModelHotReloadService:
    global _model_hot_reload_service
    if _model_hot_reload_service is None:
        _model_hot_reload_service = ModelHotReloadService()
    return _model_hot_reload_service