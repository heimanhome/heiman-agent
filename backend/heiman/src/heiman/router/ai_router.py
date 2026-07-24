import logging
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Body, Query, Depends, HTTPException
from pydantic import BaseModel

from heiman.ai.anomaly_detector_v2 import get_anomaly_detector_v2
from heiman.ai.comfort_evaluator_v2 import get_comfort_evaluator_v2
from heiman.ai.behavior_recognizer_v2 import get_behavior_recognizer_v2
from heiman.ai.decision_engine import DecisionEngine
from heiman.ai.decision_engine_v2 import get_decision_engine_v2
from heiman.ai.model_registry import get_model_registry
from heiman.manager import get_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


def _record_model_feedback(model_name: str, input_features: Dict, predicted_output: Dict,
                            confidence: float = 0.0):
    """Record model output for self-learning, auto-classify feedback correctness."""
    try:
        from heiman.ai.self_learning_system import get_self_learning_monitor, FeedbackType
        monitor = get_self_learning_monitor()
        collector = monitor.get_feedback_collector()

        # 自动根据输出质量判断反馈类型
        feedback_type = FeedbackType.UNCERTAIN
        adjusted_confidence = confidence

        if model_name == "anomaly_detector":
            total_devices = input_features.get("device_count", input_features.get("total_devices", 1))
            anomaly_count = predicted_output.get("anomaly_count", len(predicted_output.get("anomalies", [])))
            anomaly_ratio = anomaly_count / max(total_devices, 1)
            if anomaly_ratio <= 0.25 and anomaly_count >= 0:
                feedback_type = FeedbackType.CORRECT
                adjusted_confidence = max(confidence, 0.8)
            elif anomaly_ratio > 0.6:
                feedback_type = FeedbackType.INCORRECT
                adjusted_confidence = max(confidence, 0.6)

        elif model_name == "comfort_evaluator":
            level = predicted_output.get("level", "")
            score = predicted_output.get("score", 0)
            if level in ("good", "excellent") and score >= 65:
                feedback_type = FeedbackType.CORRECT
                adjusted_confidence = max(confidence, 0.85)
            elif level == "poor" and score < 35:
                feedback_type = FeedbackType.INCORRECT
                adjusted_confidence = max(confidence, 0.7)

        elif model_name == "behavior_recognizer":
            activity = predicted_output.get("activity", "")
            conf = predicted_output.get("confidence", confidence)
            if activity and conf >= 0.6:
                feedback_type = FeedbackType.CORRECT
                adjusted_confidence = max(confidence, min(conf, 0.9))
            elif activity and conf < 0.3:
                feedback_type = FeedbackType.INCORRECT
                adjusted_confidence = max(confidence, 0.6)

        elif model_name == "decision_engine":
            decisions = predicted_output.get("decisions", [])
            if decisions and len(decisions) > 0:
                feedback_type = FeedbackType.CORRECT
                adjusted_confidence = max(confidence, 0.75)

        collector.record_feedback(
            model_name=model_name,
            input_features=input_features,
            predicted_output=predicted_output,
            actual_output=predicted_output,  # 自动验证时以预测输出作为实际输出
            feedback_type=feedback_type,
            confidence=adjusted_confidence,
        )
    except Exception as e:
        logger.debug("Failed to record model feedback: %s", e)


def _record_agent_run(source: str, query: str, duration_ms: float, success: bool, error_msg: str | None = None):
    """Record an agent run to the observability DB."""
    try:
        from heiman.observability.recorder import get_recorder
        recorder = get_recorder()
        if recorder:
            recorder.record_agent_run(
                run_id=str(uuid4()),
                trace_id=str(uuid4()),
                source=source,
                query=query,
                duration_ms=duration_ms,
                success=success,
                error_msg=error_msg,
            )
    except Exception as e:
        logger.debug("[AI] Failed to record agent run: %s", e)


class AnomalyResponse(BaseModel):
    anomalies: List[Dict]
    device_count: int
    anomaly_count: int


class ComfortResponse(BaseModel):
    level: str
    score: int
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    co2: Optional[int] = None
    pm25: Optional[int] = None
    hcho: Optional[float] = None
    temperature_status: Optional[str] = None
    humidity_status: Optional[str] = None
    co2_status: Optional[str] = None
    pm25_status: Optional[str] = None
    hcho_status: Optional[str] = None
    suggestions: List[str] = []


class ActivityResponse(BaseModel):
    activity: str
    activity_label: str
    confidence: float
    room_id: Optional[str] = None
    room_name: Optional[str] = None
    timestamp: str
    details: Dict = {}


class AnalysisResponse(BaseModel):
    anomalies: List[Dict]
    comfort: Dict
    activity: Dict
    decision: Dict
    suggestion: Dict
    summary: str
    device_count: int
    online_count: int


class RoutineResponse(BaseModel):
    date: str
    wake_up_time: Optional[str] = None
    sleep_time: Optional[str] = None
    leave_home_times: List[str] = []
    return_home_times: List[str] = []


async def get_device_data(home_id: Optional[str] = None) -> List[Dict]:
    mgr = get_manager()
    if mgr.api_client.is_authenticated:
        try:
            devices_dict = await mgr.api_client.get_devices(home_id)
            if isinstance(devices_dict, dict):
                return list(devices_dict.values())
            return list(devices_dict)
        except (AttributeError, Exception):
            return []
    return []


async def get_event_data(home_id: Optional[str] = None) -> List[Dict]:
    mgr = get_manager()
    return mgr.event_repo.list(limit=50)


@router.get("/anomaly", response_model=AnomalyResponse)
async def detect_anomalies(
    home_id: Optional[str] = Query(None),
    device_data: List[Dict] = Depends(get_device_data),
):
    detector = get_anomaly_detector_v2()
    results = detector.detect_batch(device_data)
    anomalies = [a.to_dict() for a in results]
    
    for device in device_data[:10]:
        has_anomaly = any(a.get("device_id") == str(device.get("deviceId", device.get("id"))) for a in anomalies)
        _record_model_feedback(
            model_name="anomaly_detector",
            input_features={"device": device.get("deviceId", device.get("id")), "device_type": device.get("type", ""), "properties": device.get("properties", {})},
            predicted_output={"has_anomaly": has_anomaly},
            confidence=0.7,
        )
    
    return AnomalyResponse(
        anomalies=anomalies,
        device_count=len(device_data),
        anomaly_count=len(anomalies),
    )


@router.get("/anomaly/behavior")
async def detect_behavior_anomaly(
    home_id: Optional[str] = Query(None),
    events: List[Dict] = Depends(get_event_data),
):
    detector = AnomalyDetector()
    result = detector.detect_behavior_anomaly(events)
    
    if result:
        return {"anomaly": result.to_dict()}
    return {"anomaly": None, "message": "未检测到行为异常"}


