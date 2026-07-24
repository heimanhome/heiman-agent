import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from uuid import uuid4

from heiman.database.connector import get_db_connector

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNCERTAIN = "uncertain"
    MANUAL_OVERRIDE = "manual_override"


class LearningStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class ModelName(str, Enum):
    ANOMALY_DETECTOR = "anomaly_detector"
    BEHAVIOR_RECOGNIZER = "behavior_recognizer"
    COMFORT_EVALUATOR = "comfort_evaluator"
    RULE_GENERATOR = "rule_generator"
    DECISION_ENGINE = "decision_engine"


class FeedbackCollector:
    def __init__(self):
        self._db = get_db_connector()
        self._pending_feedback: List[Dict] = []
        self._flush_interval = 30
        self._flush_lock = threading.Lock()
        self._start_flush_thread()

    def _start_flush_thread(self):
        def flush_loop():
            while True:
                time.sleep(self._flush_interval)
                self._flush_pending()

        thread = threading.Thread(target=flush_loop, daemon=True)
        thread.start()

    def _flush_pending(self):
        with self._flush_lock:
            if not self._pending_feedback:
                return

            try:
                with self._db.get_connection() as conn:
                    cursor = conn.cursor()
                    for feedback in self._pending_feedback:
                        cursor.execute("""
                            INSERT INTO model_feedback (
                                feedback_id, model_name, prediction_id,
                                input_features, predicted_output, actual_output,
                                feedback_type, confidence, user_id, metadata
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            feedback["feedback_id"],
                            feedback["model_name"],
                            feedback.get("prediction_id"),
                            json.dumps(feedback["input_features"]),
                            json.dumps(feedback["predicted_output"]),
                            json.dumps(feedback["actual_output"]) if feedback.get("actual_output") else None,
                            feedback["feedback_type"],
                            feedback.get("confidence"),
                            feedback.get("user_id"),
                            json.dumps(feedback.get("metadata", {})) if feedback.get("metadata") else None,
                        ))
                    conn.commit()

                logger.info("[FeedbackCollector] Flushed %d feedback records", len(self._pending_feedback))
                self._pending_feedback.clear()
            except Exception as e:
                logger.error("[FeedbackCollector] Failed to flush feedback: %s", e)

    def record_feedback(self, model_name: str, input_features: Dict, predicted_output: Dict,
                        actual_output: Dict | None = None, feedback_type: FeedbackType = FeedbackType.UNCERTAIN,
                        confidence: float = 0.0, prediction_id: str | None = None,
                        user_id: str | None = None, metadata: Dict | None = None):
        feedback = {
            "feedback_id": str(uuid4()),
            "model_name": model_name,
            "prediction_id": prediction_id,
            "input_features": input_features,
            "predicted_output": predicted_output,
            "actual_output": actual_output,
            "feedback_type": feedback_type.value,
            "confidence": confidence,
            "user_id": user_id,
            "metadata": metadata,
        }

        with self._flush_lock:
            self._pending_feedback.append(feedback)

        if len(self._pending_feedback) >= 100:
            self._flush_pending()

    def get_feedback_by_model(self, model_name: str, limit: int = 100) -> List[Dict]:
        try:
            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                rows = cursor.execute(
                    "SELECT * FROM model_feedback WHERE model_name = ? ORDER BY timestamp DESC LIMIT ?",
                    (model_name, limit),
                ).fetchall()

                result = []
                for row in rows:
                    result.append({
                        "feedback_id": row["feedback_id"],
                        "model_name": row["model_name"],
                        "prediction_id": row["prediction_id"],
                        "input_features": json.loads(row["input_features"]) if row["input_features"] else {},
                        "predicted_output": json.loads(row["predicted_output"]) if row["predicted_output"] else {},
                        "actual_output": json.loads(row["actual_output"]) if row["actual_output"] else None,
                        "feedback_type": row["feedback_type"],
                        "confidence": row["confidence"],
                        "user_id": row["user_id"],
                        "timestamp": row["timestamp"],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    })
                return result
        except Exception as e:
            logger.error("[FeedbackCollector] Failed to get feedback: %s", e)
            return []

    def get_feedback_count_by_model(self, model_name: str) -> int:
        """Get total feedback count for a specific model."""
        try:
            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM model_feedback WHERE model_name = ?",
                    (model_name,),
                ).fetchone()
                return row["cnt"] if row else 0
        except Exception as e:
            logger.error("[FeedbackCollector] Failed to get feedback count: %s", e)
            return 0

    def get_total_feedback_count(self) -> int:
        """Get total feedback count across all models."""
        try:
            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM model_feedback"
                ).fetchone()
                return row["cnt"] if row else 0
        except Exception as e:
            logger.error("[FeedbackCollector] Failed to get total feedback count: %s", e)
            return 0


class PerformanceAnalyzer:
    def __init__(self):
        self._db = get_db_connector()

    def analyze_model_performance(self, model_name: str, window_hours: int = 24) -> Dict:
        try:
            window_end = datetime.now()
            window_start = window_end - timedelta(hours=window_hours)

            with self._db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT feedback_type, COUNT(*) as cnt 
                    FROM model_feedback 
                    WHERE model_name = ? AND timestamp >= ? AND timestamp <= ?
                    GROUP BY feedback_type
                """, (model_name, window_start.isoformat(), window_end.isoformat()))

                feedback_counts = {}
                for row in cursor.fetchall():
                    feedback_counts[row["feedback_type"]] = row["cnt"]

                total = sum(feedback_counts.values())
                correct = feedback_counts.get("correct", 0)
                incorrect = feedback_counts.get("incorrect", 0)
                uncertain = feedback_counts.get("uncertain", 0)
                verified = correct + incorrect

                accuracy = 0.0
                if verified > 0:
                    accuracy = correct / verified
                elif total > 0:
                    # No verified feedback yet, report neutral accuracy
                    accuracy = 0.5

                cursor.execute("""
                    SELECT AVG(confidence) as avg_confidence, COUNT(*) as cnt
                    FROM model_feedback 
                    WHERE model_name = ? AND timestamp >= ? AND timestamp <= ? AND confidence IS NOT NULL
                """, (model_name, window_start.isoformat(), window_end.isoformat()))

                confidence_row = cursor.fetchone()
                avg_confidence = confidence_row["avg_confidence"] if confidence_row and confidence_row["avg_confidence"] else 0.0

                cursor.execute("""
                    SELECT input_features, predicted_output, actual_output, confidence
                    FROM model_feedback 
                    WHERE model_name = ? AND feedback_type = 'incorrect' AND timestamp >= ?
                    ORDER BY confidence DESC LIMIT 20
                """, (model_name, window_start.isoformat()))

                error_cases = []
                for row in cursor.fetchall():
                    error_cases.append({
                        "input_features": json.loads(row["input_features"]) if row["input_features"] else {},
                        "predicted": json.loads(row["predicted_output"]) if row["predicted_output"] else {},
                        "actual": json.loads(row["actual_output"]) if row["actual_output"] else {},
                        "confidence": row["confidence"],
                    })

                cursor.execute("""
                    SELECT metric_type, AVG(value) as avg_value, COUNT(*) as cnt
                    FROM performance_metrics
                    WHERE model_name = ? AND window_start >= ?
                    GROUP BY metric_type
                """, (model_name, window_start.isoformat()))

                metrics = {}
                for row in cursor.fetchall():
                    metrics[row["metric_type"]] = {
                        "average": row["avg_value"],
                        "samples": row["cnt"],
                    }

            # Count learning cycles for this model
            cycle_count = 0
            try:
                cycle_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM learning_cycles WHERE model_name = ?",
                    (model_name,),
                ).fetchone()
                cycle_count = cycle_row["cnt"] if cycle_row else 0
            except Exception:
                pass

            needs_learning = (
                total >= 5  # 至少 5 条反馈
                and verified >= 3  # 至少 3 条已验证
                and accuracy < 0.7  # 准确率低于 70%
            ) or (incorrect >= 3)  # 或有 3 条以上的错误反馈

            return {
                "model_name": model_name,
                "accuracy": round(accuracy, 4),
                "precision": round(accuracy, 4),
                "recall": round(accuracy, 4),
                "f1_score": round(accuracy, 4),
                "feedback_count": total,
                "verified_count": verified,
                "correct_count": correct,
                "incorrect_count": incorrect,
                "uncertain_count": uncertain,
                "needs_learning": needs_learning,
                "learning_cycles": cycle_count,
                "window_hours": window_hours,
            }
        except Exception as e:
            logger.error("[PerformanceAnalyzer] Failed to analyze performance: %s", e)
            return {"model_name": model_name, "error": str(e)}

    def get_feedback_by_model(self, model_name: str, limit: int = 500) -> List[Dict]:
        """Get feedback records for a specific model (delegated from FeedbackCollector)."""
        collector = FeedbackCollector()
        return collector.get_feedback_by_model(model_name, limit)

    def identify_problematic_patterns(self, model_name: str) -> List[Dict]:
        try:
            feedback = self.get_feedback_by_model(model_name, limit=500)
            error_feedback = [f for f in feedback if f["feedback_type"] == "incorrect"]

            if not error_feedback:
                return []

            patterns = {}
            for item in error_feedback:
                input_features = item["input_features"]
                predicted = item["predicted_output"]
                actual = item["actual_output"]

                key_features = self._extract_key_features(input_features)
                pattern_key = json.dumps(key_features, sort_keys=True)

                if pattern_key not in patterns:
                    patterns[pattern_key] = {
                        "key_features": key_features,
                        "count": 0,
                        "examples": [],
                        "total_confidence": 0.0,
                        "first_seen": item["timestamp"],
                    }

                patterns[pattern_key]["count"] += 1
                patterns[pattern_key]["total_confidence"] += item.get("confidence", 0.0)
                if len(patterns[pattern_key]["examples"]) < 5:
                    patterns[pattern_key]["examples"].append({
                        "predicted": predicted,
                        "actual": actual,
                        "confidence": item["confidence"],
                    })
                if item["timestamp"] < patterns[pattern_key]["first_seen"]:
                    patterns[pattern_key]["first_seen"] = item["timestamp"]

            # Transform to frontend-expected format
            result = []
            sorted_patterns = sorted(patterns.values(), key=lambda x: x["count"], reverse=True)
            for idx, p in enumerate(sorted_patterns[:20]):
                # Determine severity based on count
                if p["count"] >= 10:
                    severity = "high"
                elif p["count"] >= 5:
                    severity = "medium"
                else:
                    severity = "low"

                # Determine pattern type
                feature_keys = list(p["key_features"].keys())
                if "sensor_type" in feature_keys:
                    pattern_type = "sensor_detection"
                elif "device_type" in feature_keys:
                    pattern_type = "device_classification"
                elif "room" in feature_keys:
                    pattern_type = "room_automation"
                else:
                    pattern_type = "rule_generation"

                # Build description from key features
                desc_parts = [f"{k}={v}" for k, v in p["key_features"].items()][:3]
                description = f"Frequent errors for: {', '.join(desc_parts)}" if desc_parts else "Pattern with similar input features"

                # Generate suggested fix
                suggested_fix = "Review training data and add more examples for this pattern"
                avg_confidence = p["total_confidence"] / p["count"] if p["count"] > 0 else 0
                if avg_confidence > 0.7:
                    suggested_fix = "High confidence errors - check for contradictory labels in training data"
                elif avg_confidence < 0.3:
                    suggested_fix = "Low confidence predictions - increase training data coverage"

                result.append({
                    "pattern_id": f"pattern_{model_name}_{idx}",
                    "model_name": model_name,
                    "pattern_type": pattern_type,
                    "description": description,
                    "severity": severity,
                    "affected_count": p["count"],
                    "suggested_fix": suggested_fix,
                    "detected_at": p["first_seen"],
                })

            return result
        except Exception as e:
            logger.error("[PerformanceAnalyzer] Failed to identify patterns: %s", e)
            return []

    def _extract_key_features(self, input_features: Dict) -> Dict:
        key_fields = ["sensor_type", "device_type", "room", "hour", "day_of_week", "status"]
        result = {}
        for field in key_fields:
            if field in input_features:
                result[field] = input_features[field]

        if "properties" in input_features and isinstance(input_features["properties"], dict):
            # 兼容 IoT 原始属性名 (PascalCase) 和标准化属性名 (camelCase)
            for prop in ["switchState", "contactState", "motionState", "temperature", "humidity",
                         "SwitchState", "ContactState"]:
                if prop in input_features["properties"]:
                    # 统一存储为 camelCase
                    key = prop[0].lower() + prop[1:] if prop[0].isupper() else prop
                    result[key] = input_features["properties"][prop]

        return result

    def record_metric(self, model_name: str, metric_type: str, value: float,
                      window_start: datetime, window_end: datetime, sample_count: int = 1):
        try:
            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO performance_metrics (
                        metric_id, model_name, metric_type, value,
                        window_start, window_end, sample_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid4()),
                    model_name,
                    metric_type,
                    value,
                    window_start.isoformat(),
                    window_end.isoformat(),
                    sample_count,
                ))
                conn.commit()
        except Exception as e:
            logger.error("[PerformanceAnalyzer] Failed to record metric: %s", e)


