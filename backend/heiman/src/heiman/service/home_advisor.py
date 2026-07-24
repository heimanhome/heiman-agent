"""
家庭智能顾问 - 定时场景下调用 LLM 对多维度家庭数据进行综合分析，生成智能建议。

触发场景：定时任务触发（如每小时），整合以下数据源：
- 发生的特定事件（告警、异常、状态变更）
- 设备当前属性与状态
- 家庭成员信息与偏好
- 日常任务执行情况
- 家庭档案记录
- 历史交互上下文

输出：结构化 JSON，包含设备联动建议、任务调度优化、异常预警、个性化建议。
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---- 系统提示词 ------------------------------------------------------------

_SYSTEM_PROMPT = """你是一位专业智能家庭顾问，负责综合分析家庭多维数据并生成可执行的智能建议。

你需要基于以下数据源进行关联分析：
1. 设备当前状态 - 所有物联网设备的当前属性、状态、连接质量
2. 设备历史趋势 - 每个设备最近若干次传感器读数的时间序列（含温度/湿度/CO2/电量等），用于趋势分析
3. 近期事件 - 最近24小时内的告警、异常、状态变更事件
4. 系统日志 - 最近系统操作记录、错误日志、警告信息
5. 家庭成员 - 成员信息、角色、家庭成员身份、在线状态
6. 任务状态 - 日常任务的执行进度与完成率
7. 家庭档案 - 家庭规则、偏好设置、人员配置

分析要求：
- 设备联动：基于设备状态关联和设备间依赖关系，推荐自动化场景。结合历史趋势判断联动是否必要
- 任务优化：基于成员习惯和任务完成情况，调整任务时间或频率
- 异常预警：基于设备历史趋势（如传感器数值持续异常上升/下降、电池电量快速衰减）和系统日志（如频繁错误），提前识别潜在风险
- 个性化建议：针对具体成员的生活习惯和偏好，给出定制化建议
- 关联分析：将设备历史趋势与事件、系统日志交叉对比，发现隐藏问题（如系统报错导致设备数据缺失）

输出格式：严格纯 JSON，不包含任何 markdown 代码块标记。"""

_USER_PROMPT = """请基于以下家庭数据进行综合分析并输出 JSON：

## 设备当前状态
{devices}

## 设备历史趋势（每个设备最近若干次读数的时间序列）
{sensor_history}

## 近期事件（最近24小时）
{events}

## 系统日志（最近操作记录、错误、警告）
{system_logs}

## 家庭成员
{persons}

## 任务执行状态
{tasks}

## 家庭档案
{profile}

