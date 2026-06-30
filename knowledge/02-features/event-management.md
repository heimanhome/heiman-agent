# Event Management Feature

## Event Types

Heiman Agent generates events based on sensor data analysis:

| Event Type | Description | Trigger Condition |
|------------|-------------|-------------------|
| ALARM | Critical alarm event | Sensor value exceeds critical threshold |
| WARNING | Warning event | Sensor value exceeds warning threshold |
| INFO | Informational event | Sensor status change, normal operation |

## Event Levels

Events are classified by severity:

| Level | Description | Priority |
|-------|-------------|----------|
| CRITICAL | Life-threatening condition | Highest |
| HIGH | Serious condition requiring attention | High |
| MEDIUM | Moderate condition | Medium |
| LOW | Minor issue or informational | Low |

## Event Processing

### Event Classification Flow

1. **Data Input**: Sensor data is received
2. **Rule Evaluation**: Classifier evaluates against predefined thresholds
3. **Event Generation**: Event is created with appropriate type and level
4. **Storage**: Event is stored in database
5. **Alerting**: Webhook notifications are sent (if configured)

### Threshold Configuration

Default thresholds for each sensor type:

| Sensor Type | Warning Threshold | Alarm Threshold |
|-------------|-------------------|-----------------|
| SMOKE | > 10% | > 30% |
| TEMPERATURE | > 30°C or < 5°C | > 40°C or < -10°C |
| HUMIDITY | > 80% or < 20% | > 90% or < 10% |
| CO | > 50 ppm | > 100 ppm |
| WATER | DETECTED | DETECTED |

## Event Dashboard

The web interface provides:
- Event list with filtering (type, level, acknowledged)
- Event details view
- Acknowledge functionality
- Timeline visualization

## API Endpoints

- `GET /api/events`: Get all events
- `GET /api/events/{event_id}`: Get event by ID
- `POST /api/events/{event_id}/acknowledge`: Acknowledge event
