import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from heiman.database.connector import get_db_connector

logger = logging.getLogger(__name__)


class ScheduledAITask:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._interval = 300
        self._last_execution = 0
        self._execution_count = 0
        self._error_count = 0
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._running and (self._task is not None and not self._task.done())

    @property
    def stats(self) -> dict:
        return {
            "running": self._running,
            "interval": self._interval,
            "last_execution": self._last_execution,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
        }

    def start(self, interval: int = 300):
        if self.is_running:
            logger.info("[ScheduledAITask] Task already running")
            return

        self._interval = interval
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("[ScheduledAITask] Scheduled AI task started, interval=%ds", interval)

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("[ScheduledAITask] Scheduled AI task stopped")

    async def _run(self):
        first_run = True
        while self._running:
            try:
                if not first_run:
                    await asyncio.sleep(self._interval)
                else:
                    first_run = False
                    # 首次执行前先等 5 秒，确保其他服务已启动完毕
                    await asyncio.sleep(5)

                if not self._running:
                    break

                # 每次执行限制 10 分钟超时，防止 AI 调用卡死导致锁永不释放
                await asyncio.wait_for(self._execute_analysis(), timeout=600)

            except asyncio.TimeoutError:
                self._error_count += 1
                logger.error("[ScheduledAITask] Analysis timed out after 600s, lock will be released")
            except asyncio.CancelledError:
                logger.info("[ScheduledAITask] Task cancelled")
                break
            except Exception as e:
                logger.error("[ScheduledAITask] Unexpected error in task loop: %s", e, exc_info=True)
                await asyncio.sleep(60)

    async def _execute_analysis(self):
        async with self._lock:
            if not self._running:
                return

            try:
                logger.info("[ScheduledAITask] Starting scheduled AI analysis")
                self._last_execution = int(time.time() * 1000)

                from heiman.ai.anomaly_detector_v2 import get_anomaly_detector_v2
                from heiman.ai.comfort_evaluator_v2 import get_comfort_evaluator_v2
                from heiman.ai.behavior_recognizer_v2 import get_behavior_recognizer_v2
                from heiman.ai.decision_engine_v2 import get_decision_engine_v2

                anomaly_detector = get_anomaly_detector_v2()
                comfort_evaluator = get_comfort_evaluator_v2()
                behavior_recognizer = get_behavior_recognizer_v2()
                decision_engine = get_decision_engine_v2()

                all_devices = await self._get_all_devices_for_analysis()
                if not all_devices:
                    logger.warning("[ScheduledAITask] No devices available for analysis")
                    return

                anomalies = [a.to_dict() for a in anomaly_detector.detect_batch(all_devices)]

                env_devices = [d for d in all_devices if d.get("temperature") is not None or d.get("humidity") is not None]
                comfort_result = {}
                if env_devices:
                    latest_env = max(env_devices, key=lambda x: x.get("lastUpdate", ""))
                    comfort_result = comfort_evaluator.evaluate_device(latest_env).to_dict()

                activity_result = behavior_recognizer.recognize_current_activity(all_devices).to_dict()

                analysis_result = await asyncio.wait_for(
                    decision_engine.analyze_home_fused(), timeout=300
                )

                await self._store_analysis_result(
                    analysis_type="scheduled",
                    result_data=analysis_result,
                    anomaly_count=len(anomalies),
                    comfort_score=comfort_result.get("score", 0) if comfort_result else 0,
                    activity_type=activity_result.get("activity", "") if activity_result else "",
                )

                self._execution_count += 1
                duration_ms = int(time.time() * 1000) - self._last_execution

                logger.info(
                    "[ScheduledAITask] Analysis completed in %.0fms - anomalies=%d, comfort=%s, activity=%s",
                    duration_ms,
                    len(anomalies),
                    comfort_result.get("level", "unknown") if comfort_result else "unknown",
                    activity_result.get("activity", "unknown") if activity_result else "unknown",
                )

                # 记录 Agent 运行
                self._record_scheduled_agent_run(duration_ms, success=True)

                # 自动记录反馈到自学习系统
                await self._record_ai_feedback_for_learning(
                    anomaly_result={"anomalies": anomalies, "total_devices": len(all_devices)},
                    comfort_result=comfort_result,
                    activity_result=activity_result,
                )

                await self._generate_rule_suggestions()

                # --- LLM 多维度家庭分析（异步，不阻塞定时循环） ---
                asyncio.create_task(self._run_home_advisor())

            except Exception as e:
                self._error_count += 1
                duration_ms = int(time.time() * 1000) - self._last_execution
                self._record_scheduled_agent_run(duration_ms, success=False, error_msg=str(e))
                logger.error("[ScheduledAITask] Analysis execution failed: %s", e, exc_info=True)

    async def _generate_rule_suggestions(self):
        try:
            from heiman.ai.smart_rule_generator import SmartRuleGenerator

            generator = SmartRuleGenerator()
            suggestions = await generator.generate_rule_suggestions(user_id="default", home_id="")

            if suggestions:
                logger.info(
                    "[ScheduledAITask] Generated %d rule suggestions",
                    len(suggestions),
                )
            else:
                logger.debug("[ScheduledAITask] No rule suggestions generated")

        except Exception as e:
            logger.error("[ScheduledAITask] Failed to generate rule suggestions: %s", e)

    def _record_scheduled_agent_run(self, duration_ms: float, success: bool, error_msg: str | None = None):
        """Record a scheduled AI analysis as an agent run in the observability DB."""
        try:
            from heiman.observability.recorder import get_recorder
            recorder = get_recorder()
            if recorder:
                recorder.record_agent_run(
                    run_id=str(uuid.uuid4()),
                    trace_id=str(uuid.uuid4()),
                    source="scheduled_ai_task",
                    query=f"Scheduled analysis #{self._execution_count + 1}",
                    duration_ms=duration_ms,
                    success=success,
                    error_msg=error_msg,
                )
        except Exception as e:
            logger.debug("[ScheduledAITask] Failed to record agent run: %s", e)

    async def _get_all_devices_for_analysis(self) -> list:
        try:
            from heiman.manager import get_manager

            mgr = get_manager()
            perception_devices = mgr.adapter.get_connected_devices()

            result = []
            for did, device in perception_devices.items():
                device_data = {
                    "id": did,
                    "name": device.name,
                    "type": device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
                    "status": "online" if device.online else "offline",
                    "battery": None,
                    "room": device.room_name or "",
                    "lastUpdate": datetime.now().isoformat(),
                }
                # 从 sensor_data_cache 获取传感器实时读数
                try:
                    dev_data = mgr.adapter.collect(did, drain=False)
                    if dev_data and dev_data.sensor_data:
                        sd = dev_data.sensor_data
                        device_data["temperature"] = sd.temperature
                        device_data["humidity"] = sd.humidity
                        device_data["co2"] = sd.co2
                        device_data["pm25"] = sd.pm25
                        device_data["switchState"] = sd.switchState
                        device_data["motionState"] = sd.motionState
                        device_data["smokeState"] = sd.smokeState
                        device_data["gasState"] = sd.gasState
                        device_data["waterState"] = sd.waterState
                        device_data["contactState"] = sd.contactState
                        device_data["alarmState"] = sd.alarmState
                        device_data["battery"] = sd.battery
                        if dev_data.timestamp:
                            device_data["lastUpdate"] = dev_data.timestamp.isoformat()
                except Exception:
                    pass
                result.append(device_data)

            return result
        except Exception as e:
            logger.error("[ScheduledAITask] Error getting devices: %s", e)
            return []

    async def _store_analysis_result(
        self,
        analysis_type: str,
        result_data: dict,
        anomaly_count: int,
        comfort_score: float,
        activity_type: str,
    ) -> None:
        try:
            import json

            db = get_db_connector()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO ai_analysis_results (
                        analysis_id, analysis_type, result_data, timestamp_ms,
                        anomaly_count, comfort_score, activity_type, home_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        analysis_type,
                        json.dumps(result_data),
                        int(datetime.now().timestamp() * 1000),
                        anomaly_count,
                        comfort_score,
                        activity_type,
                        result_data.get("home_id", ""),
                    ),
                )
                conn.commit()
            logger.debug("[ScheduledAITask] Analysis result stored")
        except Exception as e:
            logger.warning("[ScheduledAITask] Failed to store analysis result: %s", e)

    async def _run_home_advisor(self):
        """执行 LLM 多维度家庭数据分析（异步后台任务）。"""
        try:
            from heiman.service.home_advisor import run_home_advisor
            result = await run_home_advisor()
            if result and result.success:
                logger.info(
                    "[ScheduledAITask] Home advisor completed - suggestions=%d summary=%s",
                    len(result.device_linkage_suggestions)
                    + len(result.task_optimizations)
                    + len(result.anomaly_warnings)
                    + len(result.personalized_recommendations),
                    (result.summary[:60] if result.summary else ""),
                )
            elif result:
                logger.warning("[ScheduledAITask] Home advisor failed: %s", result.error_message)
        except Exception as e:
            logger.error("[ScheduledAITask] Home advisor error: %s", e, exc_info=True)

    async def force_run(self):
        logger.info("[ScheduledAITask] Forcing immediate analysis run")
        await self._execute_analysis()

    async def _record_ai_feedback_for_learning(
        self,
        anomaly_result: dict,
        comfort_result: dict,
        activity_result: dict,
    ):
        """将定时分析结果作为反馈记录到自学习系统中"""
        try:
            from heiman.ai.self_learning_system import get_self_learning_monitor, FeedbackType
            monitor = get_self_learning_monitor()
            collector = monitor.get_feedback_collector()

            # 异常检测器反馈
            anomalies = anomaly_result.get("anomalies", [])
            total_devices = anomaly_result.get("total_devices", 1)
            anomaly_ratio = len(anomalies) / max(total_devices, 1)
            anomaly_feedback_type = FeedbackType.CORRECT if anomaly_ratio <= 0.3 else FeedbackType.UNCERTAIN
            collector.record_feedback(
                model_name="anomaly_detector",
                input_features={"device_count": total_devices},
                predicted_output={"anomaly_count": len(anomalies), "anomalies": anomalies},
                actual_output={"anomaly_count": len(anomalies), "anomalies": anomalies},
                feedback_type=anomaly_feedback_type,
                confidence=0.75 if anomaly_ratio <= 0.3 else 0.5,
                metadata={"source": "scheduled_task"},
            )

            # 舒适度反馈
            if comfort_result:
                score = comfort_result.get("score", 0)
                level = comfort_result.get("level", "")
                comfort_feedback_type = FeedbackType.CORRECT if score >= 65 else FeedbackType.UNCERTAIN
                collector.record_feedback(
                    model_name="comfort_evaluator",
                    input_features={"environment": "home"},
                    predicted_output=comfort_result,
                    actual_output=comfort_result,
                    feedback_type=comfort_feedback_type,
                    confidence=0.8 if score >= 65 else 0.5,
                    metadata={"source": "scheduled_task"},
                )

            # 行为识别反馈
            if activity_result and activity_result.get("activity"):
                activity_conf = activity_result.get("confidence", 0.5)
                behavior_feedback_type = FeedbackType.CORRECT if activity_conf >= 0.6 else FeedbackType.UNCERTAIN
                collector.record_feedback(
                    model_name="behavior_recognizer",
                    input_features={"devices": total_devices},
                    predicted_output=activity_result,
                    actual_output=activity_result,
                    feedback_type=behavior_feedback_type,
                    confidence=activity_conf,
                    metadata={"source": "scheduled_task"},
                )

            # 决策引擎反馈
            analysis_data = {"model_name": "decision_engine", "source": "scheduled_task"}
            collector.record_feedback(
                model_name="decision_engine",
                input_features={"trigger": "scheduled"},
                predicted_output=analysis_data,
                actual_output=analysis_data,
                feedback_type=FeedbackType.CORRECT,
                confidence=0.7,
                metadata={"source": "scheduled_task"},
            )

            logger.info("[ScheduledAITask] Recorded AI feedback for self-learning system")

        except Exception as e:
            logger.warning("[ScheduledAITask] Failed to record AI feedback: %s", e)


_scheduled_ai_task = None


def get_scheduled_ai_task() -> ScheduledAITask:
    global _scheduled_ai_task
    if _scheduled_ai_task is None:
        _scheduled_ai_task = ScheduledAITask()
    return _scheduled_ai_task