请输出以下 JSON 结构（注意：必须是合法 JSON，不要用 markdown 包裹）：
{{
  "summary": "2-3句话概述家庭当前整体状况，需体现历史趋势和系统状态",
  "device_linkage_suggestions": [
    {{
      "trigger_device": "触发设备名称",
      "trigger_condition": "触发条件",
      "action_device": "执行设备名称",
      "action": "建议的联动动作",
      "rationale": "基于数据分析的建议理由",
      "priority": "high/medium/low"
    }}
  ],
  "task_optimizations": [
    {{
      "task_name": "任务名称",
      "current_status": "当前执行状态",
      "suggestion": "具体优化建议",
      "rationale": "基于数据模式的优化理由",
      "priority": "high/medium/low"
    }}
  ],
  "anomaly_warnings": [
    {{
      "type": "异常类型",
      "detail": "详细预警描述",
      "affected_device": "受影响的设备（如有）",
      "urgency": "urgent/high/medium/low",
      "preventive_action": "建议的预防措施"
    }}
  ],
  "personalized_recommendations": [
    {{
      "target": "目标人员或设备",
      "recommendation": "个性化建议内容",
      "context": "建议产生的背景",
      "priority": "high/medium/low"
    }}
  ]
}}"""


# ---- 上下文 & 结果模型 ----------------------------------------------------

@dataclass
class HomeContext:
    """家庭综合分析上下文"""
    devices: List[Dict[str, Any]] = field(default_factory=list)
    sensor_history: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)  # did -> [历史读数...]
    events: List[Dict[str, Any]] = field(default_factory=list)
    system_logs: List[Dict[str, Any]] = field(default_factory=list)
    persons: List[Dict[str, Any]] = field(default_factory=list)
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    profile: Dict[str, Any] = field(default_factory=dict)
    home_id: str = ""


@dataclass
class HomeAdvisorResult:
    """家庭顾问分析结果"""
    analysis_id: str = ""
    home_id: str = ""
    timestamp_iso: str = ""
    success: bool = False
    summary: str = ""
    device_linkage_suggestions: list = field(default_factory=list)
    task_optimizations: list = field(default_factory=list)
    anomaly_warnings: list = field(default_factory=list)
    personalized_recommendations: list = field(default_factory=list)
    raw_response: str = ""
    model_used: str = ""
    error_message: str = ""
    token_usage: Dict[str, int] = field(default_factory=dict)
    created_ms: int = 0


# ---- 收集器：从现有系统获取上下文数据 -----------------------------------------

async def collect_home_context(mgr) -> HomeContext:
    """从 manager 收集家庭综合上下文数据，含设备历史趋势和系统日志。"""
    context = HomeContext()
    from datetime import timedelta

    # ---- 1. 设备当前状态（真实设备 + 传感器实时读数） ----
    try:
        perception_devices = mgr.adapter.get_connected_devices()
        if perception_devices:
            for did, pdev in perception_devices.items():
                device_data = {
                    "device_id": did,
                    "name": pdev.name,
                    "type": pdev.device_type.value if hasattr(pdev.device_type, 'value') else str(pdev.device_type),
                    "status": "online" if pdev.online else "offline",
                    "room_name": pdev.room_name or "",
                    "lastUpdate": datetime.now().isoformat(),
                }
                # 获取传感器实时读数
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
                        device_data["rssi"] = sd.rssi
                        if dev_data.timestamp:
                            device_data["lastUpdate"] = dev_data.timestamp.isoformat()
                except Exception:
                    pass
                context.devices.append(device_data)
            logger.info("[HomeAdvisor] Collected %d real devices with sensor readings", len(context.devices))
        else:
            logger.warning("[HomeAdvisor] No connected devices from adapter")
    except Exception as e:
        logger.warning("[HomeAdvisor] Failed to collect device states: %s", e)

    # ---- 2. 设备历史趋势（每个设备最近 15 条读数，时间序列） ----
    try:
        all_logs = mgr.sensor_log_repo.query(limit=300)  # 默认按 timestamp DESC 排序
        if isinstance(all_logs, list) and all_logs:
            # 按 did 分组，保留每个设备最近 15 条
            from collections import defaultdict
            device_logs: Dict[str, list] = defaultdict(list)
            for row in all_logs:
                did = row.get("did") if isinstance(row, dict) else getattr(row, "did", "")
                if not did:
                    continue
                device_logs[did].append(row)

            for did, logs in device_logs.items():
                # 只保留每个设备最近 15 条，按时间升序方便 LLM 看趋势
                recent = logs[:15]
                recent.reverse()  # 升序: 最早 → 最新
                context.sensor_history[did] = [
                    {
                        "timestamp": (r.get("timestamp") if isinstance(r, dict) else getattr(r, "timestamp", "")),
                        "sensor_type": (r.get("sensor_type") if isinstance(r, dict) else getattr(r, "sensor_type", "")),
                        "value": (r.get("value") if isinstance(r, dict) else getattr(r, "value", 0)),
                        "unit": (r.get("unit") if isinstance(r, dict) else getattr(r, "unit", "")),
                        "battery": (r.get("battery") if isinstance(r, dict) else getattr(r, "battery", "")),
                        "status": (r.get("status") if isinstance(r, dict) else getattr(r, "status", "")),
                        "temperature": (r.get("temperature") if isinstance(r, dict) else getattr(r, "temperature", None)),
                        "humidity": (r.get("humidity") if isinstance(r, dict) else getattr(r, "humidity", None)),
                        "co2": (r.get("co2") if isinstance(r, dict) else getattr(r, "co2", None)),
                        "pm25": (r.get("pm25") if isinstance(r, dict) else getattr(r, "pm25", None)),
                    }
                    for r in recent
                ]
            logger.info(
                "[HomeAdvisor] Collected sensor history for %d devices, total logs=%d",
                len(context.sensor_history), len(all_logs),
            )
    except Exception as e:
        logger.warning("[HomeAdvisor] Failed to collect sensor history: %s", e)

    # ---- 3. 近期事件（最近24小时） ----
    try:
        day_ago = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        events = mgr.event_repo.query(limit=20, after=day_ago) if hasattr(mgr.event_repo, 'query') else []
        context.events = [
            {
                "event_id": e.get("event_id", "") if isinstance(e, dict) else getattr(e, "event_id", ""),
                "event_type": e.get("event_type", "") if isinstance(e, dict) else getattr(e, "event_type", ""),
                "level": e.get("level", "") if isinstance(e, dict) else getattr(e, "level", ""),
                "device_id": e.get("did", "") if isinstance(e, dict) else getattr(e, "did", ""),
                "timestamp": e.get("timestamp", "") if isinstance(e, dict) else getattr(e, "timestamp", ""),
                "data": e.get("data", {}) if isinstance(e, dict) else getattr(e, "data", {}),
            }
            for e in (events if isinstance(events, list) else [])
        ]
    except Exception as e:
        logger.warning("[HomeAdvisor] Failed to collect recent events: %s", e)

    # ---- 4. 系统日志（最近 30 条，优先错误和警告） ----
    try:
        from heiman.database.log_repo import get_log_repo
        log_repo = get_log_repo()
        # 先拉错误和警告，再补常规日志
        error_logs = log_repo.query(level="error", limit=10)
        warn_logs = log_repo.query(level="warning", limit=10)
        all_op_logs = log_repo.query(limit=20)
        # 合并去重（按 id），按时间倒序
        seen_ids = set()
        merged: list = []
        for lg in (error_logs or []) + (warn_logs or []) + (all_op_logs or []):
            log_id = lg.get("id") if isinstance(lg, dict) else getattr(lg, "id", "")
            if log_id and log_id in seen_ids:
                continue
            if log_id:
                seen_ids.add(log_id)
            merged.append(lg)
        # 按时间倒序，取前 30
        merged.sort(
            key=lambda x: (x.get("time") if isinstance(x, dict) else getattr(x, "time", "")),
            reverse=True,
        )
        context.system_logs = [
            {
                "time": (lg.get("time") if isinstance(lg, dict) else getattr(lg, "time", "")),
                "level": (lg.get("level") if isinstance(lg, dict) else getattr(lg, "level", "")),
                "action": (lg.get("action") if isinstance(lg, dict) else getattr(lg, "action", "")),
                "user": (lg.get("user") if isinstance(lg, dict) else getattr(lg, "user", "")),
                "message": (lg.get("message") if isinstance(lg, dict) else getattr(lg, "message", "")),
            }
            for lg in merged[:30]
        ]
    except Exception as e:
        logger.warning("[HomeAdvisor] Failed to collect system logs: %s", e)

    # ---- 5. 家庭成员（含角色、家庭身份、状态） ----
    try:
        from heiman.database.person_repo import get_person_repo
        person_repo = get_person_repo()
        persons = person_repo.get_all()
        context.persons = [
            {
                "id": getattr(p, "id", str(p)),
                "name": getattr(p, "name", ""),
                "alias_name": getattr(p, "alias_name", ""),
                "role": getattr(p, "role", "family"),
                "role_type": getattr(p, "role_type", ""),
                "is_home_root": getattr(p, "is_home_root", False),
                "status": getattr(p, "status", ""),
                "user_account": getattr(p, "user_account", ""),
                "home_name": getattr(p, "home_name", ""),
                "remark": getattr(p, "remark", ""),
            }
            for p in persons
        ]
    except Exception as e:
        logger.warning("[HomeAdvisor] Failed to collect persons: %s", e)

    # ---- 6. 任务状态 ----
    try:
        from heiman.database.task_repo import TaskRepo
        from heiman.database.task_record_repo import TaskRecordRepo
        task_repo = TaskRepo()
        record_repo = TaskRecordRepo()

        tasks = task_repo.list_all()
        task_statuses = []
        for t in tasks:
            task_id = t.get("task_id", "")
            status_info = {
                "task_id": task_id,
                "description": t.get("description", ""),
                "status": t.get("status", "unknown"),
            }
            try:
                progress = record_repo.get_progress_derived(task_id)
                if progress:
                    status_info["progress_pct"] = progress.progress_pct
                    status_info["remaining"] = progress.remaining
            except Exception:
                pass
            task_statuses.append(status_info)
        context.tasks = task_statuses
    except Exception as e:
        logger.warning("[HomeAdvisor] Failed to collect tasks: %s", e)

    # ---- 7. 家庭档案 ----
    try:
        from heiman.home_profile.service import HomeProfileService
        profile_service = HomeProfileService()
        profile_text = profile_service.rendered()
        context.profile = {"rendered": profile_text}
    except Exception as e:
        logger.warning("[HomeAdvisor] Failed to collect home profile: %s", e)

    return context


# ---- 主分析器 --------------------------------------------------------------

class HomeAdvisor:
    """定时家庭智能顾问 - LLM 多维度分析器"""

    def __init__(self):
        pass

    async def analyze(
        self,
        context: HomeContext,
        model: str | None = None,
        store: bool = True,
    ) -> HomeAdvisorResult:
        """执行多维度家庭数据综合分析。

        Args:
            context: 家庭数据上下文
            model: LLM 模型名，None 则使用配置
            store: 是否存入数据库

        Returns:
            HomeAdvisorResult 包含结构化分析结果
        """
        analysis_id = str(uuid.uuid4())
        created_ms = int(time.time() * 1000)
        timestamp = datetime.utcnow().isoformat()

        try:
            # 解析模型名
            if model is None:
                model = self._get_default_model()

            prompt = self._build_prompt(context)
            logger.info(
                "[HomeAdvisor] Sending home analysis request | home=%s devices=%d history_devices=%d events=%d syslogs=%d persons=%d tasks=%d",
                context.home_id,
                len(context.devices),
                len(context.sensor_history),
                len(context.events),
                len(context.system_logs),
                len(context.persons),
                len(context.tasks),
            )

            raw_response, token_usage = await self._call_llm(prompt, model)
            parsed = self._parse_response(raw_response)

            result = HomeAdvisorResult(
                analysis_id=analysis_id,
                home_id=context.home_id,
                timestamp_iso=timestamp,
                success=True,
                summary=parsed.get("summary", ""),
                device_linkage_suggestions=parsed.get("device_linkage_suggestions", []),
                task_optimizations=parsed.get("task_optimizations", []),
                anomaly_warnings=parsed.get("anomaly_warnings", []),
                personalized_recommendations=parsed.get("personalized_recommendations", []),
                raw_response=raw_response,
                model_used=model,
                token_usage=token_usage,
                created_ms=created_ms,
            )

            if store:
                self._last_ctx_devices = len(context.devices)
                self._last_ctx_history = len(context.sensor_history)
                self._last_ctx_events = len(context.events)
                self._last_ctx_syslogs = len(context.system_logs)
                self._last_ctx_persons = len(context.persons)
                self._last_ctx_tasks = len(context.tasks)
                self._store_result(result)

            suggestion_count = (
                len(result.device_linkage_suggestions)
                + len(result.task_optimizations)
                + len(result.anomaly_warnings)
                + len(result.personalized_recommendations)
            )
            logger.info(
                "[HomeAdvisor] Analysis complete | analysis_id=%s suggestions=%d summary=%s",
                analysis_id, suggestion_count,
                result.summary[:80] if result.summary else "(empty)",
            )
            return result

        except Exception as e:
            logger.error(
                "[HomeAdvisor] Analysis failed | analysis_id=%s error=%s",
                analysis_id, e, exc_info=True,
            )
            return HomeAdvisorResult(
                analysis_id=analysis_id,
                home_id=context.home_id,
                timestamp_iso=timestamp,
                success=False,
                error_message=str(e),
                created_ms=created_ms,
            )

    # ---- 内部方法 -----------------------------------------------------------

    @staticmethod
    def _get_default_model() -> str:
        """从配置获取默认模型名。"""
        try:
            from heiman.config import get_settings
            settings = get_settings()
            heiman_model = getattr(settings, "model", None)
            if heiman_model and hasattr(heiman_model, "heiman"):
                return getattr(heiman_model.heiman, "model", "qwen3:8b")
        except Exception:
            pass
        return "qwen3:8b"

    def _build_prompt(self, ctx: HomeContext) -> str:
        """构造 LLM 提示词。"""
        # 传感器历史：每个设备显示最近读数摘要 + 关键趋势指标
        sensor_history_summary = {}
        for did, history in ctx.sensor_history.items():
            if not history:
                continue
            sensor_history_summary[did] = {
                "readings_count": len(history),
                "time_range": f"{history[0].get('timestamp', '?')} ~ {history[-1].get('timestamp', '?')}",
                "latest": history[-1] if history else {},
                "readings": history,
            }

        return _USER_PROMPT.format(
            devices=json.dumps(ctx.devices[:30], ensure_ascii=False, indent=2),
            sensor_history=json.dumps(sensor_history_summary, ensure_ascii=False, indent=2),
            events=json.dumps(ctx.events[:15], ensure_ascii=False, indent=2),
            system_logs=json.dumps(ctx.system_logs[:30], ensure_ascii=False, indent=2),
            persons=json.dumps(ctx.persons, ensure_ascii=False, indent=2),
            tasks=json.dumps(ctx.tasks, ensure_ascii=False, indent=2),
            profile=json.dumps(ctx.profile, ensure_ascii=False, indent=2),
        )

    async def _call_llm(self, prompt: str, model: str) -> tuple[str, dict]:
        """异步调用 LLM，返回 (响应文本, token_usage)。"""
        from openai import AsyncOpenAI

        from heiman.config import get_settings

        settings = get_settings()
        heiman_model = getattr(settings, "model", None)
        if heiman_model and hasattr(heiman_model, "heiman"):
            profile = heiman_model.heiman
            base_url = getattr(profile, "base_url", "http://127.0.0.1:11434/v1")
            api_key = getattr(profile, "api_key", "ollama")
        else:
            base_url = "http://127.0.0.1:11434/v1"
            api_key = "ollama"

        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"

        client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        start_time = time.time()

        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.5,
            "max_tokens": 2048,
        }

        # response_format 兼容
        try:
            kwargs["response_format"] = {"type": "json_object"}
            response = await client.chat.completions.create(**kwargs)
        except Exception as fmt_err:
            logger.warning(
                "[HomeAdvisor] response_format not supported by %s, retrying: %s",
                model, fmt_err,
            )
            del kwargs["response_format"]
            response = await client.chat.completions.create(**kwargs)

        elapsed = time.time() - start_time
        content = response.choices[0].message.content or "{}"
        token_usage = {}

        if hasattr(response, "usage") and response.usage:
            token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            logger.info(
                "[HomeAdvisor] LLM token usage - model=%s, prompt=%d, completion=%d, total=%d, elapsed=%.2fs",
                model,
                token_usage["prompt_tokens"],
                token_usage["completion_tokens"],
                token_usage["total_tokens"],
                elapsed,
            )

        return content, token_usage

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """解析 LLM JSON 响应，处理各种格式异常。"""
        text = raw.strip()
        # 清理 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning("[HomeAdvisor] Failed to parse JSON, returning empty")
            return {}

    def _store_result(self, result: HomeAdvisorResult) -> None:
        """将分析结果存入 ai_analysis_results 表。"""
        try:
            from heiman.database.connector import get_db_connector
            db = get_db_connector()
            result_json = json.dumps({
                "summary": result.summary,
                "device_linkage_suggestions": result.device_linkage_suggestions,
                "task_optimizations": result.task_optimizations,
                "anomaly_warnings": result.anomaly_warnings,
                "personalized_recommendations": result.personalized_recommendations,
                "token_usage": result.token_usage,
                "model_used": result.model_used,
                "success": result.success,
                "error_message": result.error_message,
                "context_stats": {
                    "devices": getattr(self, "_last_ctx_devices", 0),
                    "sensor_history_devices": getattr(self, "_last_ctx_history", 0),
                    "events": getattr(self, "_last_ctx_events", 0),
                    "system_logs": getattr(self, "_last_ctx_syslogs", 0),
                    "persons": getattr(self, "_last_ctx_persons", 0),
                    "tasks": getattr(self, "_last_ctx_tasks", 0),
                },
            }, ensure_ascii=False)

            with db.get_connection() as conn:
                conn.execute(
                    """INSERT INTO ai_analysis_results
                       (analysis_id, analysis_type, result_data, timestamp_ms, home_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        result.analysis_id,
                        "llm_home_advisor",
                        result_json,
                        result.created_ms,
                        result.home_id or "",
                        result.timestamp_iso,
                    ),
                )
                conn.commit()
            logger.info("[HomeAdvisor] Result stored to DB: analysis_id=%s", result.analysis_id)
        except Exception as e:
            logger.error("[HomeAdvisor] Failed to store result: %s", e)


# ---- 便捷入口 --------------------------------------------------------------

async def run_home_advisor() -> HomeAdvisorResult | None:
    """便捷入口：收集上下文 → 调用 LLM → 返回结果。

    供 scheduled_ai_task.py 调用。
    """
    try:
        from heiman.manager import get_manager

        mgr = get_manager()
        context = await collect_home_context(mgr)

        if not context.devices and not context.events and not context.sensor_history:
            logger.info("[HomeAdvisor] No data to analyze, skipping")
            return None

        advisor = HomeAdvisor()
        result = await advisor.analyze(context, store=True)
        return result

    except Exception as e:
        logger.error("[HomeAdvisor] Home advisor run failed: %s", e, exc_info=True)
        return None
