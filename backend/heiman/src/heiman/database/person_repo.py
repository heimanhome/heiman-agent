import logging
import uuid
from typing import Any

from heiman.database.connector import get_db_connector
from heiman.schema.person import Person

logger = logging.getLogger(__name__)

UNSET: Any = object()


class PersonRepo:
    def __init__(self):
        self.db_connector = get_db_connector()

    def _row_to_person(self, row: dict[str, Any]) -> Person:
        return Person(
            id=row["id"],
            name=row["name"],
            role=row.get("role"),
            user_id=row.get("user_id"),
            home_id=row.get("home_id"),
            home_name=row.get("home_name"),
            user_account=row.get("user_account"),
            alias_name=row.get("alias_name"),
            head_img_url=row.get("head_img_url"),
            is_home_root=row.get("is_home_root"),
            role_type=row.get("role_type"),
            status=row.get("status"),
            remark=row.get("remark"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def get_all(self) -> list[Person]:
        rows = self.db_connector.execute_query(
            "SELECT * FROM person ORDER BY is_home_root DESC, role_type ASC, created_at ASC"
        )
        return [self._row_to_person(r) for r in rows]

    def get_by_home_id(self, home_id: str) -> list[Person]:
        rows = self.db_connector.execute_query(
            "SELECT * FROM person WHERE home_id = ? ORDER BY is_home_root DESC, role_type ASC, created_at ASC",
            (home_id,),
        )
        return [self._row_to_person(r) for r in rows]

    def get_by_id(self, person_id: str) -> Person | None:
        rows = self.db_connector.execute_query(
            "SELECT * FROM person WHERE id = ?", (person_id,)
        )
        return self._row_to_person(rows[0]) if rows else None

    def get_by_user_id(self, user_id: str) -> Person | None:
        rows = self.db_connector.execute_query(
            "SELECT * FROM person WHERE user_id = ?", (user_id,)
        )
        return self._row_to_person(rows[0]) if rows else None

    def exists(self, person_id: str) -> bool:
        rows = self.db_connector.execute_query(
            "SELECT id FROM person WHERE id = ?", (person_id,)
        )
        return bool(rows)

    def exists_by_user_id(self, user_id: str) -> bool:
        rows = self.db_connector.execute_query(
            "SELECT id FROM person WHERE user_id = ?", (user_id,)
        )
        return bool(rows)

    def exists_by_name(self, name: str, exclude_id: str | None = None) -> bool:
        if exclude_id:
            rows = self.db_connector.execute_query(
                "SELECT id FROM person WHERE name = ? AND id != ?", (name, exclude_id)
            )
        else:
            rows = self.db_connector.execute_query(
                "SELECT id FROM person WHERE name = ?", (name,)
            )
        return bool(rows)

    def create(self, name: str, role: str | None, **kwargs) -> str:
        assert name and name.strip(), "person.name 不可为空"
        person_id = str(uuid.uuid4())
        from datetime import datetime
        now = datetime.now().isoformat()
        fields = ["id", "name", "role", "created_at", "updated_at"]
        values = [person_id, name, role, now, now]
        placeholders = ["?", "?", "?", "?", "?"]
        for key in ["user_id", "home_id", "home_name", "user_account", "alias_name",
                    "head_img_url", "is_home_root", "role_type", "status", "remark"]:
            if key in kwargs and kwargs[key] is not None:
                fields.append(key)
                values.append(kwargs[key])
                placeholders.append("?")
        self.db_connector.execute_update(
            f"INSERT INTO person ({', '.join(fields)}) VALUES ({', '.join(placeholders)})",
            tuple(values),
        )
        logger.info("Person created: id=%s name=%s", person_id, name)
        return person_id

    def update(self, person_id: str, name: str | None = None, role: object = UNSET, **kwargs) -> bool:
        fields = []
        params = []
        if name is not None:
            assert name.strip(), "person.name 不可为空"
            fields.append("name = ?")
            params.append(name)
        if role is not UNSET:
            fields.append("role = ?")
            params.append(role)
        for key in ["user_id", "home_id", "home_name", "user_account", "alias_name",
                    "head_img_url", "is_home_root", "role_type", "status", "remark"]:
            if key in kwargs:
                fields.append(f"{key} = ?")
                params.append(kwargs[key])
        if not fields:
            return False
        from datetime import datetime
        fields.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(person_id)
        affected = self.db_connector.execute_update(
            f"UPDATE person SET {', '.join(fields)} WHERE id = ?",
            tuple(params),
        )
        return affected > 0

    def upsert_by_user_id(self, user_id: str, name: str, **kwargs) -> str:
        existing = self.get_by_user_id(user_id)
        if existing:
            update_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            if name and name != existing.name:
                update_kwargs["name"] = name
            if update_kwargs:
                self.update(existing.id, **update_kwargs)
            return existing.id
        else:
            return self.create(name, kwargs.get("role"), user_id=user_id, **kwargs)

    def delete(self, person_id: str) -> bool:
        affected = self.db_connector.execute_update(
            "DELETE FROM person WHERE id = ?", (person_id,)
        )
        return affected > 0
