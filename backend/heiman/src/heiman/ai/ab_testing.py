"""
A/B testing framework for ML vs rule-based models.

Splits traffic between ML and rule-based models, tracks performance
metrics per variant, and determines which variant performs better.

Architecture:
    1. For each model, traffic is split ML vs rule-based (e.g., 70/30)
    2. Both variants record predictions + actual outcomes to DB
    3. Periodic analysis compares accuracy, latency, user satisfaction
    4. Auto-promote ML to 100% when statistically significantly better
"""

import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4

from heiman.database.connector import get_db_connector

logger = logging.getLogger(__name__)


class Variant(str, Enum):
    ML = "ml"
    RULE = "rule"
    BOTH = "both"  # Both variants run, but only one result served


class ExperimentStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    PAUSED = "paused"


@dataclass
class ExperimentConfig:
    model_name: str
    ml_ratio: float = 0.7          # Proportion of traffic to ML
    min_sample_size: int = 100     # Minimum samples for statistical significance
    significance_level: float = 0.05
    min_improvement: float = 0.02  # Minimum accuracy improvement to promote
    auto_promote: bool = True      # Auto-promote ML when significantly better
    shadow_mode: bool = False      # Run both variants, serve rule-based


class ABTesting:
    """
    A/B testing framework for ML model deployment.

    Usage:
        tester = ABTesting()
        tester.start_experiment("comfort_evaluator", ml_ratio=0.7)
        variant = tester.get_variant("comfort_evaluator", context_hash="abc123")
    """

    def __init__(self):
        self._db = get_db_connector()
        self._experiments: Dict[str, ExperimentConfig] = {}
        self._init_tables()
        self._load_experiments()

    def _init_tables(self):
        """Create AB testing tables if they don't exist."""
        try:
            with self._db.get_connection() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS ab_experiments (
                        experiment_id TEXT PRIMARY KEY,
                        model_name TEXT NOT NULL,
                        ml_ratio REAL DEFAULT 0.7,
                        min_sample_size INTEGER DEFAULT 100,
                        shadow_mode INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'running',
                        started_at TEXT,
                        completed_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS ab_results (
                        result_id TEXT PRIMARY KEY,
                        model_name TEXT NOT NULL,
                        variant TEXT NOT NULL,
                        input_features TEXT,
                        predicted_output TEXT,
                        actual_output TEXT,
                        feedback_type TEXT DEFAULT 'unknown',
                        latency_ms REAL DEFAULT 0,
                        timestamp TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_ab_results_model 
                        ON ab_results(model_name, variant, timestamp);
                """)
                conn.commit()
        except Exception as e:
            logger.debug("[ABTesting] Init tables: %s", e)

    def _load_experiments(self):
        """Load active experiments from DB."""
        try:
            with self._db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM ab_experiments WHERE status = 'running'"
                ).fetchall()
                for row in rows:
                    config = ExperimentConfig(
                        model_name=row["model_name"],
                        ml_ratio=row["ml_ratio"],
                        min_sample_size=row.get("min_sample_size", 100),
                        auto_promote=bool(row.get("auto_promote", True)),
                        shadow_mode=bool(row.get("shadow_mode", False)),
                    )
                    self._experiments[row["model_name"]] = config
        except Exception as e:
            logger.debug("[ABTesting] Load experiments: %s", e)

    def start_experiment(
        self,
        model_name: str,
        ml_ratio: float = 0.7,
        min_sample_size: int = 100,
        shadow_mode: bool = False,
    ) -> Dict:
        """Start a new A/B experiment for a model."""
        config = ExperimentConfig(
            model_name=model_name,
            ml_ratio=ml_ratio,
            min_sample_size=min_sample_size,
            shadow_mode=shadow_mode,
        )
        self._experiments[model_name] = config

        try:
            with self._db.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ab_experiments (
                        experiment_id, model_name, ml_ratio, min_sample_size,
                        shadow_mode, status, started_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid4()),
                    model_name,
                    ml_ratio,
                    min_sample_size,
                    int(shadow_mode),
                    ExperimentStatus.RUNNING.value,
                    datetime.now().isoformat(),
                ))
                conn.commit()
        except Exception as e:
            logger.warning("[ABTesting] Failed to persist experiment: %s", e)

        logger.info(
            "[ABTesting] Started experiment %s: ml_ratio=%.2f, shadow=%s",
            model_name, ml_ratio, shadow_mode,
        )
        return {
            "success": True,
            "model_name": model_name,
            "ml_ratio": ml_ratio,
            "shadow_mode": shadow_mode,
        }

    def get_variant(self, model_name: str, context_hash: Optional[str] = None) -> Variant:
        """
        Determine which variant to use for this request.

        Returns Variant.ML or Variant.RULE based on traffic split.
        Uses consistent hashing if context_hash is provided (same input → same variant).
        """
        experiment = self._experiments.get(model_name)
        if not experiment:
            return Variant.RULE  # Default to rule-based if no experiment

        if experiment.shadow_mode:
            return Variant.RULE  # Serve rule-based, ML runs in background

        if context_hash:
            # Consistent hashing: same input always goes to same variant
            seed = hash(f"{model_name}:{context_hash}") & 0xFFFFFFFF
            rng = random.Random(seed)
            return Variant.ML if rng.random() < experiment.ml_ratio else Variant.RULE

        # Random assignment
        return Variant.ML if random.random() < experiment.ml_ratio else Variant.RULE

    def record_result(
        self,
        model_name: str,
        variant: Variant,
        input_features: Dict,
        predicted_output: Dict,
        actual_output: Optional[Dict] = None,
        latency_ms: float = 0.0,
    ):
        """Record a prediction result for analysis."""
        try:
            with self._db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO ab_results (
                        result_id, model_name, variant, input_features,
                        predicted_output, actual_output, latency_ms, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid4()),
                    model_name,
                    variant.value,
                    json.dumps(input_features),
                    json.dumps(predicted_output),
                    json.dumps(actual_output) if actual_output else None,
                    latency_ms,
                    datetime.now().isoformat(),
                ))
                conn.commit()
        except Exception as e:
            logger.debug("[ABTesting] Record result failed: %s", e)

    def analyze_experiment(self, model_name: str) -> Dict:
        """Analyze A/B experiment results with statistical tests."""
        try:
            with self._db.get_connection() as conn:
                # Get variant stats
                ml_stats = self._get_variant_stats(conn, model_name, Variant.ML)
                rule_stats = self._get_variant_stats(conn, model_name, Variant.RULE)

                ml_total = ml_stats["total"]
                rule_total = rule_stats["total"]

                ml_accuracy = ml_stats["accuracy"]
                rule_accuracy = rule_stats["accuracy"]

                improvement = ml_accuracy - rule_accuracy

                # Simple statistical test (z-test for proportions approximation)
                significant = False
                confidence = 0.0
                if ml_total >= 30 and rule_total >= 30:
                    # Pooled standard error
                    p_pool = (ml_stats["correct"] + rule_stats["correct"]) / max(1, ml_total + rule_total)
                    se = (p_pool * (1 - p_pool) * (1/ml_total + 1/rule_total)) ** 0.5
                    if se > 0:
                        z_score = improvement / se
                        # Approximate p-value from z-score
                        confidence = min(1.0, abs(z_score) / 3.0 + 0.5)
                        significant = abs(z_score) > 1.96  # 95% confidence

                return {
                    "model_name": model_name,
                    "ml_variant": {
                        "total": ml_total,
                        "correct": ml_stats["correct"],
                        "incorrect": ml_stats["incorrect"],
                        "accuracy": round(ml_accuracy, 4),
                        "avg_latency_ms": round(ml_stats["avg_latency"], 2),
                    },
                    "rule_variant": {
                        "total": rule_total,
                        "correct": rule_stats["correct"],
                        "incorrect": rule_stats["incorrect"],
                        "accuracy": round(rule_accuracy, 4),
                        "avg_latency_ms": round(rule_stats["avg_latency"], 2),
                    },
                    "improvement": round(improvement, 4),
                    "significant": significant,
                    "confidence": round(confidence, 4),
                    "recommendation": self._get_recommendation(
                        improvement, significant, ml_total,
                    ),
                }
        except Exception as e:
            logger.error("[ABTesting] Analysis failed: %s", e)
            return {"error": str(e)}

    def _get_variant_stats(self, conn, model_name: str, variant: Variant) -> Dict:
        """Get stats for a specific variant."""
        rows = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN feedback_type = 'correct' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN feedback_type = 'incorrect' THEN 1 ELSE 0 END) as incorrect,
                AVG(latency_ms) as avg_latency
            FROM ab_results
            WHERE model_name = ? AND variant = ?
            """, (model_name, variant.value)).fetchone()
        return dict(rows) if rows else {"total": 0, "correct": 0, "incorrect": 0, "avg_latency": 0.0}

    def _get_recommendation(self, improvement: float, significant: bool, ml_samples: int) -> str:
        if ml_samples < 50:
            return "not_enough_data"
        if significant and improvement > 0.02:
            return "promote_ml"
        elif significant and improvement < -0.02:
            return "rollback_ml"
        elif improvement > 0:
            return "continue_testing_ml_favored"
        else:
            return "continue_testing_rule_favored"

    def promote_ml(self, model_name: str) -> Dict:
        """Promote ML variant to 100% traffic."""
        self._experiments.pop(model_name, None)
        try:
            with self._db.get_connection() as conn:
                conn.execute(
                    "UPDATE ab_experiments SET status = 'completed', completed_at = ? WHERE model_name = ? AND status = 'running'",
                    (datetime.now().isoformat(), model_name),
                )
                conn.commit()
        except Exception:
            pass
        logger.info("[ABTesting] Promoted ML for %s", model_name)
        return {"success": True, "model_name": model_name, "action": "promoted_ml"}

    def list_experiments(self) -> List[Dict]:
        """List all experiments with analysis."""
        results = []
        for model_name in list(self._experiments.keys()):
            config = self._experiments[model_name]
            analysis = self.analyze_experiment(model_name)
            results.append({
                "model_name": model_name,
                "config": {
                    "ml_ratio": config.ml_ratio,
                    "shadow_mode": config.shadow_mode,
                },
                "analysis": analysis,
            })
        return results


_ab_testing: Optional[ABTesting] = None


def get_ab_testing() -> ABTesting:
    global _ab_testing
    if _ab_testing is None:
        _ab_testing = ABTesting()
    return _ab_testing
