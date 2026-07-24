from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4
import logging
import json

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel

from heiman.database.rule_repo import RuleRepo
from heiman.database.rule_suggestion_repo import RuleSuggestionRepo
from heiman.dependencies import get_rule_repo
from heiman.schema.rule import Rule, RuleAction, RuleCondition, RuleActionType, SensorType, SuggestionStatus
from heiman.ai.smart_rule_generator import SmartRuleGenerator

router = APIRouter(prefix="/rules", tags=["rules"])
logger = logging.getLogger(__name__)


class RuleCreateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool = True
    cooldown: int | None = None
    cooldown_minutes: int | None = None
    trigger: dict | None = None
    action: dict | None = None
    home_id: str | None = None


@router.get("", response_model=dict)
async def get_rules(
    enabled_only: Annotated[bool, Query()] = False,
    home_id: Annotated[str | None, Query()] = None,
    rule_repo: RuleRepo = Depends(get_rule_repo),
):
    """获取规则列表"""
    try:
        rules = rule_repo.get_all(enabled_only=enabled_only, home_id=home_id)
        logger.info("Listed %d rules (enabled_only=%s)", len(rules), enabled_only)
        return {"success": True, "data": [r.model_dump() for r in rules]}
    except Exception as e:
        logger.error("Failed to list rules: %s", e)
        return {"success": False, "data": [], "message": str(e)}