class LearningEngine:
    def __init__(self):
        self._db = get_db_connector()
        self._status = LearningStatus.IDLE
        self._lock = asyncio.Lock()
        self._min_samples_for_learning = 5  # 降低门槛：50 → 5，确保学习能触发
        self._min_accuracy_threshold = 0.6  # 降低准确率门槛

    @property
    def status(self) -> LearningStatus:
        return self._status

    async def start_learning_cycle(self, model_name: str) -> Dict:
        async with self._lock:
            if self._status == LearningStatus.RUNNING:
                return {"error": "Learning cycle already running"}

            self._status = LearningStatus.RUNNING
            cycle_id = str(uuid4())
            start_time = datetime.now()

            try:
                # 先刷新所有待处理的反馈到数据库，确保分析能看到最新数据
                try:
                    from heiman.ai.self_learning_system import get_self_learning_monitor as _get_monitor
                    _mon = _get_monitor()
                    _mon.get_feedback_collector()._flush_pending()
                except Exception:
                    pass

                analyzer = PerformanceAnalyzer()
                feedback_collector = FeedbackCollector()

                before_performance = analyzer.analyze_model_performance(model_name, window_hours=72)
                feedback_count = before_performance.get("feedback_count", 0)

                if feedback_count < self._min_samples_for_learning:
                    end_time = datetime.now()
                    self._record_cycle(
                        cycle_id=cycle_id,
                        model_name=model_name,
                        status="skipped",
                        samples_analyzed=feedback_count,
                        performance_before=before_performance.get("accuracy", 0),
                        performance_after=before_performance.get("accuracy", 0),
                        improvements_made=0,
                        error_message=f"Insufficient samples: {feedback_count} < {self._min_samples_for_learning}",
                        start_time=start_time,
                        end_time=end_time,
                    )
                    self._status = LearningStatus.IDLE
                    return {
                        "cycle_id": cycle_id,
                        "model_name": model_name,
                        "status": "skipped",
                        "started_at": start_time.isoformat(),
                        "completed_at": end_time.isoformat(),
                        "feedback_used": feedback_count,
                        "rules_generated": 0,
                        "duration_ms": int((end_time - start_time).total_seconds() * 1000),
                        "reason": f"Insufficient samples: {feedback_count} < {self._min_samples_for_learning}",
                    }

                problematic_patterns = analyzer.identify_problematic_patterns(model_name)

                improvements_made = await self._apply_learning(model_name, problematic_patterns, before_performance)

                after_performance = analyzer.analyze_model_performance(model_name, window_hours=72)
                end_time = datetime.now()

                self._record_cycle(
                    cycle_id=cycle_id,
                    model_name=model_name,
                    status="completed",
                    samples_analyzed=feedback_count,
                    improvements_made=improvements_made,
                    performance_before=before_performance.get("accuracy", 0),
                    performance_after=after_performance.get("accuracy", 0),
                    start_time=start_time,
                    end_time=end_time,
                )

                self._status = LearningStatus.IDLE

                return {
                    "cycle_id": cycle_id,
                    "model_name": model_name,
                    "status": "completed",
                    "started_at": start_time.isoformat(),
                    "completed_at": end_time.isoformat(),
                    "feedback_used": feedback_count,
                    "rules_generated": improvements_made,
                    "duration_ms": int((end_time - start_time).total_seconds() * 1000),
                    "problematic_patterns_found": len(problematic_patterns),
                    "performance_before": round(before_performance.get("accuracy", 0), 4),
                    "performance_after": round(after_performance.get("accuracy", 0), 4),
                }
            except Exception as e:
                end_time = datetime.now()
                self._record_cycle(
                    cycle_id=cycle_id,
                    model_name=model_name,
                    status="failed",
                    error_message=str(e),
                    start_time=start_time,
                    end_time=end_time,
                )
                self._status = LearningStatus.ERROR
                logger.error("[LearningEngine] Learning cycle failed: %s", e)
                return {
                    "cycle_id": cycle_id,
                    "model_name": model_name,
                    "status": "failed",
                    "started_at": start_time.isoformat(),
                    "completed_at": end_time.isoformat(),
                    "feedback_used": 0,
                    "rules_generated": 0,
                    "duration_ms": int((end_time - start_time).total_seconds() * 1000),
                    "error": str(e),
                }

    async def _apply_learning(self, model_name: str, patterns: List[Dict], performance: Dict) -> int:
        improvements_made = 0

        for pattern in patterns[:5]:
            if pattern["count"] >= 3:
                await self._create_learning_rule(model_name, pattern)
                improvements_made += 1

        if model_name == ModelName.BEHAVIOR_RECOGNIZER.value:
            improvements_made += await self._adjust_behavior_thresholds(model_name, performance)

        if model_name == ModelName.ANOMALY_DETECTOR.value:
            improvements_made += await self._tune_anomaly_thresholds(model_name, performance)

        return improvements_made

    async def _create_learning_rule(self, model_name: str, pattern: Dict) -> bool:
        try:
            rule_id = str(uuid4())
            condition = json.dumps(pattern["key_features"])

            action = {
                "type": "adjust_prediction",
                "pattern_key": json.dumps(pattern["key_features"], sort_keys=True),
                "correct_output": pattern["examples"][0].get("actual", {}),
            }

            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO learning_rules (
                        rule_id, model_name, rule_type, condition, action, confidence_threshold
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    rule_id,
                    model_name,
                    "correction",
                    condition,
                    json.dumps(action),
                    0.6,
                ))
                conn.commit()

            logger.info("[LearningEngine] Created learning rule for %s: %s", model_name, pattern["key_features"])
            return True
        except Exception as e:
            logger.error("[LearningEngine] Failed to create learning rule: %s", e)
            return False

    async def _adjust_behavior_thresholds(self, model_name: str, performance: Dict) -> int:
        try:
            improvements = 0
            accuracy = performance.get("accuracy", 0)

            if accuracy < 0.6:
                with self._db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO learning_rules (
                            rule_id, model_name, rule_type, condition, action, confidence_threshold
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid4()),
                        model_name,
                        "threshold_adjustment",
                        json.dumps({"accuracy": "<0.6"}),
                        json.dumps({"action": "lower_confidence_threshold", "value": 0.5}),
                        0.5,
                    ))
                    conn.commit()
                improvements += 1

            return improvements
        except Exception as e:
            logger.error("[LearningEngine] Failed to adjust behavior thresholds: %s", e)
            return 0

    async def _tune_anomaly_thresholds(self, model_name: str, performance: Dict) -> int:
        try:
            improvements = 0
            error_cases = performance.get("error_cases", [])

            if len(error_cases) >= 5:
                with self._db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO learning_rules (
                            rule_id, model_name, rule_type, condition, action, confidence_threshold
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid4()),
                        model_name,
                        "threshold_adjustment",
                        json.dumps({"error_count": ">=5"}),
                        json.dumps({"action": "increase_sensitivity"}),
                        0.5,
                    ))
                    conn.commit()
                improvements += 1

            return improvements
        except Exception as e:
            logger.error("[LearningEngine] Failed to tune anomaly thresholds: %s", e)
            return 0

    def _record_cycle(self, cycle_id: str, model_name: str, status: str,
                      samples_analyzed: int = 0, improvements_made: int = 0,
                      performance_before: float = 0, performance_after: float = 0,
                      error_message: str = "",
                      start_time: Optional[datetime] = None,
                      end_time: Optional[datetime] = None):
        try:
            now = datetime.now()
            st = start_time or now
            et = end_time or now
            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO learning_cycles (
                        cycle_id, model_name, status, start_time, end_time,
                        samples_analyzed, improvements_made,
                        performance_before, performance_after, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cycle_id,
                    model_name,
                    status,
                    st.isoformat(),
                    et.isoformat(),
                    samples_analyzed,
                    improvements_made,
                    performance_before,
                    performance_after,
                    error_message,
                ))
                conn.commit()
        except Exception as e:
            logger.error("[LearningEngine] Failed to record cycle: %s", e)

    def get_learning_rules(self, model_name: str | None = None) -> List[Dict]:
        try:
            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                if model_name:
                    rows = cursor.execute(
                        "SELECT * FROM learning_rules WHERE model_name = ? ORDER BY last_updated DESC",
                        (model_name,),
                    ).fetchall()
                else:
                    rows = cursor.execute(
                        "SELECT * FROM learning_rules ORDER BY last_updated DESC",
                    ).fetchall()

                result = []
                for row in rows:
                    result.append({
                        "rule_id": row["rule_id"],
                        "model_name": row["model_name"],
                        "rule_type": row["rule_type"],
                        "condition": row["condition"] or "",
                        "action": row["action"] or "",
                        "confidence": row["confidence_threshold"] or 0.0,
                        "enabled": bool(row["enabled"]),
                        "created_at": row["created_at"],
                        "applied_count": 0,
                    })
                return result
        except Exception as e:
            logger.error("[LearningEngine] Failed to get learning rules: %s", e)
            return []

    def get_learning_cycles(self, model_name: str | None = None, limit: int = 20) -> List[Dict]:
        try:
            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                if model_name:
                    rows = cursor.execute(
                        "SELECT * FROM learning_cycles WHERE model_name = ? ORDER BY start_time DESC LIMIT ?",
                        (model_name, limit),
                    ).fetchall()
                else:
                    rows = cursor.execute(
                        "SELECT * FROM learning_cycles ORDER BY start_time DESC LIMIT ?",
                        (limit,),
                    ).fetchall()

                result = []
                for row in rows:
                    started_at = row["start_time"]
                    completed_at = row["end_time"]
                    # Calculate duration in ms
                    duration_ms = None
                    if started_at and completed_at:
                        try:
                            st = datetime.fromisoformat(started_at)
                            et = datetime.fromisoformat(completed_at)
                            duration_ms = int((et - st).total_seconds() * 1000)
                        except Exception:
                            pass

                    result.append({
                        "cycle_id": row["cycle_id"],
                        "model_name": row["model_name"],
                        "status": row["status"],
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "feedback_used": row["samples_analyzed"],
                        "rules_generated": row["improvements_made"],
                        "duration_ms": duration_ms,
                    })
                return result
        except Exception as e:
            logger.error("[LearningEngine] Failed to get learning cycles: %s", e)
            return []


