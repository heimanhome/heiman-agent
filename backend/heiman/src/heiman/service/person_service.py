import logging

from heiman.database.person_repo import PersonRepo, UNSET
from heiman.schema.person import Person
from heiman.middleware.exceptions import BadRequestException, ConflictException, ResourceNotFoundException

logger = logging.getLogger(__name__)


class PersonService:
    def __init__(self, person_repo: PersonRepo | None = None, api_client=None):
        self._person_repo = person_repo or PersonRepo()
        self._api_client = api_client

    def set_api_client(self, api_client):
        self._api_client = api_client

    def list_persons(self, home_id: str | None = None) -> list[Person]:
        if home_id:
            return self._person_repo.get_by_home_id(home_id)
        return self._person_repo.get_all()

    def get_person(self, person_id: str) -> Person | None:
        return self._person_repo.get_by_id(person_id)

    def exists(self, person_id: str) -> bool:
        return self._person_repo.exists(person_id)

    def create_person(self, name: str, role: str | None, **kwargs) -> str:
        name = (name or "").strip()
        if not name:
            raise BadRequestException("name 不可为空")
        return self._person_repo.create(name, role, **kwargs)

    def update_person(
        self, person_id: str, name: str | None = None, role: object = UNSET, **kwargs
    ) -> None:
        if not self._person_repo.exists(person_id):
            raise ResourceNotFoundException(f"Person '{person_id}' not found")
        if name is not None:
            name = name.strip()
            if not name:
                raise BadRequestException("name 不可为空")
        self._person_repo.update(person_id, name, role, **kwargs)

    def delete_person(self, person_id: str) -> None:
        if not self._person_repo.exists(person_id):
            raise ResourceNotFoundException(f"Person '{person_id}' not found")
        self._person_repo.delete(person_id)
        logger.info("Person deleted: id=%s", person_id)

    async def sync_from_heiman(self, home_id: str) -> dict:
        if not self._api_client:
            raise BadRequestException("海曼 API 客户端未初始化，请先登录")

        members = await self._api_client.get_home_members(home_id)
        if not members:
            return {"synced": 0, "added": 0, "updated": 0, "members": []}

        added = 0
        updated = 0
        synced_ids = []

        for member in members:
            user_id = str(member.get("userId") or member.get("user_id") or "")
            if not user_id:
                continue

            user_name = (
                member.get("userName")
                or member.get("user_name")
                or member.get("aliasName")
                or member.get("alias_name")
                or member.get("nickname")
                or "未知成员"
            )
            role = member.get("role")
            is_home_root = member.get("isHomeRoot") or member.get("is_home_root") or 0
            status = member.get("status") or 1

            role_str = None
            if role == 0:
                role_str = "owner"
            elif role == 1:
                role_str = "admin"
            elif role == 2:
                role_str = "member"

            existing = self._person_repo.get_by_user_id(user_id)
            if existing:
                update_data = {}
                if user_name and user_name != existing.name:
                    update_data["name"] = user_name
                if role_str != existing.role:
                    update_data["role"] = role_str
                if is_home_root != existing.is_home_root:
                    update_data["is_home_root"] = is_home_root
                if status != existing.status:
                    update_data["status"] = status

                extra_fields = {
                    "home_id": home_id,
                    "home_name": member.get("homeName") or member.get("home_name"),
                    "user_account": member.get("userAccount") or member.get("user_account"),
                    "alias_name": member.get("aliasName") or member.get("alias_name"),
                    "head_img_url": member.get("headImgUrl") or member.get("head_img_url"),
                    "role_type": role,
                    "remark": member.get("remark"),
                }
                update_data.update(extra_fields)

                if update_data:
                    self._person_repo.update(existing.id, **update_data)
                    updated += 1
                synced_ids.append(existing.id)
            else:
                person_id = self._person_repo.create(
                    user_name,
                    role_str,
                    user_id=user_id,
                    home_id=home_id,
                    home_name=member.get("homeName") or member.get("home_name"),
                    user_account=member.get("userAccount") or member.get("user_account"),
                    alias_name=member.get("aliasName") or member.get("alias_name"),
                    head_img_url=member.get("headImgUrl") or member.get("head_img_url"),
                    is_home_root=is_home_root,
                    role_type=role,
                    status=status,
                    remark=member.get("remark"),
                )
                added += 1
                synced_ids.append(person_id)

        logger.info(
            "Sync persons from Heiman: home_id=%s, added=%d, updated=%d",
            home_id, added, updated
        )

        persons = self._person_repo.get_by_home_id(home_id)
        return {
            "synced": len(synced_ids),
            "added": added,
            "updated": updated,
            "members": [p.model_dump() for p in persons],
        }
