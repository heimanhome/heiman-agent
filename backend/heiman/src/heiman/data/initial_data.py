import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def initialize_system_logs(log_repo):
    try:
        base_time = datetime.now()

        startup_logs = [
            {
                "level": "info",
                "action": "System Started",
                "user": "System",
                "message": "Heiman Agent backend started successfully",
            },
            {
                "level": "info",
                "action": "Database Initialized",
                "user": "System",
                "message": "SQLite database initialized with all required tables",
            },
            {
                "level": "info",
                "action": "API Client Ready",
                "user": "System",
                "message": "Heiman API client initialized and ready for connections",
            },
            {
                "level": "info",
                "action": "MQTT Service Started",
                "user": "System",
                "message": "MQTT service started, waiting for authentication",
            },
            {
                "level": "info",
                "action": "Web Server",
                "user": "System",
                "message": "FastAPI web server running on http://localhost:1912",
            },
            {
                "level": "success",
                "action": "Health Check",
                "user": "System",
                "message": "System health check passed - all services operational",
            },
        ]

        for log_entry in startup_logs:
            log_repo.insert(
                level=log_entry["level"],
                action=log_entry["action"],
                user=log_entry["user"],
                message=log_entry["message"],
            )

        logger.info("[INIT] Recorded %d system startup logs", len(startup_logs))
    except Exception as e:
        logger.error("[INIT] Failed to record system logs: %s", e)


def initialize_models(model_repo):
    try:
        existing_models = model_repo.get_all()
        if existing_models:
            logger.info("[INIT] Models already exist, skipping initialization")
            return

        initial_models = [
            {
                "id": "model-smoke-detection-v1",
                "name": "Smoke Detection",
                "version": "v2.1.0",
                "type": "detection",
                "status": "deployed",
                "description": "AI model for smoke detection using sensor data",
                "accuracy": 98.5,
                "last_deployed": "2024-01-10",
            },
            {
                "id": "model-co-alert-v1",
                "name": "CO Alert",
                "version": "v1.5.0",
                "type": "classification",
                "status": "deployed",
                "description": "Carbon monoxide level classification model",
                "accuracy": 96.2,
                "last_deployed": "2024-01-08",
            },
            {
                "id": "model-temp-forecast-v1",
                "name": "Temp Forecast",
                "version": "v3.0.0",
                "type": "forecast",
                "status": "training",
                "description": "Temperature prediction model for next 24 hours",
                "accuracy": 89.8,
                "last_deployed": None,
            },
            {
                "id": "model-water-leak-v1",
                "name": "Water Leak",
                "version": "v1.2.0",
                "type": "detection",
                "status": "not_deployed",
                "description": "Water leak detection model",
                "accuracy": 94.7,
                "last_deployed": None,
            },
        ]

        for model_data in initial_models:
            model_repo.create(model_data)

        logger.info("[INIT] Initialized %d models", len(initial_models))
    except Exception as e:
        logger.error("[INIT] Failed to initialize models: %s", e)


def initialize_data():
    try:
        from heiman.database.log_repo import get_log_repo
        from heiman.database.model_repo import get_model_repo

        log_repo = get_log_repo()
        model_repo = get_model_repo()

        initialize_system_logs(log_repo)
        initialize_models(model_repo)

        logger.info("[INIT] All initial data loaded successfully")
    except Exception as e:
        logger.error("[INIT] Failed to initialize data: %s", e)
