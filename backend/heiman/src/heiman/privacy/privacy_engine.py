import logging
import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PrivacyLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    PRIVATE = "private"


class DataCategory(str, Enum):
    DEVICE_STATE = "device_state"
    SENSOR_READING = "sensor_reading"
    USER_BEHAVIOR = "user_behavior"
    EMOTION_DATA = "emotion_data"
    SECURITY_EVENT = "security_event"
    ENERGY_USAGE = "energy_usage"


@dataclass
class PrivacyPolicy:
    data_category: DataCategory
    privacy_level: PrivacyLevel
    retention_days: int = 30
    allow_local_processing: bool = True
    allow_cloud_sync: bool = False
    anonymize_required: bool = True


@dataclass
class DataRecord:
    record_id: str
    category: DataCategory
    data: Dict[str, Any]
    privacy_level: PrivacyLevel
    timestamp: float
    expires_at: float = 0.0
    is_anonymized: bool = False


class PrivacyEngine:
    def __init__(self):
        self._policies: Dict[DataCategory, PrivacyPolicy] = {}
        self._data_cache: Dict[str, DataRecord] = {}
        self._anonymization_map: Dict[str, str] = {}
        self._initialized = False

    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        self._load_default_policies()
        
        if config:
            await self._apply_config(config)

        asyncio.create_task(self._cleanup_expired_data())
        self._initialized = True
        logger.info("Privacy engine initialized")

    def _load_default_policies(self):
        self._policies = {
            DataCategory.DEVICE_STATE: PrivacyPolicy(
                data_category=DataCategory.DEVICE_STATE,
                privacy_level=PrivacyLevel.INTERNAL,
                retention_days=7,
                allow_local_processing=True,
                allow_cloud_sync=False,
                anonymize_required=True,
            ),
            DataCategory.SENSOR_READING: PrivacyPolicy(
                data_category=DataCategory.SENSOR_READING,
                privacy_level=PrivacyLevel.SENSITIVE,
                retention_days=14,
                allow_local_processing=True,
                allow_cloud_sync=False,
                anonymize_required=True,
            ),
            DataCategory.USER_BEHAVIOR: PrivacyPolicy(
                data_category=DataCategory.USER_BEHAVIOR,
                privacy_level=PrivacyLevel.PRIVATE,
                retention_days=30,
                allow_local_processing=True,
                allow_cloud_sync=False,
                anonymize_required=True,
            ),
            DataCategory.EMOTION_DATA: PrivacyPolicy(
                data_category=DataCategory.EMOTION_DATA,
                privacy_level=PrivacyLevel.PRIVATE,
                retention_days=30,
                allow_local_processing=True,
                allow_cloud_sync=False,
                anonymize_required=True,
            ),
            DataCategory.SECURITY_EVENT: PrivacyPolicy(
                data_category=DataCategory.SECURITY_EVENT,
                privacy_level=PrivacyLevel.SENSITIVE,
                retention_days=90,
                allow_local_processing=True,
                allow_cloud_sync=True,
                anonymize_required=True,
            ),
            DataCategory.ENERGY_USAGE: PrivacyPolicy(
                data_category=DataCategory.ENERGY_USAGE,
                privacy_level=PrivacyLevel.INTERNAL,
                retention_days=365,
                allow_local_processing=True,
                allow_cloud_sync=False,
                anonymize_required=False,
            ),
        }

    async def _apply_config(self, config: Dict[str, Any]):
        for category_str, policy_config in config.get("policies", {}).items():
            try:
                category = DataCategory(category_str)
                if category in self._policies:
                    policy = self._policies[category]
                    if "retention_days" in policy_config:
                        policy.retention_days = policy_config["retention_days"]
                    if "allow_cloud_sync" in policy_config:
                        policy.allow_cloud_sync = policy_config["allow_cloud_sync"]
                    if "anonymize_required" in policy_config:
                        policy.anonymize_required = policy_config["anonymize_required"]
                    logger.info(f"Updated policy for {category.value}")
            except ValueError:
                logger.warning(f"Unknown data category: {category_str}")

    async def process_data(self, category: DataCategory, data: Dict[str, Any]) -> Dict[str, Any]:
        policy = self._policies.get(category)
        if not policy:
            logger.warning(f"No policy found for category {category.value}")
            return data

        if policy.anonymize_required:
            data = await self._anonymize_data(category, data)

        record_id = self._generate_record_id(data)
        expires_at = datetime.now().timestamp() + (policy.retention_days * 86400)

        record = DataRecord(
            record_id=record_id,
            category=category,
            data=data,
            privacy_level=policy.privacy_level,
            timestamp=datetime.now().timestamp(),
            expires_at=expires_at,
            is_anonymized=policy.anonymize_required,
        )

        self._data_cache[record_id] = record
        return data

    async def _anonymize_data(self, category: DataCategory, data: Dict[str, Any]) -> Dict[str, Any]:
        anonymized = data.copy()

        sensitive_fields = {
            DataCategory.DEVICE_STATE: ["device_id", "mac_address", "ip_address"],
            DataCategory.SENSOR_READING: ["device_id", "location", "room_name"],
            DataCategory.USER_BEHAVIOR: ["user_id", "username", "device_id"],
            DataCategory.EMOTION_DATA: ["user_id", "username"],
            DataCategory.SECURITY_EVENT: ["device_id", "location", "camera_url"],
            DataCategory.ENERGY_USAGE: ["meter_id", "account_id"],
        }

        fields_to_anonymize = sensitive_fields.get(category, [])
        for field in fields_to_anonymize:
            if field in anonymized and anonymized[field]:
                original_value = str(anonymized[field])
                if original_value not in self._anonymization_map:
                    self._anonymization_map[original_value] = hashlib.sha256(original_value.encode()).hexdigest()[:16]
                anonymized[field] = self._anonymization_map[original_value]

        return anonymized

    def _generate_record_id(self, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().timestamp()
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(f"{timestamp}{data_str}".encode()).hexdigest()[:20]

    async def _cleanup_expired_data(self):
        while True:
            current_time = datetime.now().timestamp()
            expired_keys = [
                key for key, record in self._data_cache.items()
                if record.expires_at > 0 and current_time > record.expires_at
            ]
            
            for key in expired_keys:
                del self._data_cache[key]
            
            await asyncio.sleep(3600)

    def can_process_locally(self, category: DataCategory) -> bool:
        policy = self._policies.get(category)
        return policy.allow_local_processing if policy else True

    def can_sync_to_cloud(self, category: DataCategory) -> bool:
        policy = self._policies.get(category)
        return policy.allow_cloud_sync if policy else False

    def get_privacy_level(self, category: DataCategory) -> PrivacyLevel:
        policy = self._policies.get(category)
        return policy.privacy_level if policy else PrivacyLevel.SENSITIVE

    def get_policy(self, category: DataCategory) -> Optional[PrivacyPolicy]:
        return self._policies.get(category)

    def get_status(self) -> Dict[str, Any]:
        policies_info = {}
        for category, policy in self._policies.items():
            policies_info[category.value] = {
                "privacy_level": policy.privacy_level.value,
                "retention_days": policy.retention_days,
                "allow_local_processing": policy.allow_local_processing,
                "allow_cloud_sync": policy.allow_cloud_sync,
                "anonymize_required": policy.anonymize_required,
            }
        
        return {
            "initialized": self._initialized,
            "policy_count": len(self._policies),
            "cached_data_count": len(self._data_cache),
            "policies": policies_info,
            "anonymization_enabled": any(p.anonymize_required for p in self._policies.values()),
            "cloud_sync_enabled": any(p.allow_cloud_sync for p in self._policies.values()),
        }

    def get_data_retention_days(self, category: DataCategory) -> int:
        policy = self._policies.get(category)
        return policy.retention_days if policy else 30

    async def get_data_usage_summary(self) -> Dict[str, Any]:
        category_counts = {}
        for record in self._data_cache.values():
            category_counts[record.category.value] = category_counts.get(record.category.value, 0) + 1

        return {
            "total_records": len(self._data_cache),
            "records_by_category": category_counts,
            "anonymized_records": sum(1 for r in self._data_cache.values() if r.is_anonymized),
            "active_policies": len(self._policies),
        }


class FederatedLearningEngine:
    def __init__(self):
        self._local_models: Dict[str, Any] = {}
        self._model_updates: List[Dict[str, Any]] = []
        self._participant_count = 0

    async def train_local_model(self, model_id: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        if model_id not in self._local_models:
            self._local_models[model_id] = {"weights": {}, "data_count": 0}

        model = self._local_models[model_id]
        
        for record in data:
            await self._update_model_weights(model, record)
        
        model["data_count"] += len(data)
        
        update = {
            "model_id": model_id,
            "participant_id": f"local-{self._participant_count}",
            "weights": model["weights"],
            "data_count": model["data_count"],
            "timestamp": datetime.now().timestamp(),
        }
        
        self._model_updates.append(update)
        return update

    async def _update_model_weights(self, model: Dict[str, Any], record: Dict[str, Any]):
        for key, value in record.items():
            if isinstance(value, (int, float)):
                if key not in model["weights"]:
                    model["weights"][key] = {"sum": 0.0, "count": 0}
                model["weights"][key]["sum"] += value
                model["weights"][key]["count"] += 1

    async def aggregate_updates(self, model_id: str) -> Dict[str, Any]:
        updates = [u for u in self._model_updates if u["model_id"] == model_id]
        if not updates:
            return {"error": "No updates available"}

        aggregated_weights = {}
        total_data_count = 0

        for update in updates:
            total_data_count += update["data_count"]
            for key, stats in update["weights"].items():
                if key not in aggregated_weights:
                    aggregated_weights[key] = {"sum": 0.0, "count": 0}
                aggregated_weights[key]["sum"] += stats["sum"]
                aggregated_weights[key]["count"] += stats["count"]

        final_weights = {}
        for key, stats in aggregated_weights.items():
            if stats["count"] > 0:
                final_weights[key] = stats["sum"] / stats["count"]

        return {
            "model_id": model_id,
            "aggregated_weights": final_weights,
            "total_participants": len(updates),
            "total_data_points": total_data_count,
            "timestamp": datetime.now().timestamp(),
        }

    async def get_model_updates(self, model_id: str) -> List[Dict[str, Any]]:
        return [u for u in self._model_updates if u["model_id"] == model_id]

    async def clear_updates(self, model_id: str):
        self._model_updates = [u for u in self._model_updates if u["model_id"] != model_id]
        logger.info(f"Cleared updates for model {model_id}")