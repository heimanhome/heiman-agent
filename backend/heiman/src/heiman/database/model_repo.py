import logging
from typing import Optional
from datetime import datetime

from heiman.database.connector import get_db_connector

logger = logging.getLogger(__name__)


class ModelRepo:
    def __init__(self):
        self._db = get_db_connector()

    def get_all(self) -> list[dict]:
        try:
            rows = self._db.execute_query(
                "SELECT * FROM models ORDER BY name"
            )
            result = []
            for row in rows:
                row_dict = dict(row)
                row_dict["lastDeployed"] = row_dict.pop("last_deployed", "-")
                result.append(row_dict)
            return result
        except Exception as e:
            logger.error("[MODEL] Failed to get all models: %s", e)
            raise

    def get_by_id(self, model_id: str) -> Optional[dict]:
        try:
            rows = self._db.execute_query(
                "SELECT * FROM models WHERE id = ?",
                (model_id,),
            )
            if rows:
                row_dict = dict(rows[0])
                row_dict["lastDeployed"] = row_dict.pop("last_deployed", "-")
                return row_dict
            return None
        except Exception as e:
            logger.error("[MODEL] Failed to get model by id: %s", e)
            raise

    def create(self, model_data: dict) -> None:
        try:
            now = datetime.now().isoformat()
            self._db.execute_update(
                """
                INSERT INTO models (id, name, version, type, status, description, accuracy, model_path, last_deployed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_data.get("id"),
                    model_data.get("name"),
                    model_data.get("version"),
                    model_data.get("type"),
                    model_data.get("status"),
                    model_data.get("description"),
                    model_data.get("accuracy", 0),
                    model_data.get("model_path"),
                    model_data.get("last_deployed"),
                    now,
                    now,
                ),
            )
            logger.info("[MODEL] Created model: id=%s, name=%s", model_data.get("id"), model_data.get("name"))
        except Exception as e:
            logger.error("[MODEL] Failed to create model: %s", e)
            raise

    def update(self, model_id: str, model_data: dict) -> None:
        try:
            now = datetime.now().isoformat()
            update_fields = []
            params = []

            if "name" in model_data:
                update_fields.append("name = ?")
                params.append(model_data["name"])
            if "version" in model_data:
                update_fields.append("version = ?")
                params.append(model_data["version"])
            if "type" in model_data:
                update_fields.append("type = ?")
                params.append(model_data["type"])
            if "status" in model_data:
                update_fields.append("status = ?")
                params.append(model_data["status"])
            if "description" in model_data:
                update_fields.append("description = ?")
                params.append(model_data["description"])
            if "accuracy" in model_data:
                update_fields.append("accuracy = ?")
                params.append(model_data["accuracy"])
            if "model_path" in model_data:
                update_fields.append("model_path = ?")
                params.append(model_data["model_path"])
            if "last_deployed" in model_data:
                update_fields.append("last_deployed = ?")
                params.append(model_data["last_deployed"])

            update_fields.append("updated_at = ?")
            params.append(now)
            params.append(model_id)

            query = "UPDATE models SET " + ", ".join(update_fields) + " WHERE id = ?"
            self._db.execute_update(query, tuple(params))
            logger.info("[MODEL] Updated model: id=%s", model_id)
        except Exception as e:
            logger.error("[MODEL] Failed to update model: %s", e)
            raise

    def delete(self, model_id: str) -> bool:
        try:
            rows_affected = self._db.execute_update(
                "DELETE FROM models WHERE id = ?",
                (model_id,),
            )
            logger.info("[MODEL] Deleted model: id=%s, rows_affected=%d", model_id, rows_affected)
            return rows_affected > 0
        except Exception as e:
            logger.error("[MODEL] Failed to delete model: %s", e)
            raise

    def deploy(self, model_id: str) -> bool:
        try:
            model = self.get_by_id(model_id)
            if not model:
                return False

            if model["status"] == "training":
                return False

            now = datetime.now().strftime("%Y-%m-%d")
            self.update(model_id, {"status": "deployed", "last_deployed": now})
            logger.info("[MODEL] Deployed model: id=%s", model_id)
            return True
        except Exception as e:
            logger.error("[MODEL] Failed to deploy model: %s", e)
            raise

    def stop(self, model_id: str) -> bool:
        try:
            model = self.get_by_id(model_id)
            if not model:
                return False

            self.update(model_id, {"status": "not_deployed"})
            logger.info("[MODEL] Stopped model: id=%s", model_id)
            return True
        except Exception as e:
            logger.error("[MODEL] Failed to stop model: %s", e)
            raise

    def get_active_model(self) -> Optional[dict]:
        try:
            rows = self._db.execute_query(
                "SELECT * FROM models WHERE status = 'deployed' ORDER BY last_deployed DESC LIMIT 1"
            )
            if rows:
                row_dict = dict(rows[0])
                row_dict["lastDeployed"] = row_dict.pop("last_deployed", "-")
                return row_dict
            return None
        except Exception as e:
            logger.error("[MODEL] Failed to get active model: %s", e)
            raise


_model_repo = None


def get_model_repo() -> ModelRepo:
    global _model_repo
    if _model_repo is None:
        _model_repo = ModelRepo()
    return _model_repo
