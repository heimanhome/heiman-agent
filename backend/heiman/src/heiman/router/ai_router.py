import logging
import time
from datetime import datetime
from uuid import uuid4
from typing import Optional, List, Dict
from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel

from heiman.ai.anomaly_detector import AnomalyDetector
from heiman.ai.comfort_evaluator import ComfortEvaluator
from heiman.ai.behavior_recognizer import BehaviorRecognizer
from heiman.ai.decision_engine import DecisionEngine
from heiman.manager import get_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


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
        return await mgr.api_client.get_device_list(home_id)
    return []


async def get_event_data(home_id: Optional[str] = None) -> List[Dict]:
    mgr = get_manager()
    return mgr.event_repo.list(limit=50)


@router.get("/anomaly", response_model=AnomalyResponse)
async def detect_anomalies(
    home_id: Optional[str] = Query(None),
    device_data: List[Dict] = Depends(get_device_data),
):
    detector = AnomalyDetector()
    anomalies = [a.to_dict() for a in detector.detect_batch(device_data)]
    
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
    evaluator = ComfortEvaluator()
    
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
    
    return ComfortResponse(**result.to_dict())


@router.get("/activity", response_model=ActivityResponse)
async def recognize_activity(
    room_id: Optional[str] = Query(None),
    home_id: Optional[str] = Query(None),
    device_data: List[Dict] = Depends(get_device_data),
):
    recognizer = BehaviorRecognizer()
    result = recognizer.recognize_current_activity(device_data, room_id)
    
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
    engine = DecisionEngine()
    
    from heiman.ai.anomaly_detector import AnomalyDetector
    from heiman.ai.comfort_evaluator import ComfortEvaluator
    from heiman.ai.behavior_recognizer import BehaviorRecognizer
    
    anomaly_detector = AnomalyDetector()
    comfort_evaluator = ComfortEvaluator()
    behavior_recognizer = BehaviorRecognizer()
    
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
    
    return {
        "suggestion": suggestion.to_dict(),
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
    return {
        "status": "healthy",
        "services": {
            "anomaly_detector": "available",
            "comfort_evaluator": "available",
            "behavior_recognizer": "available",
            "decision_engine": "available",
            "llm_client": "available",
        },
    }


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