class SelfLearningMonitor:
    def __init__(self):
        self._feedback_collector = FeedbackCollector()
        self._performance_analyzer = PerformanceAnalyzer()
        self._learning_engine = LearningEngine()
        self._learning_interval = 300  # 5分钟检查一次（原 3600）
        self._task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            logger.info("[SelfLearningMonitor] Already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("[SelfLearningMonitor] Self-learning monitor started")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("[SelfLearningMonitor] Self-learning monitor stopped")

    async def _run(self):
        # 启动后立即执行第一次检查
        await self._perform_learning_check()

        while self._running:
            try:
                await asyncio.sleep(self._learning_interval)

                if not self._running:
                    break

                await self._perform_learning_check()

            except asyncio.CancelledError:
                logger.info("[SelfLearningMonitor] Task cancelled")
                break
            except Exception as e:
                logger.error("[SelfLearningMonitor] Error in learning loop: %s", e)
                await asyncio.sleep(60)

    async def _perform_learning_check(self):
        for model_name in [m.value for m in ModelName]:
            performance = self._performance_analyzer.analyze_model_performance(model_name)

            if performance.get("needs_learning", False):
                logger.info("[SelfLearningMonitor] Triggering learning for %s - accuracy: %.4f",
                            model_name, performance.get("accuracy", 0))
                result = await self._learning_engine.start_learning_cycle(model_name)
                logger.info("[SelfLearningMonitor] Learning cycle result for %s: %s", model_name, result.get("status"))

            self._performance_analyzer.record_metric(
                model_name=model_name,
                metric_type="accuracy",
                value=performance.get("accuracy", 0),
                window_start=datetime.now() - timedelta(hours=1),
                window_end=datetime.now(),
                sample_count=performance.get("feedback_count", 0),
            )

    def get_status(self) -> Dict:
        models_status = []
        total_feedback = 0
        last_cycle_time = None

        for model in ModelName:
            model_name = model.value
            # Get feedback count per model
            feedback_count = self._feedback_collector.get_feedback_count_by_model(model_name)
            total_feedback += feedback_count

            # Get last learning time from cycles
            cycles = self._learning_engine.get_learning_cycles(model_name, limit=1)
            last_learning_time = cycles[0]["completed_at"] if cycles else None
            if last_learning_time and (last_cycle_time is None or last_learning_time > last_cycle_time):
                last_cycle_time = last_learning_time

            # Determine model status
            performance = self._performance_analyzer.analyze_model_performance(model_name, window_hours=24)
            model_status = "active" if self._running else "idle"
            if performance.get("feedback_count", 0) > 0:
                model_status = "active"

            models_status.append({
                "name": model_name,
                "status": model_status,
                "last_learning_time": last_learning_time,
                "feedback_count": feedback_count,
            })

        return {
            "is_running": self._running,
            "models": models_status,
            "total_feedback_count": total_feedback,
            "last_cycle_time": last_cycle_time,
        }

    def get_feedback_collector(self) -> FeedbackCollector:
        return self._feedback_collector

    def get_performance_analyzer(self) -> PerformanceAnalyzer:
        return self._performance_analyzer

    def get_learning_engine(self) -> LearningEngine:
        return self._learning_engine


_self_learning_monitor = None


def get_self_learning_monitor() -> SelfLearningMonitor:
    global _self_learning_monitor
    if _self_learning_monitor is None:
        _self_learning_monitor = SelfLearningMonitor()
    return _self_learning_monitor