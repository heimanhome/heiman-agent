import json
import logging

from heiman.database.connector import get_db_connector
from heiman.schema.rule import Rule

logger = logging.getLogger(__name__)


class RuleRepo:
    def __init__(self):
        self.db_connector = get_db_connector()

    def create(self, rule: Rule) -> str:
        try:
            self.db_connector.execute_update("""
                INSERT INTO rules (
                    rule_id, name, description, enabled, conditions, actions,
                    cooldown_minutes, home_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule.rule_id,
                rule.name,
                rule.description,
                1 if rule.enabled else 0,
                json.dumps([c.model_dump() for c in rule.conditions]),
                json.dumps([a.model_dump() for a in rule.actions]),
                rule.cooldown_minutes,
                rule.home_id,
                rule.created_at.isoformat(),
                rule.updated_at.isoformat(),
            ))
            logger.info("[DB] Rule created: rule_id=%s, name=%s", rule.rule_id, rule.name)
            return rule.rule_id
        except Exception as e:
            logger.error("[DB] Failed to create rule: rule_id=%s, error=%s", rule.rule_id, e)
            raise

    def get_by_id(self, rule_id: str) -> Rule | None:
        try:
            results = self.db_connector.execute_query("""
                SELECT * FROM rules WHERE rule_id = ?
            """, (rule_id,))
            
            if not results:
                return None
            
            row_dict = results[0]
            return Rule(
                rule_id=row_dict["rule_id"],
                name=row_dict["name"],
                description=row_dict["description"],
                enabled=bool(row_dict["enabled"]),
                conditions=json.loads(row_dict["conditions"]) if row_dict["conditions"] else [],
                actions=json.loads(row_dict["actions"]) if row_dict["actions"] else [],
                cooldown_minutes=row_dict["cooldown_minutes"],
                home_id=row_dict.get("home_id"),
            )
        except Exception as e:
            logger.error("[DB] Failed to get rule: rule_id=%s, error=%s", rule_id, e)
            raise

    def get_all(self, enabled_only: bool = False, home_id: str | None = None) -> list[Rule]:
        try:
            query = "SELECT * FROM rules WHERE 1=1"
            params: list = []
            
            if enabled_only:
                query += " AND enabled = 1"
            
            if home_id:
                query += " AND home_id = ?"
                params.append(home_id)
            
            query += " ORDER BY updated_at DESC"
            
            results = self.db_connector.execute_query(query, tuple(params))
            
            result = []
            for row in results:
                row_dict = dict(row)
                conditions = json.loads(row_dict["conditions"]) if row_dict["conditions"] else []
                actions = json.loads(row_dict["actions"]) if row_dict["actions"] else []
                
                result.append(Rule(
                    rule_id=row_dict["rule_id"],
                    name=row_dict["name"],
                    description=row_dict["description"],
                    enabled=bool(row_dict["enabled"]),
                    conditions=conditions,
                    actions=actions,
                    cooldown_minutes=row_dict["cooldown_minutes"],
                    home_id=row_dict.get("home_id"),
                ))
            
            logger.debug("[DB] Retrieved %d rules", len(result))
            return result
        except Exception as e:
            logger.error("[DB] Failed to get all rules: error=%s", e)
            raise

    def update(self, rule: Rule) -> bool:
        try:
            count = self.db_connector.execute_update("""
                UPDATE rules SET
                    name = ?, description = ?, enabled = ?, conditions = ?, actions = ?,
                    cooldown_minutes = ?, home_id = ?, updated_at = ?
                WHERE rule_id = ?
            """, (
                rule.name,
                rule.description,
                1 if rule.enabled else 0,
                json.dumps([c.model_dump() for c in rule.conditions]),
                json.dumps([a.model_dump() for a in rule.actions]),
                rule.cooldown_minutes,
                rule.home_id,
                rule.updated_at.isoformat(),
                rule.rule_id,
            ))
            
            success = count > 0
            if success:
                logger.info("[DB] Rule updated: rule_id=%s", rule.rule_id)
            return success
        except Exception as e:
            logger.error("[DB] Failed to update rule: rule_id=%s, error=%s", rule.rule_id, e)
            raise

    def delete(self, rule_id: str) -> bool:
        try:
            count = self.db_connector.execute_update("""
                DELETE FROM rules WHERE rule_id = ?
            """, (rule_id,))
            
            success = count > 0
            if success:
                logger.info("[DB] Rule deleted: rule_id=%s", rule_id)
            return success
        except Exception as e:
            logger.error("[DB] Failed to delete rule: rule_id=%s, error=%s", rule_id, e)
            raise

    def exists_by_name(self, name: str, exclude_id: str | None = None) -> bool:
        try:
            query = "SELECT COUNT(*) as count FROM rules WHERE name = ?"
            params = [name]
            
            if exclude_id:
                query += " AND rule_id != ?"
                params.append(exclude_id)
            
            results = self.db_connector.execute_query(query, tuple(params))
            return results[0]["count"] > 0
        except Exception as e:
            logger.error("[DB] Failed to check rule existence: name=%s, error=%s", name, e)
            raise

    def count_all(self) -> int:
        try:
            results = self.db_connector.execute_query("SELECT COUNT(*) as count FROM rules")
            return int(results[0]["count"])
        except Exception as e:
            logger.error("[DB] Failed to count all rules: error=%s", e)
            raise

    def count_enabled(self) -> int:
        try:
            results = self.db_connector.execute_query("SELECT COUNT(*) as count FROM rules WHERE enabled = 1")
            return int(results[0]["count"])
        except Exception as e:
            logger.error("[DB] Failed to count enabled rules: error=%s", e)
            raise


_rule_repo_instance = None


def get_rule_repo() -> RuleRepo:
    global _rule_repo_instance
    if _rule_repo_instance is None:
        _rule_repo_instance = RuleRepo()
    return _rule_repo_instance