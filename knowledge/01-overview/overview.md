# Heiman Agent Overview

## Project Architecture

Heiman Agent follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Interface                          │
├─────────────────────────────────────────────────────────────┤
│                    REST API Layer                           │
│  (auth, sensors, events, rules)                            │
├─────────────────────────────────────────────────────────────┤
│                   Business Logic Layer                      │
│  (collector, classifier, rule engine, adapters)            │
├─────────────────────────────────────────────────────────────┤
│                    Data Access Layer                        │
│  (sensor_repo, event_repo, rule_repo)                      │
├─────────────────────────────────────────────────────────────┤
│                     Database Layer                          │
│  (SQLite: sensor_logs, events, rules)                      │
├─────────────────────────────────────────────────────────────┤
│                    Heiman Cloud API                         │
│  (HTTP: spapi.heiman.cn, OAuth2)                           │
└─────────────────────────────────────────────────────────────┘
```

## Core Modules

### 1. Adapter Layer
- `SensorDeviceAdapter`: Connects to Heiman Cloud API
- Implements `BaseDeviceAdapter` interface
- Handles device discovery and data collection

### 2. Collector Layer
- `SensorCollector`: Manages multiple adapters
- Periodically refreshes sensor data
- Coordinates data flow between modules

### 3. Classifier Layer
- `EventClassifier`: Analyzes sensor data
- Generates events based on predefined rules
- Supports multiple event types (ALARM, WARNING, INFO)

### 4. Rule Engine
- `RuleEngine`: Executes user-defined rules
- Evaluates conditions against sensor data
- Triggers actions (LOG, ALERT, WEBHOOK)

### 5. Authentication
- OAuth2 flow with Heiman Cloud
- Token management and refresh
- Session-based authentication

## Data Flow

1. **Sensor Data Collection**: Heiman Cloud → Adapter → Collector → Database
2. **Event Processing**: Sensor Data → Classifier → Event → Database → Alert
3. **Rule Execution**: Sensor Data → Rule Engine → Action → Notification
4. **Web Dashboard**: API → Frontend → User Interface

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, TypeScript, TailwindCSS, Zustand |
| Backend | FastAPI, Python 3.10+ |
| Database | SQLite |
| API Client | httpx, heiman-connect |
| Authentication | OAuth2 |
| CLI | argparse, rich |
