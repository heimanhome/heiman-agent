import logging
import asyncio
from datetime import datetime, timedelta
from typing import Any

import httpx

from heiman.database.rule_repo import RuleRepo
from heiman.schema.sensor import SensorData, SensorEvent, SensorType
from heiman.schema.rule import Rule, RuleAction, RuleActionType, RuleCondition

logger = logging.getLogger(__name__)


class RuleEngine:
    def __init__(self):
        self._rule_repo = RuleRepo()
        self._last_triggered: dict[str, datetime] = {}
        self._action_idempotency: dict[str, datetime] = {}
    
    def evaluate(self, sensor_data: SensorData) -> list[RuleAction]:
        actions: list[RuleAction] = []
        rules = self._rule_repo.get_all(enabled_only=True)
        
        for rule in rules:
            if self._check_cooldown(rule):
                continue
            
            if self._evaluate_rule(rule, sensor_data):
                actions.extend(rule.actions)
                self._last_triggered[rule.rule_id] = datetime.now()
                logger.info("Rule triggered: %s (%s)", rule.name, rule.rule_id)
        
        return actions
    
    def _check_cooldown(self, rule: Rule) -> bool:
        last_time = self._last_triggered.get(rule.rule_id)
        if not last_time:
            return False
        
        cooldown = timedelta(minutes=rule.cooldown_minutes)
        return datetime.now() - last_time < cooldown
    
    def _evaluate_rule(self, rule: Rule, sensor_data: SensorData) -> bool:
        if not rule.conditions:
            return False
        
        all_conditions_met = True
        for condition in rule.conditions:
            if not self._evaluate_condition(condition, sensor_data):
                all_conditions_met = False
                break
        
        return all_conditions_met
    
    def _validate_condition(self, condition: RuleCondition) -> bool:
        if not condition.sensor_type:
            logger.error("Condition missing sensor_type")
            return False
        if not condition.operator:
            logger.error("Condition missing operator")
            return False
        if condition.threshold is None:
            logger.error("Condition missing threshold")
            return False
        
        valid_operators = {">", ">=", "<", "<=", "==", "!=", "in", "not_in"}
        if condition.operator not in valid_operators:
            logger.error("Invalid operator: %s", condition.operator)
            return False
        
        if condition.operator in ("in", "not_in") and not isinstance(condition.threshold, list):
            logger.error("Operator %s requires list threshold", condition.operator)
            return False
        
        return True
    
    def _evaluate_condition(self, condition: RuleCondition, sensor_data: SensorData) -> bool:
        if not self._validate_condition(condition):
            return False
        
        if condition.did and condition.did != sensor_data.did:
            return False
        
        if condition.sensor_type != sensor_data.sensor_type:
            return False
        
        try:
            sensor_value = sensor_data.value
            threshold = condition.threshold
            
            if condition.operator == ">":
                return sensor_value > threshold
            elif condition.operator == ">=":
                return sensor_value >= threshold
            elif condition.operator == "<":
                return sensor_value < threshold
            elif condition.operator == "<=":
                return sensor_value <= threshold
            elif condition.operator == "==":
                return sensor_value == threshold
            elif condition.operator == "!=":
                return sensor_value != threshold
            elif condition.operator == "in":
                if isinstance(threshold, list):
                    return sensor_value in threshold
            elif condition.operator == "not_in":
                if isinstance(threshold, list):
                    return sensor_value not in threshold
        except (ValueError, TypeError) as e:
            logger.error("Condition evaluation error: %s", e)
            return False
        
        return False
    
    def _get_action_idempotency_key(self, action: RuleAction, sensor_data: SensorData | None) -> str:
        base = f"{action.action_type.value}:{action.action_id if hasattr(action, 'action_id') else id(action)}"
        if sensor_data:
            base += f":{sensor_data.did}:{sensor_data.timestamp.isoformat() if isinstance(sensor_data.timestamp, datetime) else sensor_data.timestamp}"
        return base
    
    def _check_action_idempotency(self, action: RuleAction, sensor_data: SensorData | None, ttl_seconds: int = 60) -> bool:
        key = self._get_action_idempotency_key(action, sensor_data)
        now = datetime.now()
        last_exec = self._action_idempotency.get(key)
        
        if last_exec and (now - last_exec).total_seconds() < ttl_seconds:
            logger.debug("Action skipped due to idempotency: %s", key)
            return False
        
        self._action_idempotency[key] = now
        return True
    
    def _cleanup_idempotency_cache(self) -> None:
        now = datetime.now()
        expired_keys = [
            k for k, v in self._action_idempotency.items()
            if (now - v).total_seconds() > 300
        ]
        for key in expired_keys:
            del self._action_idempotency[key]
    
    async def execute_action_async(self, action: RuleAction, sensor_data: SensorData | None = None) -> bool:
        logger.info("Executing action: %s", action.action_type.value)
        
        if not self._check_action_idempotency(action, sensor_data):
            logger.debug("Action skipped (idempotent): %s", action.action_type.value)
            return True
        
        try:
            if action.action_type == RuleActionType.ALERT:
                return self._execute_alert_action(action)
            elif action.action_type == RuleActionType.LOG:
                return self._execute_log_action(action)
            elif action.action_type == RuleActionType.WEBHOOK:
                return await self._execute_webhook_action_async(action)
            elif action.action_type == RuleActionType.MESSAGE:
                return self._execute_message_action(action)
            else:
                logger.warning("Unknown action type: %s", action.action_type.value)
                return False
        except Exception as e:
            logger.error("Action execution failed: %s", e)
            return False
    
    def execute_action(self, action: RuleAction, sensor_data: SensorData | None = None) -> bool:
        if action.action_type == RuleActionType.WEBHOOK:
            logger.warning("Webhook action called synchronously, use execute_action_async instead")
            return False
        return asyncio.run(self.execute_action_async(action, sensor_data))
    
    def _execute_alert_action(self, action: RuleAction) -> bool:
        logger.warning("ALERT: %s", action.payload.get("message", "Alert triggered"))
        return True
    
    def _execute_log_action(self, action: RuleAction) -> bool:
        logger.info("LOG: %s", action.payload.get("message", "Log entry"))
        return True
    
    async def _execute_webhook_action_async(self, action: RuleAction) -> bool:
        url = action.payload.get("url")
        if not url:
            logger.error("Webhook URL not specified")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=action.payload.get("data", {}),
                    timeout=10.0,
                )
                success = response.status_code == 200
                logger.info("Webhook %s: %s -> %d", "succeeded" if success else "failed", url, response.status_code)
                return success
        except Exception as e:
            logger.error("Webhook failed: %s", e)
            return False
    
    def _execute_message_action(self, action: RuleAction) -> bool:
        message = action.payload.get("message", "")
        logger.info("MESSAGE: %s", message)
        return True
    
    async def run_rules(self, sensor_data: SensorData) -> list[RuleAction]:
        actions = self.evaluate(sensor_data)
        for action in actions:
            await self.execute_action_async(action, sensor_data)
        self._cleanup_idempotency_cache()
        return actions