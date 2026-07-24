import json
import logging
from datetime import datetime

from heiman.database.connector import get_db_connector
from heiman.schema.rule import RuleSuggestion, SuggestionStatus

logger = logging.getLogger(__name__)


class RuleSuggestionRepo:
    def __init__(self):
        self.db_connector = get_db_connector()

    def create(self, suggestion: RuleSuggestion) -> str:
        try:
            self.db_connector.execute_update("""
                INSERT INTO rule_suggestions (
                    suggestion_id, user_id, home_id, name, description,
                    confidence, pattern_type, trigger_device_id, trigger_device_name,
                    action_device_id, action_device_name, rule_data, status,
                    created_at, approved_at, rejected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                suggestion.suggestion_id,
                suggestion.user_id,
                suggestion.home_id,
                suggestion.name,
                suggestion.description,
                suggestion.confidence,
                suggestion.pattern_type,
                suggestion.trigger_device_id,
                suggestion.trigger_device_name,
                suggestion.action_device_id,
                suggestion.action_device_name,
                json.dumps(suggestion.rule_data),
                suggestion.status.value,
                suggestion.created_at.isoformat(),
                suggestion.approved_at.isoformat() if suggestion.approved_at else None,
                suggestion.rejected_at.isoformat() if suggestion.rejected_at else None,
            ))
            logger.info("[DB] Rule suggestion created: id=%s, name=%s", suggestion.suggestion_id, suggestion.name)
            return suggestion.suggestion_id
        except Exception as e:
            logger.error("[DB] Failed to create rule suggestion: %s", e)
            raise

    def get_by_id(self, suggestion_id: str) -> RuleSuggestion | None:
        try:
            with self.db_connector.get_connection() as conn:
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT * FROM rule_suggestions WHERE suggestion_id = ?",
                    (suggestion_id,),
                ).fetchone()
                if row:
                    return self._row_to_suggestion(row)
                return None
        except Exception as e:
            logger.error("[DB] Failed to get rule suggestion: %s", e)
            return None

    def get_by_user(self, user_id: str, status: SuggestionStatus | None = None) -> list[RuleSuggestion]:
        try:
            with self.db_connector.get_connection() as conn:
                cursor = conn.cursor()
                if status:
                    rows = cursor.execute(
                        "SELECT * FROM rule_suggestions WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                        (user_id, status.value),
                    ).fetchall()
                else:
                    rows = cursor.execute(
                        "SELECT * FROM rule_suggestions WHERE user_id = ? ORDER BY created_at DESC",
                        (user_id,),
                    ).fetchall()
                return [self._row_to_suggestion(row) for row in rows]
        except Exception as e:
            logger.error("[DB] Failed to get rule suggestions by user: %s", e)
            return []

    def get_pending(self, user_id: str | None = None) -> list[RuleSuggestion]:
        try:
            with self.db_connector.get_connection() as conn:
                cursor = conn.cursor()
                if user_id:
                    rows = cursor.execute(
                        "SELECT * FROM rule_suggestions WHERE status = 'pending' AND user_id = ? ORDER BY created_at DESC",
                        (user_id,),
                    ).fetchall()
                else:
                    rows = cursor.execute(
                        "SELECT * FROM rule_suggestions WHERE status = 'pending' ORDER BY created_at DESC",
                    ).fetchall()
                return [self._row_to_suggestion(row) for row in rows]
        except Exception as e:
            logger.error("[DB] Failed to get pending rule suggestions: %s", e)
            return []

    def update_status(self, suggestion_id: str, status: SuggestionStatus) -> bool:
        try:
            now = datetime.now().isoformat()
            if status == SuggestionStatus.APPROVED:
                self.db_connector.execute_update("""
                    UPDATE rule_suggestions SET status = ?, approved_at = ?, rejected_at = NULL
                    WHERE suggestion_id = ?
                """, (status.value, now, suggestion_id))
            elif status == SuggestionStatus.REJECTED:
                self.db_connector.execute_update("""
                    UPDATE rule_suggestions SET status = ?, rejected_at = ?, approved_at = NULL
                    WHERE suggestion_id = ?
                """, (status.value, now, suggestion_id))
            elif status == SuggestionStatus.PENDING:
                self.db_connector.execute_update("""
                    UPDATE rule_suggestions SET status = ?, approved_at = NULL, rejected_at = NULL
                    WHERE suggestion_id = ?
                """, (status.value, suggestion_id))
            logger.info("[DB] Rule suggestion status updated: id=%s, status=%s", suggestion_id, status.value)
            return True
        except Exception as e:
            logger.error("[DB] Failed to update rule suggestion status: %s", e)
            return False

    def delete(self, suggestion_id: str) -> bool:
        try:
            self.db_connector.execute_update(
                "DELETE FROM rule_suggestions WHERE suggestion_id = ?",
                (suggestion_id,),
            )
            logger.info("[DB] Rule suggestion deleted: id=%s", suggestion_id)
            return True
        except Exception as e:
            logger.error("[DB] Failed to delete rule suggestion: %s", e)
            return False

    def _row_to_suggestion(self, row) -> RuleSuggestion:
        return RuleSuggestion(
            suggestion_id=row["suggestion_id"],
            user_id=row["user_id"],
            home_id=row["home_id"],
            name=row["name"],
            description=row["description"],
            confidence=row["confidence"],
            pattern_type=row["pattern_type"],
            trigger_device_id=row["trigger_device_id"],
            trigger_device_name=row["trigger_device_name"],
            action_device_id=row["action_device_id"],
            action_device_name=row["action_device_name"],
            rule_data=json.loads(row["rule_data"]) if row["rule_data"] else {},
            status=SuggestionStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            approved_at=datetime.fromisoformat(row["approved_at"]) if row["approved_at"] else None,
            rejected_at=datetime.fromisoformat(row["rejected_at"]) if row["rejected_at"] else None,
        )