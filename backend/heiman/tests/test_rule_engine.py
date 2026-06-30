import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from heiman.rule.rule_engine import RuleEngine
from heiman.schema.rule import (
    Rule, RuleAction, RuleActionType, RuleCondition,
)
from heiman.schema.sensor import SensorData, SensorType, SensorStatus


@pytest.fixture
def rule_engine():
    engine = RuleEngine()
    engine._rule_repo = MagicMock()
    engine._rule_repo.get_all.return_value = []
    return engine


@pytest.fixture
def sample_sensor_data():
    return SensorData(
        did="test-device-001",
        name="Test Temperature Sensor",
        sensor_type=SensorType.TEMPERATURE,
        value=25.0,
        unit="℃",
        status=SensorStatus.NORMAL,
        room_id="room-1",
        room_name="Living Room",
        home_id="home-1",
        timestamp=datetime.now(),
    )


def create_test_rule(
    rule_id="rule-001",
    name="Test Rule",
    conditions=None,
    actions=None,
    cooldown_minutes=5,
):
    if conditions is None:
        conditions = [
            RuleCondition(
                sensor_type=SensorType.TEMPERATURE,
                operator=">",
                threshold=30.0,
            )
        ]
    if actions is None:
        actions = [
            RuleAction(
                action_type=RuleActionType.ALERT,
                payload={"message": "Temperature too high"},
            )
        ]
    return Rule(
        rule_id=rule_id,
        name=name,
        conditions=conditions,
        actions=actions,
        cooldown_minutes=cooldown_minutes,
        enabled=True,
    )


class TestRuleEngineEvaluate:
    def test_no_rules_returns_empty(self, rule_engine, sample_sensor_data):
        rule_engine._rule_repo.get_all.return_value = []
        actions = rule_engine.evaluate(sample_sensor_data)
        assert actions == []

    def test_rule_triggers_when_condition_met(self, rule_engine, sample_sensor_data):
        sample_sensor_data.value = 35.0
        rule = create_test_rule()
        rule_engine._rule_repo.get_all.return_value = [rule]

        actions = rule_engine.evaluate(sample_sensor_data)

        assert len(actions) == 1
        assert actions[0].action_type == RuleActionType.ALERT

    def test_rule_does_not_trigger_when_condition_not_met(
        self, rule_engine, sample_sensor_data
    ):
        sample_sensor_data.value = 25.0
        rule = create_test_rule()
        rule_engine._rule_repo.get_all.return_value = [rule]

        actions = rule_engine.evaluate(sample_sensor_data)

        assert len(actions) == 0

    def test_cooldown_prevents_retrigger(self, rule_engine, sample_sensor_data):
        sample_sensor_data.value = 35.0
        rule = create_test_rule(cooldown_minutes=10)
        rule_engine._rule_repo.get_all.return_value = [rule]

        rule_engine.evaluate(sample_sensor_data)
        actions = rule_engine.evaluate(sample_sensor_data)

        assert len(actions) == 0

    def test_cooldown_expires_allows_retrigger(self, rule_engine, sample_sensor_data):
        sample_sensor_data.value = 35.0
        rule = create_test_rule(cooldown_minutes=1)
        rule_engine._rule_repo.get_all.return_value = [rule]

        rule_engine.evaluate(sample_sensor_data)
        rule_engine._last_triggered[rule.rule_id] = datetime.now() - timedelta(
            minutes=2
        )
        actions = rule_engine.evaluate(sample_sensor_data)

        assert len(actions) == 1

    def test_disabled_rule_not_evaluated(self, rule_engine, sample_sensor_data):
        sample_sensor_data.value = 35.0
        rule = create_test_rule()
        rule.enabled = False

        def mock_get_all(enabled_only=False):
            if enabled_only:
                return []
            return [rule]

        rule_engine._rule_repo.get_all.side_effect = mock_get_all

        actions = rule_engine.evaluate(sample_sensor_data)

        assert len(actions) == 0


class TestConditionEvaluation:
    def test_greater_than_operator(self, rule_engine, sample_sensor_data):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator=">",
            threshold=30.0,
        )
        sample_sensor_data.value = 35.0
        assert rule_engine._evaluate_condition(condition, sample_sensor_data) is True

    def test_less_than_operator(self, rule_engine, sample_sensor_data):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator="<",
            threshold=30.0,
        )
        sample_sensor_data.value = 25.0
        assert rule_engine._evaluate_condition(condition, sample_sensor_data) is True

    def test_equality_operator(self, rule_engine, sample_sensor_data):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator="==",
            threshold=25.0,
        )
        sample_sensor_data.value = 25.0
        assert rule_engine._evaluate_condition(condition, sample_sensor_data) is True

    def test_in_operator(self, rule_engine, sample_sensor_data):
        condition = RuleCondition(
            sensor_type=SensorType.SMOKE,
            operator="in",
            threshold=[1, 2, 3],
        )
        sample_sensor_data.sensor_type = SensorType.SMOKE
        sample_sensor_data.value = 1
        assert rule_engine._evaluate_condition(condition, sample_sensor_data) is True

    def test_not_in_operator(self, rule_engine, sample_sensor_data):
        condition = RuleCondition(
            sensor_type=SensorType.SMOKE,
            operator="not_in",
            threshold=[1, 2, 3],
        )
        sample_sensor_data.sensor_type = SensorType.SMOKE
        sample_sensor_data.value = 0
        assert rule_engine._evaluate_condition(condition, sample_sensor_data) is True

    def test_different_sensor_type_returns_false(self, rule_engine, sample_sensor_data):
        condition = RuleCondition(
            sensor_type=SensorType.HUMIDITY,
            operator=">",
            threshold=30.0,
        )
        sample_sensor_data.value = 35.0
        assert rule_engine._evaluate_condition(condition, sample_sensor_data) is False

    def test_did_mismatch_returns_false(self, rule_engine, sample_sensor_data):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator=">",
            threshold=30.0,
            did="other-device",
        )
        sample_sensor_data.value = 35.0
        assert rule_engine._evaluate_condition(condition, sample_sensor_data) is False

    def test_invalid_condition_returns_false(self, rule_engine, sample_sensor_data):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator="invalid_op",
            threshold=30.0,
        )
        assert rule_engine._evaluate_condition(condition, sample_sensor_data) is False


