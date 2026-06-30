import logging

from heiman.database.task_repo import TaskRepo, TaskLinkConflict
from heiman.database.rule_repo import RuleRepo
from heiman.schema.task import (
    TaskCreateRequest,
    TaskLinkAddRequest,
    TaskUpdateRequest,
    TaskFullView,
    TaskLinkEntry,
)

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, rule_repo: RuleRepo | None = None):
        self.repo = TaskRepo()
        self.rule_repo = rule_repo or RuleRepo()

    def create_task(self, req: TaskCreateRequest) -> None:
        self.repo.create_task(task_id=req.task_id, description=req.description)

    def add_link(self, task_id: str, req: TaskLinkAddRequest) -> None:
        self.repo.add_link(task_id, req.kind, req.ref)

    def update_description(self, task_id: str, req: TaskUpdateRequest) -> bool:
        return self.repo.update_description(task_id, req.description)

    def get_full_view(self, task_id: str) -> TaskFullView | None:
        raw = self.repo.get_full_view(task_id)
        if raw is None:
            return None
        return self._to_full_view(raw)

    def list_for_dedupe(self) -> list[TaskFullView]:
        return [self._to_full_view(raw) for raw in self.repo.list_all()]

    def _to_full_view(self, raw: dict) -> TaskFullView:
        return TaskFullView(
            task_id=raw["task_id"],
            description=raw["description"],
            status=raw["status"],
            paused_at=raw["paused_at"],
            created_at=raw["created_at"],
            links=[TaskLinkEntry(**link) for link in raw["links"]],
        )

    def disable_task(self, task_id: str) -> dict:
        return self._toggle_task(task_id, target_status="paused")

    def enable_task(self, task_id: str) -> dict:
        return self._toggle_task(task_id, target_status="active")

    def _toggle_task(self, task_id: str, target_status: str) -> dict:
        meta_result = self.repo.set_status(task_id, target_status)
        if meta_result == "not_found":
            raise TaskLinkConflict(f"task {task_id!r} not found")

        rule_results = []
        for rule_id in self.repo.get_rule_refs(task_id):
            rule = self.rule_repo.get_by_id(rule_id)
            if rule is None:
                rule_results.append(
                    {"rule_id": rule_id, "result": "not_found"}
                )
                continue
            rule.enabled = target_status == "active"
            from heiman.schema.rule import Rule
            updated_rule = Rule(
                rule_id=rule.rule_id,
                name=rule.name,
                description=rule.description,
                enabled=rule.enabled,
                conditions=rule.conditions,
                actions=rule.actions,
                cooldown_minutes=rule.cooldown_minutes,
            )
            ok = self.rule_repo.update(updated_rule)
            rule_results.append(
                {"rule_id": rule_id, "result": "ok" if ok else "fail"}
            )

        full = self.repo.get_full_view(task_id)
        agent_pending = []
        for link in full["links"]:
            if link["kind"] == "cron":
                agent_pending.append(
                    {"kind": "cron", "ref": link["ref"], "action": "disable" if target_status == "paused" else "enable"}
                )

        return {
            "task_id": task_id,
            "status": target_status,
            "backend_synced": {
                "meta_status": meta_result,
                "rules": rule_results,
            },
            "agent_pending": agent_pending,
        }

    def delete_task(self, task_id: str, reason: str = "completed") -> dict | None:
        full = self.repo.get_full_view(task_id)
        if full is None:
            return None

        task_link_count = len(full["links"])
        rule_ids = [link["ref"] for link in full["links"] if link["kind"] == "rule"]
        deleted_rules = []

        for rid in rule_ids:
            if self.rule_repo.delete(rid):
                deleted_rules.append(rid)

        self.repo.delete_task(task_id)

        agent_pending = [
            {"kind": "cron", "ref": link["ref"], "action": "remove"}
            for link in full["links"]
            if link["kind"] == "cron"
        ]

        return {
            "task_id": task_id,
            "backend_synced": {
                "rules_deleted": deleted_rules,
                "task_link_rows_deleted": task_link_count,
            },
            "agent_pending": agent_pending,
        }