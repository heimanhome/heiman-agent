# Heiman Agent

[简体中文](README.md) | **English**

An intelligent agent for Heiman sensors, designed for smart home safety monitoring and automation.

## Features

### Sensor Integration
- Supports multiple sensor types: smoke, temperature & humidity, carbon monoxide, water leak, door contact, and more
- Real-time sensor data collection via Heiman HTTP and MQTT protocols
- Device online status monitoring and event triggering

### Intelligent Analysis
- AI-powered anomaly detection engine that automatically identifies abnormal behavior patterns
- Comfort assessment with health recommendations based on environmental data
- Behavior recognition and learning to understand daily activity routines

### Rule Engine
- Custom rules for automation scenarios
- Flexible condition and action configuration
- Rule cooldown mechanism to prevent repeated triggering

### Real-Time Communication
- Real-time data push over MQTT
- Server-Sent Events (SSE) for live frontend updates
- Device status change notifications

### Visual Management
- Responsive web management interface
- Multi-language support (Chinese, English, Japanese, Korean)
- Device status dashboard, event logs, and sensor history charts

### Command-Line Tool
- Full CLI command set for device management, rule configuration, event queries, and more
- API debugging and health check support

## Tech Stack

### Backend
- Python 3.10+
- FastAPI
- SQLite (database)
- Paho MQTT
- HTTPX
- Pydantic 2

### Frontend
- React 18
- TypeScript
- Vite 6
- TailwindCSS 3
- Zustand (state management)
- Chart.js (charts)
- React Router DOM

### CLI
- Click
- Rich
- HTTPX

## Project Structure

```
heiman-agent/
├── backend/
│   └── heiman/              # FastAPI backend service
│       ├── src/heiman/
│       │   ├── adapter/     # Device adapters
│       │   ├── ai/          # AI modules (anomaly detection, behavior recognition, etc.)
│       │   ├── classifier/  # Event classifier
│       │   ├── client/      # Heiman API client
│       │   ├── collector/   # Data collector
│       │   ├── config/      # Configuration management
│       │   ├── database/    # Database module
│       │   ├── home_profile/# Home profile
│       │   ├── middleware/  # Middleware
│       │   ├── node_monitor/# Node monitoring
│       │   ├── observability/# Observability
│       │   ├── perception/  # Perception engine
│       │   ├── router/      # API routes
│       │   ├── rule/        # Rule engine
│       │   ├── schema/      # Data models
│       │   ├── service/     # Business services
│       │   ├── main.py      # Application entry point
│       │   ├── manager.py   # Service manager
│       │   └── mqtt_service.py # MQTT service
│       ├── tests/           # Test cases
│       ├── .env             # Environment configuration
│       ├── .env.example     # Environment configuration example
│       └── pyproject.toml   # Python project configuration
├── cli/                     # Command-line tool
│   ├── src/heiman_cli/
│   │   ├── commands/        # CLI commands
│   │   └── main.py          # CLI entry point
│   ├── tests/               # CLI tests
│   └── pyproject.toml
├── web/                     # Frontend web application
│   ├── src/
│   │   ├── api/             # API client
│   │   ├── components/      # UI components
│   │   ├── hooks/           # Custom hooks
│   │   ├── i18n/            # Internationalization
│   │   ├── pages/           # Page components
│   │   ├── store/           # State management
│   │   └── types/           # TypeScript type definitions
│   ├── tests/               # Frontend tests
│   └── package.json
├── plugins/                 # Plugins directory
│   └── openclaw/
├── .github/workflows/       # CI/CD workflows
├── Dockerfile               # Docker image build
├── docker-compose.yml       # Docker Compose configuration
├── README.md                # Project documentation (Chinese)
├── README_EN.md             # Project documentation (this file)
├── CHANGELOG.md             # Changelog
└── API_REFERENCE.md         # API reference
```

## Installation

### Prerequisites

- Python 3.10+
- Node.js 20+
- pnpm (frontend package manager)

### Backend Installation

```bash
# Enter the backend directory
cd backend/heiman

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# Install dependencies
pip install -e .

# Install test dependencies
pip install pytest pytest-asyncio httpx
```

### CLI Installation

```bash
cd cli
pip install -e .
```