@router.get("/comfort", response_model=ComfortResponse)
async def evaluate_comfort(
    home_id: Optional[str] = Query(None),
    temperature: Optional[float] = Query(None),
    humidity: Optional[float] = Query(None),
    co2: Optional[int] = Query(None),
    pm25: Optional[int] = Query(None),
    hcho: Optional[float] = Query(None),
    device_data: List[Dict] = Depends(get_device_data),
):
    # Use ML evaluator with rule-based fallback
    evaluator = get_comfort_evaluator_v2()
    
    if temperature is not None or humidity is not None:
        result = evaluator.evaluate(temperature, humidity, co2, pm25, hcho)
    else:
        env_devices = [
            d for d in device_data 
            if d.get("temperature") is not None or d.get("humidity") is not None
        ]
        if env_devices:
            latest_env = max(env_devices, key=lambda x: x.get("lastUpdate", ""))
            result = evaluator.evaluate_device(latest_env)
        else:
            return ComfortResponse(level="fair", score=50, suggestions=["暂无环境数据"])
    
    # Record feedback for ML training
    _record_model_feedback(
        model_name="comfort_evaluator",
        input_features={
            "temperature": temperature,
            "humidity": humidity,
            "co2": co2,
            "pm25": pm25,
            "hcho": hcho,
        },
        predicted_output={"score": result.score, "level": result.level.value},
        confidence=0.7,
    )
    
    return ComfortResponse(**result.to_dict())


@router.get("/activity", response_model=ActivityResponse)
async def recognize_activity(
    room_id: Optional[str] = Query(None),
    home_id: Optional[str] = Query(None),
    device_data: List[Dict] = Depends(get_device_data),
):
    recognizer = get_behavior_recognizer_v2()
    result = recognizer.recognize_current_activity(device_data, room_id)
    
    _record_model_feedback(
        model_name="behavior_recognizer",
        input_features={"devices": device_data, "room_id": room_id},
        predicted_output={"activity": result.activity.value, "confidence": result.confidence},
        confidence=result.confidence,
    )
    
    return ActivityResponse(**result.to_dict())


@router.get("/activity/routine", response_model=RoutineResponse)
async def get_daily_routine(
    date: Optional[str] = Query(None),
    home_id: Optional[str] = Query(None),
    events: List[Dict] = Depends(get_event_data),
):
    recognizer = BehaviorRecognizer()
    
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的日期格式，应为 YYYY-MM-DD")
    
    routine = recognizer.get_daily_routine(events, target_date)
    
    return RoutineResponse(**routine)


@router.get("/analyze", response_model=AnalysisResponse)
async def analyze_home(
    home_id: Optional[str] = Query(None),
    device_data: List[Dict] = Depends(get_device_data),
    events: List[Dict] = Depends(get_event_data),
):
    engine = DecisionEngine()
    result = engine.analyze_home(device_data, events)
    
    return AnalysisResponse(**result)


@router.get("/suggest")
async def get_suggestion(
    home_id: Optional[str] = Query(None),
    device_data: List[Dict] = Depends(get_device_data),
    events: List[Dict] = Depends(get_event_data),
):
    engine = get_decision_engine_v2()
    
    anomaly_detector = get_anomaly_detector_v2()
    comfort_evaluator = get_comfort_evaluator_v2()
    behavior_recognizer = get_behavior_recognizer_v2()
    
    anomalies = [a.to_dict() for a in anomaly_detector.detect_batch(device_data)]
    activity = behavior_recognizer.recognize_current_activity(device_data).to_dict()
    
    env_devices = [
        d for d in device_data 
        if d.get("temperature") is not None or d.get("humidity") is not None
    ]
    comfort = {}
    if env_devices:
        latest_env = max(env_devices, key=lambda x: x.get("lastUpdate", ""))
        comfort = comfort_evaluator.evaluate_device(latest_env).to_dict()
    
    context = {
        "device_data": device_data,
        "events": events,
        "anomalies": anomalies,
        "comfort": comfort,
        "activity": activity,
    }
    
    suggestion = engine.suggest_action(context)
    
    _record_model_feedback(
        model_name="decision_engine",
        input_features=context,
        predicted_output={"action": suggestion.action if hasattr(suggestion, 'action') else suggestion.get("action", "")},
        confidence=0.7,
    )
    
    return {
        "suggestion": suggestion.to_dict() if hasattr(suggestion, 'to_dict') else suggestion,
        "context": {
            "anomalies": len(anomalies),
            "activity": activity.get("activity"),
            "comfort_level": comfort.get("level"),
        },
    }


@router.get("/summary")
async def get_summary(
    home_id: Optional[str] = Query(None),
    events: List[Dict] = Depends(get_event_data),
):
    engine = DecisionEngine()
    summary = engine.summarize_events(events)
    
    return {"summary": summary, "event_count": len(events)}


@router.get("/health")
async def ai_health():
    evaluator = get_comfort_evaluator_v2()
    return {
        "status": "healthy",
        "services": {
            "anomaly_detector": "available",
            "comfort_evaluator": f"ml_ready={evaluator.is_ml_ready}",
            "behavior_recognizer": "available",
            "decision_engine": "available",
            "llm_client": "available",
            "ml_model_registry": "available",
        },
    }


@router.get("/learning/status")
async def get_learning_status():
    from heiman.ai.self_learning_system import get_self_learning_monitor
    monitor = get_self_learning_monitor()
    return {"success": True, "data": monitor.get_status()}


@router.post("/learning/start")
async def start_learning():
    from heiman.ai.self_learning_system import get_self_learning_monitor
    monitor = get_self_learning_monitor()
    monitor.start()
    return {"success": True, "message": "Self-learning monitor started"}


@router.post("/learning/stop")
async def stop_learning():
    from heiman.ai.self_learning_system import get_self_learning_monitor
    monitor = get_self_learning_monitor()
    monitor.stop()
    return {"success": True, "message": "Self-learning monitor stopped"}


@router.get("/learning/performance")
async def get_model_performance(
    model_name: Optional[str] = Query(None),
    window_hours: int = Query(24),
):
    from heiman.ai.self_learning_system import get_self_learning_monitor
    monitor = get_self_learning_monitor()
    # 刷新待处理的反馈数据到数据库
    try:
        monitor.get_feedback_collector()._flush_pending()
    except Exception:
        pass
    analyzer = monitor.get_performance_analyzer()

    if model_name:
        result = analyzer.analyze_model_performance(model_name, window_hours)
    else:
        result = {}
        from heiman.ai.self_learning_system import ModelName
        for name in [m.value for m in ModelName]:
            result[name] = analyzer.analyze_model_performance(name, window_hours)

    return {"success": True, "data": result}