@router.get("/{rule_id}", response_model=dict)
async def get_rule(
    rule_id: str,
    rule_repo: RuleRepo = Depends(get_rule_repo),
):
    """获取单个规则"""
    try:
        rule = rule_repo.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        logger.debug("Got rule: id=%s, name=%s", rule_id, rule.name)
        return {"success": True, "data": rule.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get rule %s: %s", rule_id, e)
        return {"success": False, "message": str(e)}


@router.post("", response_model=dict)
async def create_rule(
    request: Request,
    name: Annotated[str | None, Query()] = None,
    description: Annotated[str | None, Query()] = None,
    enabled: Annotated[bool | None, Query()] = True,
    cooldown_minutes: Annotated[int | None, Query(ge=0)] = 5,
    trigger: Annotated[str | None, Query(description="JSON string for trigger condition")] = None,
    action_config: Annotated[str | None, Query(description="JSON string for action config")] = None,
    rule_repo: RuleRepo = Depends(get_rule_repo),
):
    """创建规则

    支持两种方式:
    1. 使用 query params (trigger 和 action_config JSON 字符串)
    2. 通过 JSON body 创建
    """
    try:
        body_data = None
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body_data = await request.json()
            except Exception:
                pass

        conditions = []
        actions = []
        rule_name = name
        rule_description = description
        rule_enabled = enabled if enabled is not None else True
        rule_cooldown = cooldown_minutes if cooldown_minutes is not None else 5
        rule_home_id = None

        if body_data:
            rule_name = body_data.get("name", rule_name)
            rule_description = body_data.get("description", rule_description)
            rule_enabled = body_data.get("enabled", rule_enabled)
            rule_cooldown = body_data.get("cooldown_minutes") or body_data.get("cooldown") or rule_cooldown
            rule_home_id = body_data.get("home_id")

            trigger_data = body_data.get("trigger")
            if trigger_data and isinstance(trigger_data, dict):
                sensor_type_str = trigger_data.get("property", trigger_data.get("sensor_type", "CO"))
                try:
                    sensor_type = SensorType(str(sensor_type_str).upper())
                except ValueError:
                    sensor_type = SensorType.CO

                conditions.append(RuleCondition(
                    did=trigger_data.get("did"),
                    sensor_type=sensor_type,
                    operator=trigger_data.get("operator", ">="),
                    threshold=trigger_data.get("threshold"),
                ))
                if not rule_home_id:
                    rule_home_id = trigger_data.get("home_id")

            action_data = body_data.get("action")
            if action_data and isinstance(action_data, dict):
                action_type_str = action_data.get("type", "notification")
                if action_type_str == "notification":
                    action_type = RuleActionType.ALERT
                else:
                    try:
                        action_type = RuleActionType(action_type_str)
                    except ValueError:
                        action_type = RuleActionType.ALERT

                actions.append(RuleAction(
                    action_type=action_type,
                    payload={
                        "title": action_data.get("title", ""),
                        "message": action_data.get("message", ""),
                    },
                ))

        if trigger:
            try:
                trigger_data = json.loads(trigger)
                if isinstance(trigger_data, dict):
                    if not rule_home_id:
                        rule_home_id = trigger_data.get("home_id")
                    conditions.append(RuleCondition(
                        did=trigger_data.get("did"),
                        sensor_type=SensorType.CO,
                        operator=trigger_data.get("operator", ">="),
                        threshold=trigger_data.get("threshold"),
                    ))
            except json.JSONDecodeError:
                pass

        if action_config:
            try:
                action_data = json.loads(action_config)
                if isinstance(action_data, dict):
                    actions.append(RuleAction(
                        action_type=RuleActionType.ALERT,
                        payload={
                            "title": action_data.get("title", ""),
                            "message": action_data.get("message", ""),
                        },
                    ))
            except json.JSONDecodeError:
                pass

        if not rule_name:
            rule_name = f"规则_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if rule_repo.exists_by_name(rule_name):
            raise HTTPException(status_code=400, detail="Rule name already exists")

        rule = Rule(
            rule_id=str(uuid4()),
            name=rule_name,
            description=rule_description,
            enabled=rule_enabled,
            conditions=conditions,
            actions=actions,
            cooldown_minutes=rule_cooldown,
            home_id=rule_home_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        rule_repo.create(rule)
        logger.info("Created rule: id=%s, name=%s", rule.rule_id, rule_name)
        return {"success": True, "data": rule.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create rule: %s", e)
        return {"success": False, "message": str(e)}


@router.put("/{rule_id}", response_model=dict)
async def update_rule(
    rule_id: str,
    name: Annotated[str | None, Query()] = None,
    description: Annotated[str | None, Query()] = None,
    enabled: Annotated[bool | None, Query()] = None,
    cooldown_minutes: Annotated[int | None, Query(ge=0)] = None,
    rule_repo: RuleRepo = Depends(get_rule_repo),
):
    """更新规则"""
    try:
        rule = rule_repo.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        if name and name != rule.name:
            if rule_repo.exists_by_name(name, exclude_id=rule_id):
                raise HTTPException(status_code=400, detail="Rule name already exists")
            rule.name = name
        
        if description is not None:
            rule.description = description
        
        if enabled is not None:
            rule.enabled = enabled
        
        if cooldown_minutes is not None:
            rule.cooldown_minutes = cooldown_minutes
        
        rule.updated_at = datetime.now()
        rule_repo.update(rule)
        
        logger.info("Updated rule: id=%s", rule_id)
        return {"success": True, "data": rule.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update rule %s: %s", rule_id, e)
        return {"success": False, "message": str(e)}


@router.delete("/{rule_id}", response_model=dict)
async def delete_rule(
    rule_id: str,
    rule_repo: RuleRepo = Depends(get_rule_repo),
):
    """删除规则"""
    try:
        if not rule_repo.get_by_id(rule_id):
            raise HTTPException(status_code=404, detail="Rule not found")
        
        success = rule_repo.delete(rule_id)
        logger.info("Deleted rule: id=%s, success=%s", rule_id, success)
        return {"success": True, "data": {"rule_id": rule_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete rule %s: %s", rule_id, e)
        return {"success": False, "message": str(e)}


@router.post("/{rule_id}/conditions", response_model=dict)
async def add_condition(
    rule_id: str,
    sensor_type: Annotated[SensorType, Query()],
    operator: Annotated[str, Query()],
    threshold: Annotated[float | int, Query()],
    did: Annotated[str, Query()] = "",
    window_seconds: Annotated[int | None, Query()] = None,
    rule_repo: RuleRepo = Depends(get_rule_repo),
):
    """添加规则条件"""
    try:
        rule = rule_repo.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        condition = RuleCondition(
            did=did,
            sensor_type=sensor_type,
            operator=operator,
            threshold=threshold,
            window_seconds=window_seconds,
        )
        
        rule.conditions.append(condition)
        rule.updated_at = datetime.now()
        rule_repo.update(rule)
        
        logger.info("Added condition to rule: id=%s, sensor_type=%s", rule_id, sensor_type)
        return {"success": True, "data": rule.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to add condition to rule %s: %s", rule_id, e)
        return {"success": False, "message": str(e)}


@router.post("/{rule_id}/actions", response_model=dict)
async def add_action(
    rule_id: str,
    action_type: Annotated[RuleActionType, Query()],
    payload: Annotated[str, Query()] = "{}",
    rule_repo: RuleRepo = Depends(get_rule_repo),
):
    """添加规则动作"""
    try:
        rule = rule_repo.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        try:
            payload_dict = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid payload JSON")
        
        action = RuleAction(
            action_type=action_type,
            payload=payload_dict,
        )
        
        rule.actions.append(action)
        rule.updated_at = datetime.now()
        rule_repo.update(rule)
        
        logger.info("Added action to rule: id=%s, action_type=%s", rule_id, action_type)
        return {"success": True, "data": rule.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to add action to rule %s: %s", rule_id, e)
        return {"success": False, "message": str(e)}


@router.get("/suggestions", response_model=dict)
async def get_rule_suggestions(
    user_id: Annotated[str, Query()] = "default",
    status: Annotated[str | None, Query()] = None,
):
    """获取规则建议列表"""
    try:
        suggestion_repo = RuleSuggestionRepo()
        if status:
            try:
                status_enum = SuggestionStatus(status)
                suggestions = suggestion_repo.get_by_user(user_id, status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid status value")
        else:
            suggestions = suggestion_repo.get_by_user(user_id)

        logger.info("Listed %d rule suggestions for user %s", len(suggestions), user_id)
        return {"success": True, "data": [s.model_dump() for s in suggestions]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get rule suggestions: %s", e)
        return {"success": False, "message": str(e)}


@router.post("/suggestions/{suggestion_id}/approve", response_model=dict)
async def approve_rule_suggestion(suggestion_id: str):
    """批准规则建议并创建规则"""
    try:
        generator = SmartRuleGenerator()
        rule = await generator.approve_suggestion(suggestion_id)

        if not rule:
            raise HTTPException(status_code=404, detail="Suggestion not found or not pending")

        logger.info("Approved rule suggestion: %s", rule.name)
        return {"success": True, "data": rule.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to approve rule suggestion: %s", e)
        return {"success": False, "message": str(e)}


@router.post("/suggestions/{suggestion_id}/reject", response_model=dict)
async def reject_rule_suggestion(suggestion_id: str):
    """拒绝规则建议"""
    try:
        generator = SmartRuleGenerator()
        success = await generator.reject_suggestion(suggestion_id)

        if not success:
            raise HTTPException(status_code=404, detail="Suggestion not found")

        logger.info("Rejected rule suggestion: %s", suggestion_id)
        return {"success": True, "message": "Suggestion rejected"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reject rule suggestion: %s", e)
        return {"success": False, "message": str(e)}


@router.post("/suggestions/generate", response_model=dict)
async def generate_rule_suggestions(
    user_id: Annotated[str, Query()] = "default",
    home_id: Annotated[str, Query()] = "",
):
    """手动触发规则建议生成"""
    try:
        generator = SmartRuleGenerator()
        suggestions = await generator.generate_rule_suggestions(user_id, home_id)

        logger.info("Generated %d rule suggestions for user %s", len(suggestions), user_id)
        return {"success": True, "data": [s.model_dump() for s in suggestions]}
    except Exception as e:
        logger.error("Failed to generate rule suggestions: %s", e)
        return {"success": False, "message": str(e)}
