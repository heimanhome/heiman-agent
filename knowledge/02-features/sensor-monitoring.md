# Sensor Monitoring Feature

## Supported Sensor Types

Heiman Agent supports the following sensor types:

| Sensor Type | Description | Unit | Data Range |
|-------------|-------------|------|------------|
| SMOKE | Smoke detector | % | 0-100 |
| TEMPERATURE | Temperature sensor | °C | -40 to 80 |
| HUMIDITY | Humidity sensor | % | 0-100 |
| CO | Carbon monoxide detector | ppm | 0-1000 |
| WATER | Water leak sensor | - | DETECTED/UNDERTECTED |

## Sensor Data Collection

### Data Flow

1. **Device Sync**: Adapter connects to Heiman Cloud API
2. **Data Fetch**: Sensor data is periodically fetched
3. **Storage**: Data is stored in SQLite database
4. **Event Generation**: Classifier analyzes data and generates events

### Sync Interval

- Default: 30 seconds
- Configurable via `SENSOR_SYNC_INTERVAL_SECONDS` environment variable

## Sensor Status

Each sensor has a status that reflects its current state:

| Status | Description | Color |
|--------|-------------|-------|
| NORMAL | Sensor is functioning normally | Green |
| WARNING | Sensor value is outside normal range | Yellow |
| ALARM | Critical condition detected | Red |
| OFFLINE | Sensor is not responding | Gray |

## Sensor Dashboard

The web interface provides:
- Real-time sensor data display
- Historical data charts
- Sensor status indicators
- Quick access to sensor details

## API Endpoints

- `GET /api/sensors`: Get all sensors
- `GET /api/sensors/{did}`: Get sensor by ID
- `GET /api/sensors/{did}/history`: Get sensor history
- `POST /api/sensors/data`: Push sensor data
