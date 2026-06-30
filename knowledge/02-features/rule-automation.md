# Rule Automation Feature

## Rule Structure

A rule consists of:
1. **Conditions**: When the rule should trigger
2. **Actions**: What should happen when triggered
3. **Cooldown**: Minimum time between triggers

## Rule Conditions

Conditions define when a rule should activate:

| Field | Description | Example |
|-------|-------------|---------|
| did | Device ID (optional) | "sensor_001" |
| sensor_type | Sensor type filter (optional) | "SMOKE" |
| operator | Comparison operator | ">", "<", "=", "!=" |
| value | Threshold value | 30 |
| window_seconds | Duration threshold must be met (optional) | 60 |

## Rule Actions

Actions define what happens when conditions are met:

| Action Type | Description | Configuration |
|-------------|-------------|---------------|
| LOG | Log the event | None |
| ALERT | Send an alert | message |
| WEBHOOK | Call external API | target (URL), message |

## Rule Engine Flow

1. **Rule Loading**: Rules are loaded from database
2. **Condition Evaluation**: Sensor data is evaluated against rule conditions
3. **Action Execution**: If conditions are met, actions are executed
4. **Cooldown Check**: Rule is temporarily disabled after execution
5. **Logging**: Rule execution is logged

## Rule Management

### Web Interface
- Rule list with status indicators
- Create/edit rule form
- Rule preview functionality
- Enable/disable toggle

### CLI Commands
- `heiman rule list`: List all rules
- `heiman rule get <rule_id>`: Get rule details
- `heiman rule create`: Create new rule
- `heiman rule delete <rule_id>`: Delete rule

## API Endpoints

- `GET /api/rules`: Get all rules
- `GET /api/rules/{rule_id}`: Get rule by ID
- `POST /api/rules`: Create new rule
- `PUT /api/rules/{rule_id}`: Update rule
- `DELETE /api/rules/{rule_id}`: Delete rule

## Example Rule

```json
{
  "name": "Smoke Alarm",
  "description": "Trigger alarm when smoke detected",
  "enabled": true,
  "conditions": [
    {
      "sensor_type": "SMOKE",
      "operator": ">",
      "value": 30
    }
  ],
  "actions": [
    {
      "type": "ALERT",
      "message": "Smoke detected! Evacuate immediately!"
    },
    {
      "type": "WEBHOOK",
      "target": "https://example.com/webhook/alert",
      "message": "Smoke alarm triggered"
    }
  ],
  "cooldown_minutes": 5
}
```
