# API Reference

## Base URL

All API endpoints are relative to `http://localhost:1912`.

## Authentication

Most endpoints require OAuth2 authentication. Include the `Authorization` header with a bearer token:

```bash
Authorization: bearer <token>
```

## Response Format

All successful responses return JSON with the following format:

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

Error responses:

```json
{
  "code": 401,
  "message": "Unauthorized",
  "error": "..."
}
```

---

## Authentication Endpoints

### GET /api/auth/login

Redirect to Heiman OAuth2 login page.

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "login_url": "https://spfile.heiman.cn/applogin/sso.html?..."
  }
}
```

### GET /api/auth/token

Get current authentication token.

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "..."
  }
}
```

### POST /api/auth/refresh

Refresh access token.

**Request Body:**
```json
{
  "refresh_token": "..."
}
```

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "..."
  }
}
```

---

## Sensor Endpoints

### GET /api/sensors

Get all sensors.

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "did": "sensor_001",
      "name": "Kitchen Smoke Detector",
      "type": "SMOKE",
      "value": 15,
      "unit": "%",
      "status": "NORMAL",
      "battery_level": 85,
      "last_update": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### GET /api/sensors/{did}

Get sensor by ID.

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "did": "sensor_001",
    "name": "Kitchen Smoke Detector",
    "type": "SMOKE",
    "value": 15,
    "unit": "%",
    "status": "NORMAL",
    "battery_level": 85,
    "last_update": "2024-01-15T10:30:00Z"
  }
}
```

### GET /api/sensors/{did}/history

Get sensor historical data.

**Query Parameters:**
- `start_time`: ISO 8601 timestamp (optional)
- `end_time`: ISO 8601 timestamp (optional)
- `limit`: Number of records (default: 100)

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "value": 15,
      "status": "NORMAL"
    }
  ]
}
```

### POST /api/sensors/data

Push sensor data (internal use).

**Request Body:**
```json
{
  "did": "sensor_001",
  "value": 25,
  "status": "NORMAL"
}
```

**Response:**
```json
{
  "code": 0,
  "message": "success"
}
```

---

## Event Endpoints

### GET /api/events

Get all events.

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20)
- `type`: Filter by event type (ALARM, WARNING, INFO)
- `acknowledged`: Filter by acknowledgment status

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "events": [
      {
        "id": "event_001",
        "sensor_id": "sensor_001",
        "type": "WARNING",
        "message": "Smoke level above threshold",
        "timestamp": "2024-01-15T10:30:00Z",
        "acknowledged": false,
        "data": {
          "value": 85,
          "threshold": 70
        }
      }
    ],
    "total": 100,
    "page": 1,
    "limit": 20
  }
}
```

### GET /api/events/{event_id}

Get event by ID.

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "event_001",
    "sensor_id": "sensor_001",
    "type": "WARNING",
    "message": "Smoke level above threshold",
    "timestamp": "2024-01-15T10:30:00Z",
    "acknowledged": false,
    "data": {
      "value": 85,
      "threshold": 70
    }
  }
}
```

### POST /api/events/{event_id}/acknowledge

Acknowledge an event.

**Response:**
```json
{
  "code": 0,
  "message": "Event acknowledged"
}
```

---

## Rule Endpoints

### GET /api/rules

Get all rules.

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": "rule_001",
      "name": "Smoke Alarm",
      "description": "Trigger alert when smoke level exceeds 70%",
      "enabled": true,
      "condition": {
        "sensor_type": "SMOKE",
        "operator": ">",
        "value": 70
      },
      "action": {
        "type": "ALERT",
        "message": "Smoke detected!"
      },
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

### POST /api/rules

Create a new rule.

**Request Body:**
```json
{
  "name": "High Temperature Alert",
  "description": "Alert when temperature exceeds 35°C",
  "enabled": true,
  "condition": {
    "sensor_type": "TEMPERATURE",
    "operator": ">",
    "value": 35
  },
  "action": {
    "type": "ALERT",
    "message": "Temperature too high!"
  }
}
```

**Response:**
```json
{
  "code": 0,
  "message": "Rule created",
  "data": {
    "id": "rule_002"
  }
}
```

### PUT /api/rules/{rule_id}

Update a rule.

**Request Body:**
```json
{
  "name": "Updated Rule",
  "enabled": false
}
```

**Response:**
```json
{
  "code": 0,
  "message": "Rule updated"
}
```

### DELETE /api/rules/{rule_id}

Delete a rule.

**Response:**
```json
{
  "code": 0,
  "message": "Rule deleted"
}
```

---

## Admin Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "status": "healthy",
    "service": "heiman-agent",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### GET /api/admin/status

Get system status.

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "sensor_count": 5,
    "online_sensors": 4,
    "event_count": 10,
    "rule_count": 3,
    "database_size": 1024000
  }
}
```

### POST /api/admin/cleanup

Cleanup historical data.

**Request Body:**
```json
{
  "dry_run": false,
  "older_than_days": 30
}
```

**Response:**
```json
{
  "code": 0,
  "message": "Cleanup completed",
  "data": {
    "deleted_records": 500
  }
}
```

---

## Monitor Endpoints

### GET /api/monitor/resources

Get system resource usage.

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "cpu": {
      "percent": 15,
      "count": 4
    },
    "memory": {
      "total": 8589934592,
      "available": 4294967296,
      "used": 4294967296,
      "percent": 50
    },
    "disk": {
      "total": 250059350016,
      "used": 125029675008,
      "free": 125029675008,
      "percent": 50
    }
  }
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 500 | Internal Server Error |