@router.get("/learning/cycles")
async def get_learning_cycles(
    model_name: Optional[str] = Query(None),
    limit: int = Query(20),
):
    from heiman.ai.self_learning_system import get_self_learning_monitor
    monitor = get_self_learning_monitor()
    engine = monitor.get_learning_engine()

    cycles = engine.get_learning_cycles(model_name, limit)
    return {"success": True, "data": cycles}


@router.get("/learning/rules")
async def get_learning_rules(
    model_name: Optional[str] = Query(None),
):
    from heiman.ai.self_learning_system import get_self_learning_monitor
    monitor = get_self_learning_monitor()
    engine = monitor.get_learning_engine()

    rules = engine.get_learning_rules(model_name)
    return {"success": True, "data": rules}


class FeedbackRequest(BaseModel):
    model_name: str
    input_features: Dict = {}
    predicted_output: Dict = {}
    actual_output: Optional[Dict] = None
    feedback_type: str = "uncertain"
    confidence: float = 0.0


@router.post("/learning/feedback")
async def submit_feedback(body: FeedbackRequest):
    from heiman.ai.self_learning_system import get_self_learning_monitor, FeedbackType
    monitor = get_self_learning_monitor()
    collector = monitor.get_feedback_collector()

    try:
        feedback_enum = FeedbackType(body.feedback_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid feedback_type")

    collector.record_feedback(
        model_name=body.model_name,
        input_features=body.input_features,
        predicted_output=body.predicted_output,
        actual_output=body.actual_output,
        feedback_type=feedback_enum,
        confidence=body.confidence,
    )

    # 立即刷新到数据库
    try:
        collector._flush_pending()
    except Exception:
        pass

    return {"success": True, "message": "Feedback recorded"}


class VerifyFeedbackRequest(BaseModel):
    model_name: str
    feedback_type: str  # "correct" or "incorrect"
    prediction_id: Optional[str] = None
    note: Optional[str] = None


@router.post("/learning/verify-feedback")
async def verify_feedback(body: VerifyFeedbackRequest):
    """用户手动验证反馈：标记模型的某次预测正确或错误"""
    from heiman.ai.self_learning_system import get_self_learning_monitor, FeedbackType
    monitor = get_self_learning_monitor()
    collector = monitor.get_feedback_collector()

    try:
        feedback_enum = FeedbackType(body.feedback_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail="feedback_type must be 'correct' or 'incorrect'")

    if feedback_enum not in (FeedbackType.CORRECT, FeedbackType.INCORRECT):
        raise HTTPException(status_code=400, detail="feedback_type must be 'correct' or 'incorrect'")

    collector.record_feedback(
        model_name=body.model_name,
        input_features={"verification_source": "manual"},
        predicted_output={"note": body.note or "Manually verified"},
        actual_output={"note": body.note or "Manually verified"},
        feedback_type=feedback_enum,
        confidence=1.0,
        prediction_id=body.prediction_id,
    )

    # 立即刷新到数据库
    try:
        collector._flush_pending()
    except Exception:
        pass

    # 返回更新后的性能数据
    monitor2 = get_self_learning_monitor()
    analyzer = monitor2.get_performance_analyzer()
    performance = analyzer.analyze_model_performance(body.model_name, window_hours=24)

    return {
        "success": True,
        "message": f"Feedback verified as {body.feedback_type}",
        "updated_performance": performance,
    }


@router.post("/learning/seed-data")
async def seed_learning_data():
    """为自学习系统生成种子反馈数据，让系统有初始学习基础"""
    from heiman.ai.self_learning_system import get_self_learning_monitor, FeedbackType
    monitor = get_self_learning_monitor()
    collector = monitor.get_feedback_collector()

    seed_count = 0
    # 为每个模型生成种子数据
    for model_name in ["anomaly_detector", "comfort_evaluator", "behavior_recognizer", "rule_generator", "decision_engine"]:
        # 3 条正确反馈
        for i in range(3):
            collector.record_feedback(
                model_name=model_name,
                input_features={"seed": True, "index": i},
                predicted_output={"result": "normal", "seed": True},
                actual_output={"result": "normal", "seed": True},
                feedback_type=FeedbackType.CORRECT,
                confidence=0.9,
                metadata={"source": "seed_data"},
            )
            seed_count += 1
        # 1 条错误反馈（让系统有改进空间）
        collector.record_feedback(
            model_name=model_name,
            input_features={"seed": True, "index": "error"},
            predicted_output={"result": "anomaly", "seed": True},
            actual_output={"result": "normal", "seed": True},
            feedback_type=FeedbackType.INCORRECT,
            confidence=0.3,
            metadata={"source": "seed_data"},
        )
        seed_count += 1

    # 立即刷新
    try:
        collector._flush_pending()
    except Exception:
        pass

    # 触发所有模型的学习
    engine = monitor.get_learning_engine()
    results = {}
    for model_name in ["anomaly_detector", "comfort_evaluator", "behavior_recognizer", "rule_generator", "decision_engine"]:
        try:
            r = await engine.start_learning_cycle(model_name)
            results[model_name] = r.get("status", "unknown")
        except Exception as e:
            results[model_name] = f"error: {e}"

    return {
        "success": True,
        "message": f"Generated {seed_count} seed feedback records",
        "learning_results": results,
    }


@router.post("/learning/trigger")
async def trigger_learning_cycle(
    model_name: str = Query(...),
):
    from heiman.ai.self_learning_system import get_self_learning_monitor
    monitor = get_self_learning_monitor()
    # 刷新待处理的反馈数据
    try:
        monitor.get_feedback_collector()._flush_pending()
    except Exception:
        pass
    engine = monitor.get_learning_engine()

    result = await engine.start_learning_cycle(model_name)
    return {"success": True, "data": result}


@router.get("/learning/problematic-patterns")
async def get_problematic_patterns(
    model_name: str = Query(...),
):
    from heiman.ai.self_learning_system import get_self_learning_monitor
    monitor = get_self_learning_monitor()
    analyzer = monitor.get_performance_analyzer()

    patterns = analyzer.identify_problematic_patterns(model_name)
    return {"success": True, "data": patterns}


@router.get("/analyze/fused")
async def analyze_home_fused(
    home_id: str = Query("default", description="家庭ID"),
):
    engine = DecisionEngine()
    result = await engine.analyze_home_fused(home_id)
    return result


@router.get("/perception/identity")
async def get_identity_info(
    home_id: str = Query("default", description="家庭ID"),
):
    from heiman.ai.orchestrator import AIOrchestrator

    orchestrator = AIOrchestrator()
    scene_context = await orchestrator.fuse_perception_data(home_id)

    user_identity = None
    if scene_context.user_identity:
        user_identity = {
            "person_id": scene_context.user_identity.person_id,
            "name": scene_context.user_identity.name,
            "role": scene_context.user_identity.role,
            "confidence": scene_context.user_identity.confidence,
        }

    return {
        "user_identity": user_identity,
        "activities": scene_context.activities,
        "environment": scene_context.environment,
    }


@router.get("/intent/respond")
async def intent_response(
    query: str = Query(..., description="用户查询"),
    home_id: str = Query("default", description="家庭ID"),
):
    from heiman.ai.orchestrator import AIOrchestrator

    start_ms = time.time() * 1000
    success = True
    error_msg = None
    try:
        orchestrator = AIOrchestrator()
        scene_context = await orchestrator.fuse_perception_data(home_id)
        result = await orchestrator.generate_intent_response(scene_context, query)
        return {"response": result["response"]}
    except Exception as e:
        success = False
        error_msg = str(e)
        logger.error("[AI] intent_response failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        duration_ms = time.time() * 1000 - start_ms
        _record_agent_run("ai_intent", query[:500], duration_ms, success, error_msg)


@router.get("/habits")
async def get_user_habits(
    user_id: str = Query("default", description="用户ID"),
):
    from heiman.ai.orchestrator import AIOrchestrator

    orchestrator = AIOrchestrator()
    return await orchestrator.get_habits(user_id)


@router.get("/suggestions")
async def get_action_suggestions(
    user_id: str = Query("default", description="用户ID"),
    home_id: str = Query("default", description="家庭ID"),
):
    from heiman.ai.orchestrator import AIOrchestrator

    orchestrator = AIOrchestrator()
    scene_context = await orchestrator.fuse_perception_data(home_id)
    context = {
        "user_identity": scene_context.user_identity.name if scene_context.user_identity else None,
        "activities": scene_context.activities,
        "environment": scene_context.environment,
        "security_state": scene_context.security_state,
    }
    return await orchestrator.get_action_suggestions(user_id, context)


@router.post("/preference")
async def update_user_preference(
    user_id: str = Query("default", description="用户ID"),
    key: str = Query(..., description="偏好键"),
    value: str = Query(..., description="偏好值"),
):
    from heiman.ai.orchestrator import AIOrchestrator

    orchestrator = AIOrchestrator()
    await orchestrator.update_preference(user_id, key, value)

    return {"status": "success", "message": f"Preference {key} updated"}


@router.post("/edge/infer")
async def edge_inference(
    model_id: str = Query("llm_default", description="模型ID"),
    prompt: str = Query(..., description="推理提示"),
    max_tokens: int = Query(512, description="最大token数"),
    temperature: float = Query(0.7, description="温度"),
):
    from heiman.ai.orchestrator import AIOrchestrator

    orchestrator = AIOrchestrator()
    params = {
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    return await orchestrator.edge_infer(model_id, prompt, params)


@router.get("/edge/models")
async def list_edge_models():
    from heiman.perception.edge_inference import EdgeInferenceEngine

    engine = EdgeInferenceEngine()
    return await engine.list_models()


@router.get("/perception/events")
async def get_perception_events(
    home_id: str = Query("default", description="家庭ID"),
    limit: int = Query(20, description="返回数量"),
):
    from heiman.ai.orchestrator import AIOrchestrator

    orchestrator = AIOrchestrator()
    perception_engine = orchestrator.get_perception_engine()

    if perception_engine:
        events = await perception_engine.get_recent_events(limit=limit)
        return {
            "events": [
                {
                    "type": e.type.value,
                    "location": e.location,
                    "timestamp": e.timestamp,
                    "confidence": e.confidence,
                    "payload": e.payload,
                }
                for e in events
            ],
            "count": len(events),
        }
    return {"events": [], "count": 0}


@router.get("/analysis/results")
async def get_ai_analysis_results(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    analysis_type: Optional[str] = Query(None, description="分析类型"),
    home_id: Optional[str] = Query(None, description="家庭ID"),
):
    try:
        from heiman.database.connector import get_db_connector

        db = get_db_connector()
        base_query = """
            SELECT * FROM ai_analysis_results
            WHERE 1=1
        """
        params = []

        if analysis_type:
            base_query += " AND analysis_type = ?"
            params.append(analysis_type)
        if home_id:
            base_query += " AND home_id = ?"
            params.append(home_id)

        # 先查总数
        count_query = base_query.replace("SELECT *", "SELECT COUNT(*) as cnt")
        offset = (page - 1) * page_size
        data_query = base_query + " ORDER BY timestamp_ms DESC LIMIT ? OFFSET ?"

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 总数
            cursor.execute(count_query, tuple(params))
            total_row = cursor.fetchone()
            total = total_row["cnt"] if total_row else 0

            # 分页数据
            cursor.execute(data_query, tuple(params) + (page_size, offset))
            rows = cursor.fetchall()

        total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

        results = []
        for row in rows:
            result_data = row["result_data"]
            try:
                import json

                result_data = json.loads(result_data)
            except Exception:
                pass

            results.append({
                "analysis_id": row["analysis_id"],
                "analysis_type": row["analysis_type"],
                "result_data": result_data,
                "timestamp_ms": row["timestamp_ms"],
                "anomaly_count": row["anomaly_count"],
                "comfort_score": row["comfort_score"],
                "activity_type": row["activity_type"],
                "home_id": row["home_id"],
                "created_at": row["created_at"],
            })

        return {
            "success": True,
            "data": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "items": results,
            },
        }
    except Exception as e:
        logger.error("[AI] Failed to get analysis results: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token/usage")
async def get_token_usage(
    since_ms: Optional[int] = Query(None, description="起始时间戳(ms)"),
    until_ms: Optional[int] = Query(None, description="结束时间戳(ms)"),
    model: Optional[str] = Query(None, description="模型名称"),
    usage_type: Optional[str] = Query(None, description="使用类型"),
):
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo

        repo = get_token_usage_repo()
        events, truncated = repo.list_events(since_ms, until_ms)

        if model:
            events = [e for e in events if e["model"] == model]
        if usage_type:
            events = [e for e in events if e["usage_type"] == usage_type]

        total_prompt = sum(e["prompt_tokens"] for e in events)
        total_completion = sum(e["completion_tokens"] for e in events)
        total_tokens = sum(e["total_tokens"] for e in events)

        return {
            "success": True,
            "data": {
                "usage": events,
                "summary": {
                    "prompt_tokens": total_prompt,
                    "completion_tokens": total_completion,
                    "total_tokens": total_tokens,
                    "request_count": len(events),
                },
                "truncated": truncated,
            },
        }
    except Exception as e:
        logger.error("[AI] Failed to get token usage: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token/quota")
async def get_token_quota(
    model: Optional[str] = Query("", description="模型名称"),
    usage_type: Optional[str] = Query("api", description="使用类型"),
):
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo

        repo = get_token_usage_repo()
        quota_status = repo.check_quota(model or "", usage_type or "api")

        # Transform to match frontend expected format
        daily_usage = quota_status.get("daily_usage", 0)
        daily_limit = quota_status.get("daily_limit", 100000)
        remaining = max(0, daily_limit - daily_usage)
        usage_percent = round((daily_usage / daily_limit * 100), 1) if daily_limit > 0 else 0
        warning_threshold = quota_status.get("warning_threshold", 0.8)

        if daily_usage >= daily_limit:
            status = "exceeded"
            message = "Token配额已用完"
        elif quota_status.get("at_warning", False):
            status = "warning"
            message = f"Token使用量已达{usage_percent}%，接近上限"
        else:
            status = "ok"
            message = "Token配额正常"

        return {"success": True, "data": {
            "model": quota_status.get("model", model or ""),
            "usage_type": quota_status.get("usage_type", usage_type or "api"),
            "daily_limit": daily_limit,
            "warning_threshold": warning_threshold,
            "current_usage": daily_usage,
            "remaining": remaining,
            "usage_percent": usage_percent,
            "status": status,
            "message": message,
        }}
    except Exception as e:
        logger.error("[AI] Failed to get token quota: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/token/quota")
async def set_token_quota(
    model: str = Query("", description="模型名称"),
    usage_type: str = Query("api", description="使用类型"),
    daily_limit: int = Query(100000, description="每日限额"),
    warning_threshold: float = Query(0.8, description="警告阈值"),
    body: dict | None = Body(None, embed=True),  # 兼容前端 axios POST JSON body
):
    try:
        # 兼容前端 axios POST { params: {...} } 格式
        if body and "params" in body:
            params = body["params"]
            model = params.get("model", model)
            usage_type = params.get("usage_type", usage_type)
            daily_limit = params.get("daily_limit", daily_limit)
            warning_threshold = params.get("warning_threshold", warning_threshold)
        elif body:
            model = body.get("model", model)
            usage_type = body.get("usage_type", usage_type)
            daily_limit = body.get("daily_limit", daily_limit)
            warning_threshold = body.get("warning_threshold", warning_threshold)

        from heiman.database.token_usage_repo import get_token_usage_repo

        repo = get_token_usage_repo()
        repo.set_quota(model, usage_type, daily_limit, warning_threshold)

        return {
            "status": "success",
            "message": f"Quota updated for model={model}, type={usage_type}",
            "quota": repo.get_quota(model, usage_type),
        }
    except Exception as e:
        logger.error("[AI] Failed to set token quota: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token/daily")
async def get_token_daily_usage(
    since_date: Optional[str] = Query(None, description="起始日期"),
    until_date: Optional[str] = Query(None, description="结束日期"),
):
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo

        repo = get_token_usage_repo()
        daily_data = repo.aggregate_daily(since_date, until_date)

        total_tokens = sum(d["total_tokens"] for d in daily_data)

        return {
            "success": True,
            "data": {
                "daily_data": daily_data,
                "total_tokens": total_tokens,
            },
        }
    except Exception as e:
        logger.error("[AI] Failed to get daily token usage: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assistant")
async def smart_home_assistant(
    user_id: str = Query("default", description="用户ID"),
    page: int = Query(1, ge=1, description="操作列表页码"),
    page_size: int = Query(10, ge=1, le=50, description="操作每页数量"),
):
    try:
        engine = DecisionEngine()
        await engine.initialize()
        result = await engine.smart_home_assistant(user_id)

        # 对 proactive_actions 分页
        all_actions = result.get("proactive_actions", [])
        total_actions = len(all_actions)
        total_pages = max(1, (total_actions + page_size - 1) // page_size) if total_actions > 0 else 1
        offset = (page - 1) * page_size
        paged_actions = all_actions[offset : offset + page_size]

        result["proactive_actions"] = paged_actions
        result["proactive_actions_total"] = total_actions
        result["proactive_actions_page"] = page
        result["proactive_actions_page_size"] = page_size
        result["proactive_actions_total_pages"] = total_pages

        return {"success": True, "data": result}
    except Exception as e:
        logger.error("[AI] Smart home assistant failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/emotion")
async def analyze_emotion(
    user_id: str = Query("default", description="用户ID"),
    activity: Optional[str] = Query(None, description="当前活动"),
    hour: Optional[int] = Query(None, description="当前时间"),
):
    try:
        from heiman.perception.emotion_engine import EmotionEngine

        engine = EmotionEngine()
        emotion_context = {
            "hour": hour if hour is not None else datetime.now().hour,
            "day_of_week": datetime.now().weekday(),
            "activity": activity or "",
            "device_states": {},
        }
        result = await engine.analyze_emotion(user_id, emotion_context)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error("[AI] Emotion analysis failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/emotion/profile")
async def get_emotional_profile(
    user_id: str = Query("default", description="用户ID"),
):
    try:
        from heiman.perception.emotion_engine import EmotionEngine

        engine = EmotionEngine()
        profile = await engine.get_user_emotional_profile(user_id)
        return {"success": True, "data": profile.to_dict() if profile else None}
    except Exception as e:
        logger.error("[AI] Get emotional profile failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/energy/stats")
async def get_energy_stats(
    days: int = Query(7, description="查询天数"),
):
    try:
        from heiman.energy.energy_manager import EnergyManager

        manager = EnergyManager()
        await manager.initialize()
        daily_stats = await manager.get_daily_stats(days=days)
        return {"success": True, "data": {"daily_stats": daily_stats}}
    except Exception as e:
        logger.error("[Energy] Get stats failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/energy/report")
async def get_energy_report(
    days: int = Query(30, description="报告天数"),
):
    try:
        from heiman.energy.energy_manager import EnergyManager

        manager = EnergyManager()
        await manager.initialize()
        report = await manager.get_energy_report(days=days)
        return {"success": True, "data": report}
    except Exception as e:
        logger.error("[Energy] Get report failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/energy/optimization")
async def get_energy_optimization():
    try:
        from heiman.energy.energy_manager import EnergyManager, EnergyMode

        manager = EnergyManager()
        await manager.initialize()
        optimization = await manager.optimize_consumption()

        # Transform to match frontend expected format
        recommendations = []
        for rec in optimization.get("recommendations", []):
            recommendations.append({
                "action": rec.get("action", ""),
                "description": rec.get("description", ""),
                "priority": rec.get("priority", "low"),
                "estimated_savings_watts": rec.get("estimated_savings_watts", 0),
            })

        return {"success": True, "data": {
            "current_mode": manager._energy_mode.value if hasattr(manager, '_energy_mode') else "auto",
            "recommendations": recommendations,
            "current_price_per_kwh": optimization.get("current_price_per_kwh", 0.8),
        }}
    except Exception as e:
        logger.error("[Energy] Optimization failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices")
async def get_all_devices():
    try:
        from heiman.device.protocol_adapter import get_adapter_registry

        registry = get_adapter_registry()
        adapters = registry.list_adapters()
        all_devices = []
        for protocol in adapters:
            adapter = registry.get_adapter(protocol)
            if adapter:
                devices = adapter.list_devices()
                for device in devices:
                    device_dict = device.to_dict()
                    device_dict["protocol"] = protocol.value
                    all_devices.append(device_dict)

        return {"success": True, "data": {
            "devices": all_devices,
            "count": len(all_devices),
            "protocols": [p.value for p in adapters],
        }}
    except Exception as e:
        logger.error("[Device] Get all devices failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/action")
async def execute_device_action(
    device_id: str = Query(..., description="设备ID"),
    action: str = Query(..., description="动作名称"),
    params: Optional[str] = Query("{}", description="动作参数JSON"),
):
    try:
        from heiman.device.protocol_adapter import get_adapter_registry
        import json

        registry = get_adapter_registry()
        adapters = registry.list_adapters()

        params_dict = json.loads(params)

        for protocol in adapters:
            adapter = registry.get_adapter(protocol)
            if adapter:
                result = adapter.execute_action(device_id, action, params_dict)
                if result.get("success"):
                    return {"success": True, "data": result}

        return {"success": False, "data": None, "message": f"Device {device_id} not found or action {action} failed"}
    except Exception as e:
        logger.error("[Device] Execute action failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/privacy/status")
async def get_privacy_status():
    try:
        from heiman.privacy.privacy_engine import PrivacyEngine

        engine = PrivacyEngine()
        await engine.initialize()
        raw_status = engine.get_status()

        # Transform to match frontend expected format
        return {"success": True, "data": {
            "anonymization_enabled": raw_status.get("anonymization_enabled", False),
            "data_retention_days": 30,
            "federated_learning_enabled": raw_status.get("cloud_sync_enabled", False),
            "local_only_processing": not raw_status.get("cloud_sync_enabled", False),
        }}
    except Exception as e:
        logger.error("[Privacy] Get status failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/privacy/anonymize")
async def anonymize_data(
    data: str = Query(..., description="待匿名化的数据JSON"),
):
    try:
        from heiman.privacy.privacy_engine import PrivacyEngine
        import json

        engine = PrivacyEngine()
        original_data = json.loads(data)
        anonymized = engine.anonymize(original_data)
        return {"success": True, "data": {"original": original_data, "anonymized": anonymized}}
    except Exception as e:
        logger.error("[Privacy] Anonymize failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/matter/devices")
async def discover_matter_devices():
    try:
        from heiman.device.matter_adapter import MatterAdapter

        adapter = MatterAdapter()
        devices = adapter.discover_devices()
        return {
            "devices": [d.to_dict() for d in devices],
            "count": len(devices),
        }
    except Exception as e:
        logger.error("[Matter] Discover devices failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/matter/commission")
async def commission_matter_device(
    device_id: str = Query(..., description="设备ID"),
    setup_code: str = Query(..., description="配网码"),
):
    try:
        from heiman.device.matter_adapter import MatterAdapter

        adapter = MatterAdapter()
        result = adapter.commission_device(device_id, setup_code)
        return result
    except Exception as e:
        logger.error("[Matter] Commission failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ML Model Management endpoints
# ============================================================

class TrainModelRequest(BaseModel):
    model_name: str = "comfort_evaluator"
    use_bootstrap: bool = True


class ModelFeedbackSubmit(BaseModel):
    model_name: str
    input_features: Dict = {}
    predicted_output: Dict = {}
    actual_output: Optional[Dict] = None
    feedback_type: str = "correct"  # correct/incorrect/uncertain/manual_override
    confidence: float = 0.0


@router.get("/ml/models")
async def list_ml_models():
    """List all ML models and their versions."""
    registry = get_model_registry()
    raw = registry.get_all_models_status()

    # V2 模型名 → 类型映射（前端需要 type 字段）
    TYPE_MAP = {
        "comfort_evaluator": "RandomForestRegressor",
        "anomaly_detector_if": "IsolationForest",
        "anomaly_detector_clf": "RandomForestClassifier",
        "behavior_recognizer": "RandomForestClassifier",
        "decision_engine": "RandomForestClassifier",
    }

    # 标记哪些模型是真正的 sklearn 模型（可训练、有特征重要性）
    ML_TRAINABLE = {
        "comfort_evaluator", "anomaly_detector", "anomaly_detector_if",
        "anomaly_detector_clf", "behavior_recognizer", "decision_engine",
    }

    models = []
    for m in raw:
        name = m.get("model_name", "")
        training_source = m.get("latest_training_source", "unknown")
        models.append({
            "name": name,
            "type": TYPE_MAP.get(name, "Unknown"),
            "status": "ready" if m.get("has_model_file") else (
                "error" if m.get("error") else "not_trained"
            ),
            "accuracy": m.get("latest_accuracy"),
            "feature_count": m.get("feature_count", m.get("total_versions", 0)),
            "samples": m.get("latest_samples", 0),
            "last_trained": m.get("latest_created_at"),
            "error": m.get("error"),
            "trainable": name in ML_TRAINABLE,
            "training_source": training_source,
        })

    return {"success": True, "data": {"models": models, "total": len(models)}}


@router.get("/ml/models/{model_name}")
async def get_model_info(model_name: str):
    """Get detailed info for a specific ML model."""
    registry = get_model_registry()
    metadata = registry.get_metadata(model_name)
    versions = registry.get_all_versions(model_name)

    if not metadata and not versions:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

    return {
        "success": True,
        "data": {
            "model_name": model_name,
            "active_version": metadata.version if metadata else None,
            "accuracy": metadata.accuracy if metadata else None,
            "samples_trained": metadata.samples_trained if metadata else 0,
            "all_versions": versions,
            "has_model": registry.model_exists(model_name),
        },
    }


@router.post("/ml/models/{model_name}/train")
async def train_model(model_name: str, body: TrainModelRequest = TrainModelRequest()):
    """Train a specific ML model."""
    trainers = {
        "comfort_evaluator": lambda: get_comfort_evaluator_v2().train(use_bootstrap=body.use_bootstrap),
        "anomaly_detector": lambda: get_anomaly_detector_v2().train(use_bootstrap=body.use_bootstrap),
        "anomaly_detector_if": lambda: get_anomaly_detector_v2().train(use_bootstrap=body.use_bootstrap),
        "anomaly_detector_clf": lambda: get_anomaly_detector_v2().train(use_bootstrap=body.use_bootstrap),
        "behavior_recognizer": lambda: get_behavior_recognizer_v2().train(use_bootstrap=body.use_bootstrap),
        "decision_engine": lambda: get_decision_engine_v2().train(use_bootstrap=body.use_bootstrap),
    }

    train_fn = trainers.get(model_name)
    if not train_fn:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' not supported. Choose: {', '.join(trainers.keys())}",
        )

    result = train_fn()
    return {"success": result.get("success", False), "data": result}


@router.post("/ml/models/train-all")
async def train_all_models(use_bootstrap: bool = True):
    """Train all ML models with bootstrap data."""
    results = {}
    trainers = {
        "comfort_evaluator": lambda: get_comfort_evaluator_v2().train(use_bootstrap=use_bootstrap),
        "anomaly_detector": lambda: get_anomaly_detector_v2().train(use_bootstrap=use_bootstrap),
        "behavior_recognizer": lambda: get_behavior_recognizer_v2().train(use_bootstrap=use_bootstrap),
        "decision_engine": lambda: get_decision_engine_v2().train(use_bootstrap=use_bootstrap),
    }

    for name, train_fn in trainers.items():
        try:
            results[name] = train_fn()
        except Exception as e:
            results[name] = {"success": False, "error": str(e)}

    # 返回前端期望的 results 列表格式
    result_list = []
    for name, r in results.items():
        result_list.append({
            "model_name": name,
            "accuracy": r.get("accuracy", 0),
            "samples": r.get("samples_trained", r.get("samples", 0)),
            "train_time": r.get("train_time", r.get("time", 0)),
            "message": str(r.get("error", "")) if not r.get("success", True) else "OK",
        })

    return {"success": True, "data": {"results": result_list}}


@router.get("/ml/models/{model_name}/comfort/info")
async def get_comfort_model_info():
    """Get ComfortEvaluatorV2 model info (ML vs rule-based)."""
    evaluator = get_comfort_evaluator_v2()
    return {"success": True, "data": evaluator.get_model_info()}


@router.post("/ml/models/{model_name}/feedback")
async def submit_ml_model_feedback(body: ModelFeedbackSubmit):
    """Submit feedback to improve ML model accuracy."""
    from heiman.ai.self_learning_system import get_self_learning_monitor, FeedbackType

    monitor = get_self_learning_monitor()
    collector = monitor.get_feedback_collector()

    try:
        feedback_enum = FeedbackType(body.feedback_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid feedback_type")

    collector.record_feedback(
        model_name=body.model_name,
        input_features=body.input_features,
        predicted_output=body.predicted_output,
        actual_output=body.actual_output,
        feedback_type=feedback_enum,
        confidence=body.confidence,
    )

    return {"success": True, "message": f"Feedback recorded for {body.model_name}"}


@router.post("/ml/models/check-retrain")
async def check_and_retrain():
    """Check if any ML model needs retraining (based on feedback accumulation)."""
    results = {}

    # Check comfort evaluator
    evaluator = get_comfort_evaluator_v2()
    if evaluator._feedback_since_train >= 50:
        result = evaluator.train(use_bootstrap=False)
        results["comfort_evaluator"] = result
    else:
        results["comfort_evaluator"] = {
            "retrained": False,
            "reason": f"Only {evaluator._feedback_since_train} new feedbacks, need 50",
        }

    return {"success": True, "data": results}


@router.get("/ml/health")
async def ml_health():
    """Health check for ML subsystem."""
    registry = get_model_registry()
    comfort_eval = get_comfort_evaluator_v2()
    anomaly_det = get_anomaly_detector_v2()
    behavior_rec = get_behavior_recognizer_v2()
    decision_eng = get_decision_engine_v2()

    return {
        "status": "healthy",
        "services": {
            "model_registry": "available",
            "comfort_evaluator_ml": comfort_eval.is_ml_ready,
            "anomaly_detector_ml": anomaly_det.is_ml_ready,
            "behavior_recognizer_ml": behavior_rec.is_ml_ready,
            "decision_engine_ml": decision_eng.is_ml_ready,
            "scikit_learn_available": True,
        },
        "models": {
            m["model_name"]: {
                "has_model": m["exists"],
                "accuracy": m["latest_accuracy"],
                "samples": m["latest_samples"],
            }
            for m in registry.get_all_models_status()
        },
    }


@router.get("/scheduler/status")
async def scheduler_status():
    """查看定时分析任务的运行状态"""
    from heiman.service.scheduled_ai_task import get_scheduled_ai_task
    task = get_scheduled_ai_task()
    stats = task.stats
    return {
        "success": True,
        "data": {
            "is_running": task.is_running,
            **stats,
            "last_execution_iso": (
                datetime.fromtimestamp(stats["last_execution"] / 1000).isoformat()
                if stats["last_execution"] else None
            ),
            "next_execution_approx": (
                "首次即将执行（启动后 5 秒）" if stats["execution_count"] == 0
                else f"约 {stats['interval']} 秒后"
            ),
        },
    }


@router.post("/scheduler/force-run")
async def scheduler_force_run():
    """手动立即触发一次定时分析"""
    from heiman.service.scheduled_ai_task import get_scheduled_ai_task
    task = get_scheduled_ai_task()
    await task.force_run()
    return {
        "success": True,
        "message": "分析已触发，请查看日志确认执行结果",
        "stats": task.stats,
    }


# ============================================================
# Phase 3: Online Learning & A/B Testing endpoints
# ============================================================

class ABExperimentStart(BaseModel):
    model_name: str
    ml_ratio: float = 0.7
    min_sample_size: int = 100
    shadow_mode: bool = False


@router.post("/ml/ab/start")
async def start_ab_experiment(body: ABExperimentStart):
    """Start an A/B experiment for a model."""
    from heiman.ai.ab_testing import get_ab_testing
    tester = get_ab_testing()
    return {"success": True, "data": tester.start_experiment(
        body.model_name, body.ml_ratio, body.min_sample_size, body.shadow_mode,
    )}


@router.get("/ml/ab/status")
async def get_ab_status():
    """Get A/B experiment status for all models."""
    from heiman.ai.ab_testing import get_ab_testing
    tester = get_ab_testing()
    raw = tester.list_experiments()
    experiments = []
    for exp in raw:
        exp_name = exp.get("model_name", "unknown")
        config = exp.get("config", {})
        analysis = exp.get("analysis", {})
        ml_var = analysis.get("ml_variant", {})
        rule_var = analysis.get("rule_variant", {})
        experiments.append({
            "name": exp_name,
            "model_name": exp_name,
            "ml_ratio": config.get("ml_ratio", 0.5),
            "shadow_mode": config.get("shadow_mode", False),
            "min_sample_size": config.get("min_sample_size", 100),
            "status": "running",
            "start_time": "",
            "variant_a_samples": rule_var.get("total", 0),
            "variant_b_samples": ml_var.get("total", 0),
        })
    return {"success": True, "data": {"experiments": experiments}}


@router.post("/ml/ab/analyze")
async def analyze_ab_experiment(body: Dict[str, Any] = Body(...)):
    """Analyze A/B experiment results."""
    from heiman.ai.ab_testing import get_ab_testing
    experiment_name = body.get("experiment_name", "")
    if not experiment_name:
        raise HTTPException(status_code=400, detail="experiment_name is required")
    tester = get_ab_testing()
    raw = tester.analyze_experiment(experiment_name)
    if "error" in raw:
        return {"success": False, "data": raw}
    ml_var = raw.get("ml_variant", {})
    rule_var = raw.get("rule_variant", {})
    return {"success": True, "data": {
        "experiment_name": raw.get("model_name", experiment_name),
        "variant_a_metrics": {
            "total": rule_var.get("total", 0),
            "accuracy": rule_var.get("accuracy", 0),
        },
        "variant_b_metrics": {
            "total": ml_var.get("total", 0),
            "accuracy": ml_var.get("accuracy", 0),
        },
        "winner": "b" if raw.get("recommendation") == "promote_ml" else (
            "a" if raw.get("recommendation") == "rollback_ml" else "tie"
        ),
        "confidence": raw.get("confidence", 0),
        "improvement": {"accuracy": raw.get("improvement", 0)},
    }}


@router.post("/ml/ab/promote")
async def promote_ml_variant(body: Dict[str, Any] = Body(...)):
    """Promote ML variant to 100% traffic."""
    from heiman.ai.ab_testing import get_ab_testing
    experiment_name = body.get("experiment_name", "")
    if not experiment_name:
        raise HTTPException(status_code=400, detail="experiment_name is required")
    tester = get_ab_testing()
    result = tester.promote_ml(experiment_name)
    return {"success": result.get("success", True), "data": result}


@router.get("/ml/online/status")
async def get_online_learning_status():
    """Get online learning retrain status for all models."""
    from heiman.ai.online_learner import get_online_learner
    from heiman.ai.model_registry import get_model_registry
    learner = get_online_learner()
    raw = learner.get_retrain_status()
    registry = get_model_registry()

    models = []
    for model_name, status_data in raw.items():
        meta = registry.get_metadata(model_name)
        models.append({
            "name": model_name,
            "feedback_since_last_train": status_data.get("new_since_train", 0),
            "retrain_threshold": status_data.get("threshold", 50),
            "last_retrain": meta.created_at if meta else None,
            "accuracy_trend": status_data.get("accuracy_trend", []),
        })
    return {"success": True, "data": {"models": models}}


@router.post("/ml/online/retrain")
async def trigger_online_retrain(model_name: str = Query("", description="模型名称，为空则全部重训练")):
    """Check and retrain models that need it."""
    from heiman.ai.online_learner import get_online_learner
    learner = get_online_learner()
    if model_name:
        results = await learner.retrain_model(model_name)
    else:
        results = await learner.auto_retrain_if_needed()
    return {"success": True, "data": results}


# ============================================================
# Phase 4: Model Explainability endpoints
# ============================================================

class ModelExplainRequest(BaseModel):
    model_name: str
    features: Dict[str, float] = {}


@router.get("/ml/explain/{model_name}")
async def explain_model(model_name: str):
    """Get comprehensive feature importance and explanation for a model."""
    from heiman.ai.model_explainer import get_explainer
    explainer = get_explainer()
    result = explainer.explain_model(model_name)
    return {"success": True, "data": result}


@router.post("/ml/explain/prediction")
async def explain_prediction(body: ModelExplainRequest):
    """Explain a single model prediction with feature contributions."""
    from heiman.ai.model_explainer import get_explainer
    from heiman.ai.model_registry import get_model_registry

    registry = get_model_registry()
    model = registry.load_model(body.model_name)
    meta = registry.get_metadata(body.model_name)

    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{body.model_name}' not found")

    feature_names = meta.feature_names if meta else []
    if not feature_names:
        raise HTTPException(status_code=400, detail="Model has no feature names")

    X = np.array([[body.features.get(name, -1.0) for name in feature_names]], dtype=np.float32)
    explainer = get_explainer()
    result = explainer.explain_prediction(model, feature_names, X)
    return {"success": True, "data": result}


@router.get("/ml/feature-importance/{model_name}")
async def get_feature_importance(model_name: str):
    """Get feature importance rankings for a model."""
    from heiman.ai.model_explainer import get_explainer
    from heiman.ai.model_registry import get_model_registry
    from heiman.ai.feedback_dataset import FeedbackDataset

    registry = get_model_registry()
    model = registry.load_model(model_name)
    meta = registry.get_metadata(model_name)

    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

    feature_names = meta.feature_names if meta else []
    explainer = get_explainer()

    report = explainer.get_feature_importance_report(model, feature_names)
    return {"success": True, "data": report}


# ---------------------------------------------------------------------------
# 告警分析 API (alert_analyses)
# ---------------------------------------------------------------------------

@router.get("/alerts")
async def list_alert_analyses(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    alert_type: Optional[str] = Query(None, description="告警类型筛选"),
    urgency_level: Optional[str] = Query(None, description="紧急程度筛选"),
):
    """列出告警 LLM 分析结果（分页）。"""
    try:
        from heiman.ai.alert_analyzer import get_alert_analyzer, init_alert_analyzer
        from heiman.database.connector import get_db_connector

        try:
            analyzer = get_alert_analyzer()
        except RuntimeError:
            db = get_db_connector()
            analyzer = init_alert_analyzer(db=db)

        result = analyzer.list_analyses(
            page=page,
            page_size=page_size,
            alert_type=alert_type,
            urgency_level=urgency_level,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error("[Alert] List alert analyses failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{analysis_id}")
async def get_alert_analysis(analysis_id: str):
    """按 analysis_id 查询单条告警分析结果。"""
    try:
        from heiman.ai.alert_analyzer import get_alert_analyzer, init_alert_analyzer
        from heiman.database.connector import get_db_connector

        try:
            analyzer = get_alert_analyzer()
        except RuntimeError:
            db = get_db_connector()
            analyzer = init_alert_analyzer(db=db)

        result = analyzer.get_by_id(analysis_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Alert analysis '{analysis_id}' not found")
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Alert] Get alert analysis failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/event/{event_id}")
async def get_alert_analysis_by_event(event_id: str):
    """按 event_id 查询最新的告警分析结果。"""
    try:
        from heiman.ai.alert_analyzer import get_alert_analyzer, init_alert_analyzer
        from heiman.database.connector import get_db_connector

        try:
            analyzer = get_alert_analyzer()
        except RuntimeError:
            db = get_db_connector()
            analyzer = init_alert_analyzer(db=db)

        result = analyzer.get_by_event(event_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"No alert analysis found for event '{event_id}'")
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Alert] Get alert analysis by event failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
