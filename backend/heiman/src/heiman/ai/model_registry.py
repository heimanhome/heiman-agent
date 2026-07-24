"""
Model registry for persisting and versioning ML models.

Models are stored as joblib files with metadata JSON in data/models/.
Supports save, load, list, and version tracking.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# Default model storage directory
DEFAULT_MODEL_DIR = Path(os.environ.get("HEIMAN_MODEL_DIR", "data/models"))

# Model names used in the self-learning system
MODEL_NAMES = [
    "comfort_evaluator",
    "anomaly_detector_if",
    "anomaly_detector_clf",
    "behavior_recognizer",
    "decision_engine",
]


class ModelMetadata:
    """Metadata for a persisted ML model."""

    def __init__(
        self,
        model_name: str,
        version: int,
        model_type: str,
        feature_names: List[str],
        created_at: str,
        accuracy: Optional[float] = None,
        samples_trained: int = 0,
        params: Optional[Dict[str, Any]] = None,
        training_source: str = "unknown",
    ):
        self.model_name = model_name
        self.version = version
        self.model_type = model_type
        self.feature_names = feature_names
        self.created_at = created_at
        self.accuracy = accuracy
        self.samples_trained = samples_trained
        self.params = params or {}
        self.training_source = training_source

    def to_dict(self) -> Dict:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "model_type": self.model_type,
            "feature_names": self.feature_names,
            "created_at": self.created_at,
            "accuracy": self.accuracy,
            "samples_trained": self.samples_trained,
            "params": self.params,
            "training_source": self.training_source,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ModelMetadata":
        return cls(
            model_name=data["model_name"],
            version=data["version"],
            model_type=data["model_type"],
            feature_names=data.get("feature_names", []),
            created_at=data["created_at"],
            accuracy=data.get("accuracy"),
            samples_trained=data.get("samples_trained", 0),
            params=data.get("params", {}),
            training_source=data.get("training_source", "unknown"),
        )


class ModelRegistry:
    """
    Registry for saving, loading, and versioning ML models.

    Directory structure:
        data/models/
            comfort_evaluator/
                model_v1.joblib
                model_v2.joblib
                metadata_v1.json
                metadata_v2.json
                active.txt        # contains "v2"
    """

    def __init__(self, model_dir: Optional[Path] = None):
        self._model_dir = Path(model_dir or DEFAULT_MODEL_DIR)
        self._model_dir.mkdir(parents=True, exist_ok=True)

    def _model_path(self, model_name: str) -> Path:
        """Get directory for a specific model."""
        path = self._model_dir / model_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_active_version(self, model_name: str) -> Optional[int]:
        """Read active version from active.txt."""
        active_file = self._model_path(model_name) / "active.txt"
        if not active_file.exists():
            return None
        try:
            content = active_file.read_text().strip()
            if content.startswith("v"):
                return int(content[1:])
            return None
        except (ValueError, FileNotFoundError):
            return None

    def _set_active_version(self, model_name: str, version: int):
        """Write active version to active.txt."""
        active_file = self._model_path(model_name) / "active.txt"
        active_file.write_text(f"v{version}")

    def save_model(
        self,
        model: Any,
        model_name: str,
        model_type: str,
        feature_names: List[str],
        accuracy: Optional[float] = None,
        samples_trained: int = 0,
        params: Optional[Dict] = None,
        training_source: str = "unknown",
    ) -> int:
        """
        Save a model with versioning.

        training_source: 'bootstrap' | 'real_feedback' | 'mixed' | 'unknown'
        """
        import joblib

        current_version = self._get_active_version(model_name) or 0
        new_version = current_version + 1

        model_dir = self._model_path(model_name)
        model_path = model_dir / f"model_v{new_version}.joblib"
        meta_path = model_dir / f"metadata_v{new_version}.json"

        # Save model
        joblib.dump(model, str(model_path))

        # Save metadata
        metadata = ModelMetadata(
            model_name=model_name,
            version=new_version,
            model_type=model_type,
            feature_names=feature_names,
            created_at=datetime.now().isoformat(),
            accuracy=accuracy,
            samples_trained=samples_trained,
            params=params,
            training_source=training_source,
        )
        meta_path.write_text(json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False))

        # Update active version
        self._set_active_version(model_name, new_version)

        logger.info(
            "[ModelRegistry] Saved %s v%d (type=%s, accuracy=%.4f, samples=%d, source=%s)",
            model_name, new_version, model_type, accuracy or 0, samples_trained, training_source,
        )
        return new_version

    def load_model(self, model_name: str, version: Optional[int] = None) -> Optional[Any]:
        """
        Load a model. If version is None, loads the active (latest) version.

        Returns the model object or None if not found.
        """
        import joblib

        if version is None:
            version = self._get_active_version(model_name)
            if version is None:
                logger.warning("[ModelRegistry] No active version for %s", model_name)
                return None

        model_dir = self._model_path(model_name)
        model_path = model_dir / f"model_v{version}.joblib"

        if not model_path.exists():
            logger.warning("[ModelRegistry] Model file not found: %s", model_path)
            return None

        try:
            model = joblib.load(str(model_path))
            logger.info("[ModelRegistry] Loaded %s v%d", model_name, version)
            return model
        except Exception as e:
            logger.error("[ModelRegistry] Failed to load %s v%d: %s", model_name, version, e)
            return None

    def get_metadata(self, model_name: str, version: Optional[int] = None) -> Optional[ModelMetadata]:
        """Get metadata for a model version."""
        if version is None:
            version = self._get_active_version(model_name)
            if version is None:
                return None

        meta_path = self._model_path(model_name) / f"metadata_v{version}.json"
        if not meta_path.exists():
            return None

        try:
            data = json.loads(meta_path.read_text())
            return ModelMetadata.from_dict(data)
        except Exception as e:
            logger.error("[ModelRegistry] Failed to read metadata: %s", e)
            return None

    def get_all_versions(self, model_name: str) -> List[Dict]:
        """Get all versions of a model with metadata."""
        model_dir = self._model_path(model_name)
        versions = []

        for meta_file in sorted(model_dir.glob("metadata_v*.json")):
            try:
                data = json.loads(meta_file.read_text())
                versions.append(data)
            except Exception:
                continue

        return versions

    def get_all_models_status(self) -> List[Dict]:
        """Get status summary for all registered models."""
        result = []
        for model_name in MODEL_NAMES:
            active_version = self._get_active_version(model_name)
            metadata = self.get_metadata(model_name) if active_version else None
            all_versions = self.get_all_versions(model_name)

            result.append({
                "model_name": model_name,
                "active_version": active_version,
                "exists": active_version is not None,
                "total_versions": len(all_versions),
                "latest_accuracy": metadata.accuracy if metadata else None,
                "latest_samples": metadata.samples_trained if metadata else 0,
                "latest_created_at": metadata.created_at if metadata else None,
                "latest_training_source": metadata.training_source if metadata else "unknown",
                "versions": all_versions,
                "has_model_file": (self._model_path(model_name) / f"model_v{active_version}.joblib").exists() if active_version else False,
            })

        return result

    def delete_version(self, model_name: str, version: int) -> bool:
        """Delete a specific model version."""
        model_dir = self._model_path(model_name)
        model_path = model_dir / f"model_v{version}.joblib"
        meta_path = model_dir / f"metadata_v{version}.json"

        deleted = False
        if model_path.exists():
            model_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
            deleted = True

        if deleted:
            active = self._get_active_version(model_name)
            if active == version:
                # Find next latest version
                all_versions = self.get_all_versions(model_name)
                if all_versions:
                    self._set_active_version(model_name, all_versions[-1]["version"])
                else:
                    active_file = self._model_path(model_name) / "active.txt"
                    if active_file.exists():
                        active_file.unlink()

        return deleted

    def model_exists(self, model_name: str) -> bool:
        """Check if a model has been saved."""
        return self._get_active_version(model_name) is not None


# Singleton
_model_registry: Optional[ModelRegistry] = None


def get_model_registry(model_dir: Optional[Path] = None) -> ModelRegistry:
    """Get or create the global model registry."""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry(model_dir)
    return _model_registry