### Frontend Installation

```bash
cd web
pnpm install
```

## Usage

### Configure Environment Variables

Copy and edit the backend environment configuration:

```bash
cd backend/heiman
cp .env.example .env
```

Edit the `.env` file and configure the following key parameters:

```env
# Heiman API configuration
HEIMAN_API_URL=https://spapi.heiman.cn
HEIMAN_APP_ID=your_app_id
HEIMAN_EMAIL=your_email@example.com
HEIMAN_PASSWORD=your_password

# Server configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Sensor refresh interval (seconds)
SENSOR_REFRESH_INTERVAL_SECONDS=30

# Rule engine configuration
RULE_ENGINE_ENABLED=true
RULE_DEFAULT_COOLDOWN_MINUTES=5

# Logging configuration
LOGGING_LEVEL=INFO
LOGGING_LOG_DIR=/tmp/heiman/logs
```

### Start the Backend Service

```bash
cd backend/heiman
heiman-backend
```

Or start directly with Uvicorn:

```bash
uvicorn heiman.main:create_app --host 0.0.0.0 --port 8000 --reload
```

### Start the Frontend Dev Server

```bash
cd web
pnpm dev
```

### Use the CLI Tool

```bash
# Show help
heiman --help

# Show subcommand help
heiman devices --help

# List devices
heiman devices list

# List events
heiman events list

# Health check
heiman health
```

## API Endpoints

### Authentication
- `GET /api/auth/profile` - Get user profile
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Refresh token

### Devices
- `GET /api/devices` - List devices
- `GET /api/devices/{device_id}` - Get a single device
- `GET /api/devices/{device_id}/properties` - Get device properties

### Sensors
- `GET /api/sensors` - List sensors
- `GET /api/sensors/{sensor_id}` - Get a single sensor
- `GET /api/sensors/{sensor_id}/history` - Get sensor history data

### Events
- `GET /api/events` - List events
- `GET /api/events/{event_id}` - Get a single event
- `POST /api/events/{event_id}/acknowledge` - Acknowledge an event

### Rules
- `GET /api/rules` - List rules
- `POST /api/rules` - Create a rule
- `PUT /api/rules/{rule_id}` - Update a rule
- `DELETE /api/rules/{rule_id}` - Delete a rule

### Observability
- `GET /api/observability/overview` - System overview
- `GET /api/health` - Health check

### Real-Time Event Stream
- `GET /api/events/stream` - SSE real-time event stream

## Testing

### Run Backend Tests

```bash
cd backend/heiman
pytest
```

### Run Frontend Tests

```bash
cd web
pnpm test
```

### Run CLI Tests

```bash
cd cli
pytest
```

## Docker Deployment

### Build the Image

```bash
docker build -t heiman-agent .
```

### Run the Container

```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/backend/heiman/.env:/app/.env \
  --name heiman-agent \
  heiman-agent
```

### Using Docker Compose

```bash
docker-compose up -d
```

## CI/CD

This project uses GitHub Actions for automated CI/CD, covering the following stages:

1. **Code linting** - Run flake8 and mypy for code quality checks
2. **Unit tests** - Run the pytest test suite
3. **Build verification** - Verify Python package and frontend builds
4. **Image build** - Build the Docker image
5. **Deployment** - Deploy to the target environment

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

### Code Style

- Python code follows PEP 8
- Use flake8 for linting
- Use mypy for type checking
- Commit messages follow the Conventional Commits specification:
  - `feat:` new feature
  - `fix:` bug fix
  - `docs:` documentation update
  - `refactor:` code refactoring
  - `test:` test-related changes
  - `chore:` build/tooling updates

### Testing Requirements

- New features must include corresponding unit tests
- Ensure all tests pass before submitting
- Test coverage target: ≥80%

## License

This project is licensed under the **MIT License (Non-Commercial Use)**. See the [LICENSE](LICENSE) file for details.

> **Important**: This project is for non-commercial use only. Any commercial use (including but not limited to sales, integration into commercial products, or commercial profit) requires written permission from the copyright holder.

## Contact

For questions or suggestions, please reach out via:

- Opening an issue in the GitHub repository
- Email: help@heimanhome.com