class TestConditionValidation:
    def test_missing_threshold_invalid(self, rule_engine):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator=">",
            threshold=None,
        )
        assert rule_engine._validate_condition(condition) is False

    def test_invalid_operator_invalid(self, rule_engine):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator="invalid_op",
            threshold=30.0,
        )
        assert rule_engine._validate_condition(condition) is False

    def test_in_operator_requires_list_threshold(self, rule_engine):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator="in",
            threshold=30.0,
        )
        assert rule_engine._validate_condition(condition) is False

    def test_not_in_operator_requires_list_threshold(self, rule_engine):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator="not_in",
            threshold=30.0,
        )
        assert rule_engine._validate_condition(condition) is False

    def test_valid_condition_passes(self, rule_engine):
        condition = RuleCondition(
            sensor_type=SensorType.TEMPERATURE,
            operator=">",
            threshold=30.0,
        )
        assert rule_engine._validate_condition(condition) is True

    def test_valid_in_condition_passes(self, rule_engine):
        condition = RuleCondition(
            sensor_type=SensorType.SMOKE,
            operator="in",
            threshold=[1, 2, 3],
        )
        assert rule_engine._validate_condition(condition) is True


class TestActionIdempotency:
    def test_same_action_skipped_within_ttl(self, rule_engine, sample_sensor_data):
        action = RuleAction(
            action_id="action-001",
            action_type=RuleActionType.ALERT,
            payload={"message": "test"},
        )

        first = rule_engine._check_action_idempotency(action, sample_sensor_data, ttl_seconds=60)
        second = rule_engine._check_action_idempotency(action, sample_sensor_data, ttl_seconds=60)

        assert first is True
        assert second is False

    def test_different_actions_not_idempotent(self, rule_engine, sample_sensor_data):
        action1 = RuleAction(
            action_id="action-001",
            action_type=RuleActionType.ALERT,
            payload={"message": "test1"},
        )

        action2 = RuleAction(
            action_id="action-002",
            action_type=RuleActionType.LOG,
            payload={"message": "test2"},
        )

        first = rule_engine._check_action_idempotency(action1, sample_sensor_data, ttl_seconds=60)
        second = rule_engine._check_action_idempotency(action2, sample_sensor_data, ttl_seconds=60)

        assert first is True
        assert second is True

    def test_idempotency_cache_cleanup(self, rule_engine, sample_sensor_data):
        action = RuleAction(
            action_id="action-001",
            action_type=RuleActionType.ALERT,
            payload={"message": "test"},
        )

        rule_engine._check_action_idempotency(action, sample_sensor_data, ttl_seconds=60)
        assert len(rule_engine._action_idempotency) == 1

        rule_engine._cleanup_idempotency_cache()
        assert len(rule_engine._action_idempotency) == 1

        for key in rule_engine._action_idempotency:
            rule_engine._action_idempotency[key] = datetime.now() - timedelta(minutes=10)

        rule_engine._cleanup_idempotency_cache()
        assert len(rule_engine._action_idempotency) == 0


class TestAsyncActions:
    @pytest.mark.asyncio
    async def test_execute_alert_action_async(self, rule_engine):
        action = RuleAction(
            action_type=RuleActionType.ALERT,
            payload={"message": "Test alert"},
        )
        result = await rule_engine.execute_action_async(action)
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_log_action_async(self, rule_engine):
        action = RuleAction(
            action_type=RuleActionType.LOG,
            payload={"message": "Test log"},
        )
        result = await rule_engine.execute_action_async(action)
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_message_action_async(self, rule_engine):
        action = RuleAction(
            action_type=RuleActionType.MESSAGE,
            payload={"message": "Test message"},
        )
        result = await rule_engine.execute_action_async(action)
        assert result is True

    @pytest.mark.asyncio
    @patch("heiman.rule.rule_engine.httpx.AsyncClient")
    async def test_execute_webhook_action_async_success(self, mock_client_class, rule_engine):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        action = RuleAction(
            action_type=RuleActionType.WEBHOOK,
            payload={"url": "http://example.com/webhook", "data": {"key": "value"}},
        )
        result = await rule_engine.execute_action_async(action)
        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    @patch("heiman.rule.rule_engine.httpx.AsyncClient")
    async def test_execute_webhook_action_async_failure(self, mock_client_class, rule_engine):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        action = RuleAction(
            action_type=RuleActionType.WEBHOOK,
            payload={"url": "http://example.com/webhook"},
        )
        result = await rule_engine.execute_action_async(action)
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_webhook_no_url(self, rule_engine):
        action = RuleAction(
            action_type=RuleActionType.WEBHOOK,
            payload={},
        )
        result = await rule_engine.execute_action_async(action)
        assert result is False


class TestRunRules:
    @pytest.mark.asyncio
    async def test_run_rules_executes_actions(self, rule_engine, sample_sensor_data):
        sample_sensor_data.value = 35.0
        rule = create_test_rule()
        rule_engine._rule_repo.get_all.return_value = [rule]

        actions = await rule_engine.run_rules(sample_sensor_data)

        assert len(actions) == 1
        assert actions[0].action_type == RuleActionType.ALERT
