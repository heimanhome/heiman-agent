"""
ML-based decision engine (V2).

Replaces the rule-based DecisionEngine with a RandomForestClassifier
for action recommendation from context (anomalies, comfort, activity, time).

Bootstrap training from rule-based engine decisions.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List

import numpy as np

from heiman.ai.decision_engine import DecisionEngine, Decision, ActionSuggestion
from heiman.ai.feature_extractor import FeatureExtractor
from heiman.ai.model_registry import get_model_registry, ModelRegistry

logger = logging.getLogger(__name__)

ACTION_MAP = {
    0: ("none", "正常"),
    1: ("alarm", "报警"),
    2: ("alert", "警告"),
    3: ("adjust_environment", "环境调整"),
    4: ("prepare_home", "准备回家"),
    5: ("welcome_home", "欢迎回家"),
    6: ("secure_home", "离家检查"),
    7: ("leave_home", "离家"),
    8: ("emergency_adjust", "紧急调整"),
}


class DecisionEngineV2:
    """
    ML-powered decision engine.

    Uses RandomForestClassifier to predict the best action from context:
        - Anomalies detected (count, severity)
        - Comfort level (score, level)
        - Current activity
        - Time of day

    Fallback: Rule-based DecisionEngine when model unavailable or
    for critical safety decisions (alarm, gas, smoke).
    """

    def __init__(self, model_registry: Optional[ModelRegistry] = None):
        self._registry = model_registry or get_model_registry()
        self._ml_model = None
        self._rule_engine = DecisionEngine()

        self._load_model()

    @property
    def is_ml_ready(self) -> bool:
        return self._ml_model is not None

    def _load_model(self):
        try:
            model = self._registry.load_model("decision_engine")
            if model is not None:
                self._ml_model = model
                meta = self._registry.get_metadata("decision_engine")
                if meta:
                    logger.info(
                        "[DecisionV2] Loaded ML model v%d (accuracy=%.4f, samples=%d)",
                        meta.version, meta.accuracy or 0, meta.samples_trained,
                    )
        except Exception as e:
            logger.warning("[DecisionV2] Failed to load model: %s", e)

    def generate_decision(self, context: Dict) -> Decision:
        """Generate decision with ML, rule-based fallback for critical/certain cases."""
        # Safety: critical anomalies always use rule-based
        anomaly_results = context.get("anomalies", context.get("anomaly_results", []))
        critical_anomalies = [
            a for a in anomaly_results
            if a.get("severity") == "critical"
        ]
        if critical_anomalies:
            return self._rule_engine.generate_decision(context)

        # Safety: alarm-generating anomaly types always rule-based
        for a in anomaly_results:
            atype = a.get("anomaly_type", "")
            if any(t in atype for t in ["smoke", "gas", "water"]):
                return self._rule_engine.generate_decision(context)

        if self.is_ml_ready:
            try:
                return self._generate_ml(context)
            except Exception as e:
                logger.warning("[DecisionV2] ML decision failed: %s", e)

        return self._rule_engine.generate_decision(context)

    def _generate_ml(self, context: Dict) -> Decision:
        dec_context = {
            "anomalies": context.get("anomalies", context.get("anomaly_results", [])),
            "comfort": context.get("comfort", {}),
            "activity": context.get("activity", {}),
            "device_data": context.get("device_data", []),
        }

        features = FeatureExtractor.extract_decision_features(dec_context)
        X = np.array([
            [features[name] for name in FeatureExtractor.DECISION_FEATURE_NAMES]
        ], dtype=np.float32)

        pred_idx = int(self._ml_model.predict(X)[0])
        proba = self._ml_model.predict_proba(X)[0]
        confidence = float(proba[pred_idx]) if pred_idx < len(proba) else 0.5

        action, action_cn = ACTION_MAP.get(pred_idx, ("none", "正常"))

        # Generate explanation
        anomaly_count = features["anomaly_count"]
        comfort_score = features["comfort_score"]
        comfort_is_poor = features["comfort_is_poor"]

        explanations = {
            "none": "当前家庭状态正常，无需特别操作。",
            "alarm": "检测到严重安全问题，请立即处理！",
            "alert": "检测到异常需要关注。",
            "adjust_environment": "环境舒适度需要调整。",
            "prepare_home": "为您准备舒适的家庭环境。",
            "welcome_home": "欢迎回家！当前家庭状态良好。",
            "secure_home": "检测到未关闭的设备，请确认安全。",
            "leave_home": "所有设备已确认安全，祝您外出愉快！",
            "emergency_adjust": "环境舒适度较差，请立即调整。",
        }

        priority = "normal"
        if action in ("alarm", "emergency_adjust"):
            priority = "critical"
        elif action in ("alert", "secure_home"):
            priority = "high"
        elif action in ("welcome_home", "leave_home"):
            priority = "low"

        return Decision(
            action=action,
            confidence=confidence,
            explanation=explanations.get(action, f"建议执行: {action_cn}"),
            priority=priority,
            details={
                "ml_confidence": round(confidence, 4),
                "anomaly_count": int(anomaly_count),
                "comfort_score": int(comfort_score),
            },
        )

    def suggest_action(self, context: Dict) -> ActionSuggestion:
        decision = self.generate_decision(context)
        return self._rule_engine.suggest_action(context)

    def analyze_home(self, devices_data, events=None):
        return self._rule_engine.analyze_home(devices_data, events or [])

    async def analyze_home_fused(self, home_id: str = "default") -> Dict:
        """代理到 V1 的 analyze_home_fused 方法,融合多源数据(传感器、事件、舒适度等)分析家庭状态."""
        return await self._rule_engine.analyze_home_fused(home_id)

    def summarize_events(self, events):
        return self._rule_engine.summarize_events(events)

    def train(self, use_bootstrap: bool = True) -> Dict:
        """Train the decision engine model."""
        from heiman.ai.feedback_dataset import FeedbackDataset

        dataset = FeedbackDataset()
        X, y = dataset.build_decision_dataset(min_samples=20)
        training_source = "real_feedback" if (X is not None and len(X) >= 50) else "bootstrap"

        if X is None or (use_bootstrap and len(X) < 50):
            X, y = self._generate_bootstrap_data(n_samples=800)
            training_source = "bootstrap"
            logger.info("[DecisionV2] Using bootstrap data: %d samples", len(X))

        if X is None or len(X) < 10:
            return {"success": False, "error": "Insufficient data"}

        X_train, X_test, y_train, y_test = FeedbackDataset.train_test_split(
            X, y, test_size=0.2,
        )

        from sklearn.ensemble import RandomForestClassifier

        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        train_acc = float(model.score(X_train, y_train))
        test_acc = float(model.score(X_test, y_test))

        version = self._registry.save_model(
            model=model,
            model_name="decision_engine",
            model_type="RandomForestClassifier",
            feature_names=FeatureExtractor.DECISION_FEATURE_NAMES,
            accuracy=test_acc,
            samples_trained=len(X),
            training_source=training_source,
            params={
                "n_estimators": 200,
                "max_depth": 12,
                "train_accuracy": train_acc,
                "test_accuracy": test_acc,
                "num_classes": len(model.classes_),
            },
        )

        self._ml_model = model

        # Class stats
        class_stats = {}
        for cls_idx in model.classes_:
            action, cn = ACTION_MAP.get(int(cls_idx), ("unknown", "未知"))
            cls_mask = y_test == cls_idx
            if cls_mask.any():
                cls_acc = float(model.score(X_test[cls_mask], y_test[cls_mask]))
                cls_count = int(cls_mask.sum())
                class_stats[f"{action}"] = {
                    "name": cn,
                    "accuracy": round(cls_acc, 4),
                    "samples": cls_count,
                }

        return {
            "success": True,
            "version": version,
            "model_type": "RandomForestClassifier",
            "samples": len(X),
            "training_source": training_source,
            "num_classes": len(model.classes_),
            "train_accuracy": round(train_acc, 4),
            "test_accuracy": round(test_acc, 4),
            "per_class": class_stats,
        }

    def _generate_bootstrap_data(self, n_samples: int = 800):
        """Generate bootstrap training data from rule-based engine."""
        np.random.seed(42)
        X_list, y_list = [], []

        action_map_rev = {
            "none": 0, "alarm": 1, "alert": 2, "adjust_environment": 3,
            "prepare_home": 4, "welcome_home": 5, "secure_home": 6,
            "leave_home": 7, "emergency_adjust": 8,
        }

        activities = ["sleeping", "awaking", "working", "cooking", "eating",
                      "leaving", "returning", "watching_tv", "unknown"]

        comfort_levels = ["excellent", "good", "fair", "poor"]

        for _ in range(n_samples):
            activity = np.random.choice(activities)

            # Generate context
            anomalies = []
            if np.random.random() < 0.15:
                sev = np.random.choice(["critical", "warning"])
                anomalies = [{
                    "severity": sev,
                    "anomaly_type": np.random.choice([
                        "smoke", "gas", "environment", "battery_low",
                        "device_offline", "water", "door",
                    ]),
                    "message": f"Test anomaly: {sev}",
                }]

            comfort = {
                "score": np.random.uniform(20, 100),
                "level": np.random.choice(comfort_levels),
            }

            context = {
                "anomalies": anomalies,
                "comfort": comfort,
                "activity": {"activity": activity},
                "device_data": [],
            }

            features = FeatureExtractor.extract_decision_features(context)
            X_list.append(np.array(
                [features[name] for name in FeatureExtractor.DECISION_FEATURE_NAMES],
                dtype=np.float32,
            ))

            decision = self._rule_engine.generate_decision(context)
            encoded = action_map_rev.get(decision.action, 0)
            y_list.append(float(encoded))

        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)

    def get_model_info(self) -> Dict:
        meta = self._registry.get_metadata("decision_engine")
        return {
            "ml_ready": self.is_ml_ready,
            "model_type": "RandomForestClassifier" if self.is_ml_ready else "rule_based",
            "version": meta.version if meta else None,
            "accuracy": meta.accuracy if meta else None,
            "samples_trained": meta.samples_trained if meta else 0,
        }


_decision_engine_v2: Optional[DecisionEngineV2] = None


def get_decision_engine_v2() -> DecisionEngineV2:
    global _decision_engine_v2
    if _decision_engine_v2 is None:
        _decision_engine_v2 = DecisionEngineV2()
    return _decision_engine_v2
