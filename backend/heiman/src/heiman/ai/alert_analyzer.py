"""
告警事件规则引擎分析器

触发时机：告警事件在 ML 分析完成后，自动调用此模块。
基于现有 ML 模型结果（异常检测、舒适度、行为识别），通过规则引擎
直接输出结构化的处理建议（JSON），包含根因分析、影响评估和修复步骤。

不依赖 LLM，零 token 消耗，毫秒级响应。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class AlertContext:
    """告警事件的完整上下文数据。"""

    event_id: str
    event_type: str                          # smoke_alarm / water_leak / tamper_alarm / co_alarm …
    device_id: str
    device_name: str
    device_type: str
    room_name: str
    home_id: str

    # 实时指标
    current_values: Dict[str, Any] = field(default_factory=dict)

    # 历史趋势（最近 24h）
    historical_events_count: int = 0
    recent_events: List[Dict[str, Any]] = field(default_factory=list)
    recent_readings: List[Dict[str, Any]] = field(default_factory=list)

    # 设备配置
    device_config: Dict[str, Any] = field(default_factory=dict)
    related_devices: List[Dict[str, Any]] = field(default_factory=list)

    # ML 分析结果
    anomaly_score: float = 0.0
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    comfort_score: float = 0.0
    behavior_analysis: Dict[str, Any] = field(default_factory=dict)

    # 关联日志
    system_logs: List[Dict[str, Any]] = field(default_factory=list)

    # 时间
    timestamp_ms: int = 0
    timestamp_iso: str = ""


@dataclass
class AlertAnalysisResult:
    """规则引擎输出的结构化告警分析结果。"""

    analysis_id: str
    event_id: str
    alert_type: str

    root_cause_analysis: Dict[str, Any] = field(default_factory=dict)
    impact_assessment: Dict[str, Any] = field(default_factory=dict)
    remediation_steps: List[Dict[str, Any]] = field(default_factory=list)
    urgency_level: str = "medium"
    recommended_actions: List[str] = field(default_factory=list)

    # 分析模式
    analysis_mode: str = "rule_engine"       # rule_engine / llm (标记分析方式)
    created_at_ms: int = 0

    success: bool = True
    error_message: str = ""


# ---------------------------------------------------------------------------
# 规则引擎核心
# ---------------------------------------------------------------------------

class AlertAnalyzer:
    """告警事件规则引擎分析器。

    基于 ML 模型结果（异常评分、舒适度、行为识别）及设备上下文，
    通过领域规则直接生成结构化分析 JSON，不依赖外部 LLM。
    """

    DEFAULT_TABLE = "alert_analyses"

    # 历史事件激增阈值：24h 内同类事件超过此值视为高频告警
    _FREQUENT_ALERT_THRESHOLD = 3

    # 异常评分阈值
    _ANOMALY_HIGH = 0.7
    _ANOMALY_MEDIUM = 0.4

    # 温度阈值（摄氏度）
    _TEMP_DANGER = 60.0
    _TEMP_HIGH = 45.0

    # CO 浓度阈值（ppm）
    _CO_DANGER = 400
    _CO_HIGH = 100

    # 烟雾浓度阈值（ppm）
    _SMOKE_DANGER = 500
    _SMOKE_HIGH = 200

    def __init__(self, db, llm_client=None, decision_engine=None):
        self._db = db
        # 保留参数兼容性但不使用 LLM

    # ---- 主入口 -----------------------------------------------------------

    async def analyze(
        self,
        context: AlertContext,
        model: str = "",
        store: bool = True,
    ) -> AlertAnalysisResult:
        """对告警事件执行规则引擎分析。

        Args:
            context: 告警上下文数据（含 ML 分析结果）
            store: 是否将结果存入数据库

        Returns:
            AlertAnalysisResult 包含结构化 JSON 分析结果
        """
        analysis_id = str(uuid.uuid4())
        created_ms = int(time.time() * 1000)

        try:
            logger.info(
                "[AlertAnalyzer] Rule-engine analysis | event=%s type=%s device=%s",
                context.event_id, context.event_type, context.device_name,
            )

            # 根据告警类型分发到不同的规则处理器
            result_data = self._analyze_by_rules(context)

            result = AlertAnalysisResult(
                analysis_id=analysis_id,
                event_id=context.event_id,
                alert_type=context.event_type,
                root_cause_analysis=result_data.get("root_cause_analysis", {}),
                impact_assessment=result_data.get("impact_assessment", {}),
                remediation_steps=result_data.get("remediation_steps", []),
                urgency_level=result_data.get("urgency_level", "medium"),
                recommended_actions=result_data.get("recommended_actions", []),
                analysis_mode="rule_engine",
                created_at_ms=created_ms,
                success=True,
            )

            if store:
                self._store_result(result)

            logger.info(
                "[AlertAnalyzer] Analysis complete | event=%s urgency=%s steps=%d mode=rule_engine",
                context.event_id, result.urgency_level, len(result.remediation_steps),
            )
            return result

        except Exception as e:
            logger.error(
                "[AlertAnalyzer] Analysis failed | event=%s error=%s",
                context.event_id, e, exc_info=True,
            )
            return AlertAnalysisResult(
                analysis_id=analysis_id,
                event_id=context.event_id,
                alert_type=context.event_type,
                success=False,
                error_message=str(e),
                created_at_ms=created_ms,
            )

    # ---- 规则分发 ---------------------------------------------------------

    def _analyze_by_rules(self, ctx: AlertContext) -> Dict[str, Any]:
        """根据告警类型分发到对应的规则处理器。"""
        et = ctx.event_type

        if et in ("smoke_alarm", "smoke_warning"):
            return self._analyze_smoke(ctx)
        elif et in ("co_alarm", "co_warning"):
            return self._analyze_co(ctx)
        elif et in ("water_leak", "water_alarm", "water_warning"):
            return self._analyze_water_leak(ctx)
        elif et in ("tamper_alarm",):
            return self._analyze_tamper(ctx)
        elif et in ("temperature_high", "temp_alarm", "temp_warning"):
            return self._analyze_temperature(ctx)
        elif et in ("device_offline",):
            return self._analyze_device_offline(ctx)
        elif et in ("contact_alarm", "contact_warning"):
            return self._analyze_contact(ctx)
        elif et in ("motion_alarm", "motion_detected"):
            return self._analyze_motion(ctx)
        else:
            return self._analyze_generic(ctx)

    # ---- 通用辅助方法 -----------------------------------------------------

    def _count_recent_similar_events(self, ctx: AlertContext) -> int:
        """统计最近 24h 同类事件数量。"""
        count = 0
        for ev in ctx.recent_events:
            if isinstance(ev, dict) and ev.get("event_type") == ctx.event_type:
                count += 1
        return count

    def _get_sensor_value(self, ctx: AlertContext, key: str, default: float = 0.0) -> float:
        """从 current_values 中提取传感器数值。"""
        val = ctx.current_values.get(key, default)
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    def _get_behavior_activity(self, ctx: AlertContext) -> str:
        """获取行为分析中的当前活动。"""
        ba = ctx.behavior_analysis
        if isinstance(ba, dict):
            return ba.get("activity", "unknown").lower()
        return "unknown"

    def _get_behavior_confidence(self, ctx: AlertContext) -> float:
        """获取行为识别的置信度。"""
        ba = ctx.behavior_analysis
        if isinstance(ba, dict):
            return float(ba.get("confidence", 0))
        return 0.0

    def _build_evidence_list(self, ctx: AlertContext, *extra: str) -> List[str]:
        """构建证据列表（从传感器指标和 ML 结果中提取）。"""
        evidence = []
        cv = ctx.current_values
        if cv.get("temperature") is not None:
            evidence.append(f"当前温度: {cv['temperature']}°C")
        if cv.get("humidity") is not None:
            evidence.append(f"当前湿度: {cv['humidity']}%")
        if cv.get("smoke_ppm") is not None:
            evidence.append(f"烟雾浓度: {cv['smoke_ppm']}ppm")
        if cv.get("co_ppm") is not None:
            evidence.append(f"CO 浓度: {cv['co_ppm']}ppm")
        if cv.get("battery") is not None:
            evidence.append(f"电池电量: {cv['battery']}%")
        if cv.get("signal_strength") is not None:
            evidence.append(f"信号强度: {cv['signal_strength']}dBm")
        if ctx.anomaly_score > 0:
            evidence.append(f"ML 异常评分: {ctx.anomaly_score:.2f}")
        for a in ctx.anomalies:
            msg = a.get("message", "") if isinstance(a, dict) else str(a)
            if msg:
                evidence.append(f"异常检测: {msg}")
        evidence.extend(extra)
        evidence.append(f"24h 同类事件数: {self._count_recent_similar_events(ctx)}")
        return [e for e in evidence if e]

    def _frequent_alerts_remediation(self) -> List[Dict[str, Any]]:
        """高频告警的通用缓解建议。"""
        return [{
            "step": 1,
            "action": "该设备在 24 小时内被频繁触发，检查传感器是否存在故障或安装位置不当",
            "urgency": "short_term",
            "expected_outcome": "确认传感器可靠性，减少误报",
            "requires_manual_intervention": True,
        }]

    # ---- 烟雾告警规则 -----------------------------------------------------

    def _analyze_smoke(self, ctx: AlertContext) -> Dict[str, Any]:
        smoke_ppm = self._get_sensor_value(ctx, "smoke_ppm")
        temp = self._get_sensor_value(ctx, "temperature")
        anomaly = ctx.anomaly_score
        activity = self._get_behavior_activity(ctx)
        similar_count = self._count_recent_similar_events(ctx)

        # --- 误报判断 ---
        is_false_alarm = False
        false_reason = None

        # 规则1：低烟雾 + 低异常评分 = 可能是灰尘/蒸汽
        if smoke_ppm < self._SMOKE_HIGH and anomaly < self._ANOMALY_MEDIUM:
            is_false_alarm = True
            false_reason = "烟雾浓度低且 ML 异常评分低，可能是灰尘、蒸汽或短暂油烟触发"

        # 规则2：行为识别为 cooking 且温度中等
        if activity in ("cooking", "kitchen") and temp < self._TEMP_DANGER and anomaly < self._ANOMALY_HIGH:
            is_false_alarm = True
            false_reason = "行为分析识别为烹饪活动，当前温度和异常评分不支持真实火情"

        # 规则3：高频告警但数据稳定 = 传感器老化
        if similar_count >= self._FREQUENT_ALERT_THRESHOLD and anomaly < self._ANOMALY_MEDIUM:
            is_false_alarm = True
            false_reason = f"24h 内已触发 {similar_count} 次，传感器数值稳定，建议检查传感器老化或积灰"

        # --- 根因分析 ---
        if is_false_alarm:
            primary_cause = f"烟雾传感器误报: {false_reason}"
            confidence = 0.85
        elif smoke_ppm >= self._SMOKE_DANGER and temp >= self._TEMP_DANGER:
            primary_cause = f"疑似真实火情：烟雾浓度 {smoke_ppm}ppm 且温度 {temp}°C 均已达到危险水平"
            confidence = 0.95
        elif anomaly >= self._ANOMALY_HIGH:
            primary_cause = "ML 异常检测高分，烟雾与温度组合异常，需要立即排查"
            confidence = 0.85
        else:
            primary_cause = f"烟雾传感器触发，烟雾浓度 {smoke_ppm}ppm，需人工确认"
            confidence = 0.6

        # --- 影响评估 ---
        if smoke_ppm >= self._SMOKE_DANGER and temp >= self._TEMP_DANGER:
            severity = "critical"
            consequences = ["危及生命安全", "可能导致严重财产损失", "烟雾可能蔓延至其他房间"]
            scope = "building_wide"
        elif anomaly >= self._ANOMALY_HIGH and not is_false_alarm:
            severity = "high"
            consequences = ["存在火灾隐患", "需要立即确认火源"]
            scope = "floor_wide"
        elif is_false_alarm:
            severity = "low"
            consequences = ["误报对生活造成干扰", "频繁误报可能导致真实告警被忽视"]
            scope = "localized"
        else:
            severity = "medium"
            consequences = ["需要确认是否有火源"]
            scope = "localized"

        # --- 修复步骤 ---
        if not is_false_alarm and smoke_ppm >= self._SMOKE_DANGER:
            remediation = [
                {"step": 1, "action": "立即检查是否有明火或浓烟，确保人员安全", "urgency": "immediate",
                 "expected_outcome": "确认火情真实性", "requires_manual_intervention": True},
                {"step": 2, "action": "如确认有火情，立即拨打119并组织撤离", "urgency": "immediate",
                 "expected_outcome": "减少人员伤亡", "requires_manual_intervention": True},
                {"step": 3, "action": "关闭燃气阀门和电源总闸", "urgency": "immediate",
                 "expected_outcome": "阻止火势蔓延", "requires_manual_intervention": True},
            ]
        elif not is_false_alarm:
            remediation = [
                {"step": 1, "action": "检查烟雾传感器附近是否有异常烟雾来源", "urgency": "short_term",
                 "expected_outcome": "定位烟雾来源", "requires_manual_intervention": True},
                {"step": 2, "action": "开窗通风，降低室内烟雾浓度", "urgency": "short_term",
                 "expected_outcome": "改善空气质量", "requires_manual_intervention": False},
            ]
        else:
            remediation = [
                {"step": 1, "action": "清理传感器表面灰尘或检查附近是否有蒸汽源", "urgency": "short_term",
                 "expected_outcome": "消除误报源", "requires_manual_intervention": True},
                {"step": 2, "action": "如持续误报，考虑更换传感器位置或固件", "urgency": "long_term",
                 "expected_outcome": "减少误报概率", "requires_manual_intervention": False},
            ]
            if similar_count >= self._FREQUENT_ALERT_THRESHOLD:
                remediation.extend(self._frequent_alerts_remediation())

        # --- 紧急程度 ---
        if smoke_ppm >= self._SMOKE_DANGER and temp >= self._TEMP_DANGER:
            urgency = "critical"
        elif anomaly >= self._ANOMALY_HIGH and not is_false_alarm:
            urgency = "high"
        elif is_false_alarm:
            urgency = "low"
        else:
            urgency = "medium"

        return {
            "root_cause_analysis": {
                "primary_cause": primary_cause,
                "confidence": confidence,
                "contributing_factors": self._smoke_contributing_factors(ctx, is_false_alarm),
                "evidence": self._build_evidence_list(
                    ctx,
                    f"烟雾浓度: {smoke_ppm}ppm (危险阈值: {self._SMOKE_DANGER}ppm)",
                    f"ML 异常评分: {anomaly:.2f}",
                    f"当前行为: {activity}",
                ),
                "is_false_alarm": is_false_alarm,
                "false_alarm_reason": false_reason,
            },
            "impact_assessment": {
                "severity": severity,
                "affected_rooms": [ctx.room_name],
                "affected_devices": [ctx.device_name] + [d.get("name", "") for d in ctx.related_devices],
                "potential_consequences": consequences,
                "estimated_scope": scope,
            },
            "remediation_steps": remediation,
            "urgency_level": urgency,
            "recommended_actions": self._smoke_actions(ctx, is_false_alarm, urgency),
        }

    def _smoke_contributing_factors(self, ctx: AlertContext, is_false: bool) -> List[str]:
        factors = []
        activity = self._get_behavior_activity(ctx)
        if activity == "cooking":
            factors.append("当前正在进行烹饪活动")
        temp = self._get_sensor_value(ctx, "temperature")
        if temp >= self._TEMP_HIGH:
            factors.append(f"环境温度偏高 ({temp}°C)")
        if self._count_recent_similar_events(ctx) >= self._FREQUENT_ALERT_THRESHOLD:
            factors.append("传感器频繁触发，可能存在老化或安装问题")
        if is_false:
            factors.append("综合分析判断为误报")
        return factors if factors else ["需要进一步排查"]

    def _smoke_actions(self, ctx: AlertContext, is_false: bool, urgency: str) -> List[str]:
        if urgency == "critical":
            return ["立即撤离并拨打119", "关闭燃气和电源", "通知所有家庭成员"]
        elif urgency == "high":
            return ["立即确认火情", "准备灭火器", "通知家庭成员警惕"]
        elif is_false:
            return ["清洁烟雾传感器", "检查传感器安装位置是否合适（是否离厨房太近）", "评估是否需要更新报警阈值"]
        else:
            return ["检查烟雾来源", "开窗通风"]

    # ---- CO 告警规则 -----------------------------------------------------

    def _analyze_co(self, ctx: AlertContext) -> Dict[str, Any]:
        co_ppm = self._get_sensor_value(ctx, "co_ppm")
        anomaly = ctx.anomaly_score
        behavior = self._get_behavior_activity(ctx)

        # 误报判断
        is_false_alarm = False
        false_reason = None
        if co_ppm < self._CO_HIGH and anomaly < self._ANOMALY_MEDIUM:
            is_false_alarm = True
            false_reason = "CO 浓度低且异常评分低，传感器可能受到干扰"

        # 根因
        if co_ppm >= self._CO_DANGER:
            cause = f"CO 浓度 {co_ppm}ppm 已达危险水平，可能源自燃气泄漏或通风不良"
            confidence = 0.95
        elif anomaly >= self._ANOMALY_HIGH:
            cause = f"CO 浓度 {co_ppm}ppm 配合 ML 异常高分，需紧急排查"
            confidence = 0.85
        else:
            cause = f"CO 传感器触发，当前浓度 {co_ppm}ppm"
            confidence = 0.6

        # 影响
        if co_ppm >= self._CO_DANGER:
            severity = "critical"
            consequences = ["一氧化碳中毒风险极高", "危及生命安全", "无色无味，人员可能已失去意识"]
            scope = "building_wide"
        elif co_ppm >= self._CO_HIGH:
            severity = "high"
            consequences = ["长时间暴露可能导致中毒", "对老人、儿童和宠物危害更大"]
            scope = "building_wide"
        else:
            severity = "medium"
            consequences = ["需要确认室内通风情况"]
            scope = "localized"

        # 修复步骤
        if co_ppm >= self._CO_DANGER:
            remediation = [
                {"step": 1, "action": "立即打开所有门窗通风", "urgency": "immediate",
                 "expected_outcome": "降低室内 CO 浓度", "requires_manual_intervention": True},
                {"step": 2, "action": "所有人员立即转移到室外", "urgency": "immediate",
                 "expected_outcome": "避免中毒", "requires_manual_intervention": True},
                {"step": 3, "action": "联系燃气公司检查管道，拨打120如有人不适", "urgency": "immediate",
                 "expected_outcome": "排查泄漏源并救治", "requires_manual_intervention": True},
            ]
        elif co_ppm >= self._CO_HIGH:
            remediation = [
                {"step": 1, "action": "打开窗户通风，关闭燃气阀门", "urgency": "immediate",
                 "expected_outcome": "降低 CO 浓度", "requires_manual_intervention": True},
                {"step": 2, "action": "检查燃气设备（热水器、灶具）是否正常燃烧", "urgency": "short_term",
                 "expected_outcome": "定位泄漏源", "requires_manual_intervention": True},
            ]
        else:
            remediation = [
                {"step": 1, "action": "开窗通风并观察 CO 浓度变化", "urgency": "short_term",
                 "expected_outcome": "确认是否为短暂波动", "requires_manual_intervention": False},
                {"step": 2, "action": "如持续触发，预约专业人员检查燃气设备", "urgency": "long_term",
                 "expected_outcome": "排除安全隐患", "requires_manual_intervention": True},
            ]

        urgency = "critical" if co_ppm >= self._CO_DANGER else ("high" if co_ppm >= self._CO_HIGH else "medium")

        return {
            "root_cause_analysis": {
                "primary_cause": cause,
                "confidence": confidence,
                "contributing_factors": self._co_factors(co_ppm, behavior, anomaly),
                "evidence": self._build_evidence_list(ctx, f"CO 浓度: {co_ppm}ppm (危险阈值: {self._CO_DANGER}ppm)"),
                "is_false_alarm": is_false_alarm,
                "false_alarm_reason": false_reason,
            },
            "impact_assessment": {
                "severity": severity,
                "affected_rooms": [ctx.room_name] + [self._get_adjacent_room_names(ctx)],
                "affected_devices": [ctx.device_name],
                "potential_consequences": consequences,
                "estimated_scope": scope,
            },
            "remediation_steps": remediation,
            "urgency_level": urgency,
            "recommended_actions": (
                ["立即撤离至室外", "打开所有门窗", "拨打120及燃气公司电话"]
                if urgency == "critical"
                else ["开窗通风", "关闭燃气阀门", "检查燃气设备"] if urgency == "high"
                else ["通风观察", "如有不适及时就医"]
            ),
        }

    def _co_factors(self, co_ppm: float, behavior: str, anomaly: float) -> List[str]:
        f = []
        if co_ppm >= self._CO_DANGER:
            f.append("CO 浓度严重超标")
        if anomaly >= self._ANOMALY_HIGH:
            f.append("ML 异常评分显示数据模式异常")
        if behavior in ("sleeping", "sleep"):
            f.append("人员处于睡眠状态，更难察觉 CO 泄漏")
        elif behavior == "away":
            f.append("人员可能不在室内")
        return f if f else ["待进一步排查"]

    def _get_adjacent_room_names(self, ctx: AlertContext) -> str:
        """获取相邻房间名（基于关联设备）。"""
        rooms = set()
        for d in ctx.related_devices:
            r = d.get("room", "") if isinstance(d, dict) else ""
            if r and r != ctx.room_name:
                rooms.add(r)
        return ", ".join(rooms) if rooms else ctx.room_name

    # ---- 漏水告警规则 -----------------------------------------------------

    def _analyze_water_leak(self, ctx: AlertContext) -> Dict[str, Any]:
        anomaly = ctx.anomaly_score
        similar_count = self._count_recent_similar_events(ctx)
        battery = self._get_sensor_value(ctx, "battery", 100)

        # 关联设备是否有同房间的其他水传感器
        related_water_sensors = [
            d.get("name", "") for d in ctx.related_devices
            if isinstance(d, dict) and "water" in d.get("type", "").lower()
        ]

        is_false_alarm = False
        false_reason = None
        if anomaly < self._ANOMALY_MEDIUM and battery > 50:
            if similar_count >= self._FREQUENT_ALERT_THRESHOLD:
                is_false_alarm = True
                false_reason = f"24h 触发 {similar_count} 次，电池正常，可能是传感器安装位置潮湿"
            else:
                is_false_alarm = True
                false_reason = "ML 异常评分低，且电池电量正常，可能是冷凝水或短暂潮湿触发"

        if anomaly >= self._ANOMALY_HIGH:
            cause = f"漏水传感器触发，ML 异常评分 {anomaly:.2f}，高概率存在真实漏水"
            confidence = 0.90
        elif related_water_sensors:
            cause = f"同房间 {', '.join(related_water_sensors)} 也存在水传感器，需要交叉验证"
            confidence = 0.75
        else:
            cause = "漏水传感器检测到水分，需人工确认是否为真实漏水"
            confidence = 0.5

        if anomaly >= self._ANOMALY_HIGH:
            severity = "high"
            consequences = ["可能造成地板/墙面损坏", "漏水过多可能导致楼下渗水", "长期漏水引发霉菌"]
            scope = "floor_wide"
        elif is_false_alarm:
            severity = "low"
            consequences = ["轻微误报"]
            scope = "localized"
        else:
            severity = "medium"
            consequences = ["存在漏水隐患"]
            scope = "localized"

        if severity in ("high", "critical"):
            remediation = [
                {"step": 1, "action": "立即检查漏水传感器位置的实际情况", "urgency": "immediate",
                 "expected_outcome": "确认漏水真实性", "requires_manual_intervention": True},
                {"step": 2, "action": "关闭对应区域的水阀", "urgency": "immediate",
                 "expected_outcome": "阻止进一步漏水", "requires_manual_intervention": True},
                {"step": 3, "action": "清理积水并使用吸水设备处理", "urgency": "short_term",
                 "expected_outcome": "减少水渍损害", "requires_manual_intervention": False},
            ]
        else:
            remediation = [
                {"step": 1, "action": "检查传感器周围是否有水渍", "urgency": "short_term",
                 "expected_outcome": "确认告警真实性", "requires_manual_intervention": True},
            ]
            if is_false_alarm:
                remediation.append({
                    "step": 2, "action": "擦干传感器探头，检查安装位置是否容易积水", "urgency": "long_term",
                    "expected_outcome": "防止重复误报", "requires_manual_intervention": True,
                })

        urgency = "high" if severity == "high" else ("low" if is_false_alarm else "medium")

        return {
            "root_cause_analysis": {
                "primary_cause": cause,
                "confidence": confidence,
                "contributing_factors": (
                    [f"同房间有关联水传感器: {', '.join(related_water_sensors)}"] if related_water_sensors
                    else ["当前数据不足以区分真实漏水与误报"]
                ),
                "evidence": self._build_evidence_list(ctx),
                "is_false_alarm": is_false_alarm,
                "false_alarm_reason": false_reason,
            },
            "impact_assessment": {
                "severity": severity,
                "affected_rooms": [ctx.room_name],
                "affected_devices": [ctx.device_name],
                "potential_consequences": consequences,
                "estimated_scope": scope,
            },
            "remediation_steps": remediation,
            "urgency_level": urgency,
            "recommended_actions": (
                ["立即检查漏水点", "关闭水阀", "清理积水"]
                if urgency == "high"
                else ["检查传感器位置", "确认是否有水渍"]
            ),
        }

    # ---- 拆动告警规则 -----------------------------------------------------

    def _analyze_tamper(self, ctx: AlertContext) -> Dict[str, Any]:
        anomaly = ctx.anomaly_score
        behavior = self._get_behavior_activity(ctx)

        is_false_alarm = False
        false_reason = None

        # 行为分析显示有人在维护/清洁 = 可能误报
        if behavior in ("cleaning", "maintenance", "moving"):
            is_false_alarm = True
            false_reason = f"行为分析显示正在进行{behavior}活动，可能是正常触碰而非恶意拆动"

        if anomaly >= self._ANOMALY_HIGH and not is_false_alarm:
            cause = "设备被异常拆动，ML 异常评分高，可能存在安全威胁（非法入侵或破坏设备）"
            confidence = 0.85
            severity = "high"
            urgency = "high"
        elif is_false_alarm:
            cause = f"设备拆动为误报，当前行为为{behavior}"
            confidence = 0.80
            severity = "low"
            urgency = "low"
        else:
            cause = "设备检测到拆动事件，需确认原因（可能是清洁、移动家具或安全事件）"
            confidence = 0.50
            severity = "medium"
            urgency = "medium"

        if severity == "high":
            remediation = [
                {"step": 1, "action": "立即检查设备是否被人为移动或破坏", "urgency": "immediate",
                 "expected_outcome": "确认设备状态", "requires_manual_intervention": True},
                {"step": 2, "action": "检查门窗是否有撬动痕迹", "urgency": "immediate",
                 "expected_outcome": "排查非法入侵", "requires_manual_intervention": True},
                {"step": 3, "action": "如确认为安全问题，立即报警", "urgency": "immediate",
                 "expected_outcome": "保障人身安全", "requires_manual_intervention": True},
            ]
        elif is_false_alarm:
            remediation = [
                {"step": 1, "action": f"当前正在进行{behavior}活动，可能是正常接触导致", "urgency": "short_term",
                 "expected_outcome": "无需额外处理", "requires_manual_intervention": False},
            ]
        else:
            remediation = [
                {"step": 1, "action": "检查设备是否被移动或碰撞", "urgency": "short_term",
                 "expected_outcome": "确认告警原因", "requires_manual_intervention": True},
            ]

        return {
            "root_cause_analysis": {
                "primary_cause": cause,
                "confidence": confidence,
                "contributing_factors": [f"当前活动: {behavior}"],
                "evidence": self._build_evidence_list(ctx, f"行为分析: {behavior}"),
                "is_false_alarm": is_false_alarm,
                "false_alarm_reason": false_reason,
            },
            "impact_assessment": {
                "severity": severity,
                "affected_rooms": [ctx.room_name],
                "affected_devices": [ctx.device_name],
                "potential_consequences": (
                    ["设备损坏", "安防失效", "可能伴随非法入侵"]
                    if severity == "high"
                    else ["设备位置可能偏移影响检测精度"]
                ),
                "estimated_scope": "localized",
            },
            "remediation_steps": remediation,
            "urgency_level": urgency,
            "recommended_actions": (
                ["检查设备状态", "检查周边安全", "必要时报警"]
                if urgency == "high"
                else ["检查设备是否松动", "重新固定设备"]
            ),
        }

    # ---- 高温告警规则 -----------------------------------------------------

    def _analyze_temperature(self, ctx: AlertContext) -> Dict[str, Any]:
        temp = self._get_sensor_value(ctx, "temperature")
        anomaly = ctx.anomaly_score
        activity = self._get_behavior_activity(ctx)

        is_false_alarm = False
        false_reason = None
        if activity in ("cooking", "kitchen") and temp < self._TEMP_DANGER:
            is_false_alarm = True
            false_reason = "当前正在烹饪，短时高温属于正常现象"

        if temp >= self._TEMP_DANGER:
            cause = f"当前温度 {temp}°C 达到危险水平，可能源于火灾或设备过热"
            confidence = 0.90
            severity = "high"
            urgency = "high"
        elif anomaly >= self._ANOMALY_HIGH:
            cause = f"温度异常 {temp}°C，ML 异常评分高，建议立即查看"
            confidence = 0.80
            severity = "high"
            urgency = "high"
        elif is_false_alarm:
            cause = f"烹饪引起的短时高温 {temp}°C，属于正常现象"
            confidence = 0.85
            severity = "low"
            urgency = "low"
        else:
            cause = f"温度偏高 {temp}°C，可能是空调故障或天气炎热"
            confidence = 0.50
            severity = "medium"
            urgency = "medium"

        if severity == "high":
            remediation = [
                {"step": 1, "action": "检查是否有火源或电器过热", "urgency": "immediate",
                 "expected_outcome": "排查火灾隐患", "requires_manual_intervention": True},
                {"step": 2, "action": "关闭不必要的电器，打开窗户降温", "urgency": "immediate",
                 "expected_outcome": "降低室内温度", "requires_manual_intervention": False},
            ]
        elif is_false_alarm:
            remediation = [
                {"step": 1, "action": "烹饪完成后温度将自然下降，无需特殊处理", "urgency": "short_term",
                 "expected_outcome": "等待自然降温", "requires_manual_intervention": False},
            ]
        else:
            remediation = [
                {"step": 1, "action": "检查空调或通风设备是否正常", "urgency": "short_term",
                 "expected_outcome": "确认降温设备工作正常", "requires_manual_intervention": True},
                {"step": 2, "action": "如持续高温，考虑增加通风或临时关闭发热电器", "urgency": "long_term",
                 "expected_outcome": "改善室内环境", "requires_manual_intervention": False},
            ]

        return {
            "root_cause_analysis": {
                "primary_cause": cause,
                "confidence": confidence,
                "contributing_factors": ([f"当前活动: {activity}"] if activity != "unknown" else []) + (
                    ["温度显著超出正常范围"] if temp >= self._TEMP_HIGH else []
                ),
                "evidence": self._build_evidence_list(ctx, f"温度: {temp}°C (高阈值: {self._TEMP_HIGH}°C)"),
                "is_false_alarm": is_false_alarm,
                "false_alarm_reason": false_reason,
            },
            "impact_assessment": {
                "severity": severity,
                "affected_rooms": [ctx.room_name],
                "affected_devices": [ctx.device_name],
                "potential_consequences": (
                    ["火灾风险", "电器损坏", "人员中暑"]
                    if severity == "high"
                    else ["体感不适", "电器寿命缩短"]
                ),
                "estimated_scope": "localized",
            },
            "remediation_steps": remediation,
            "urgency_level": urgency,
            "recommended_actions": (
                ["检查火源", "关闭发热电器", "通风降温"]
                if urgency == "high"
                else ["开窗通风", "检查空调"] if urgency == "medium"
                else ["无需处理，烹饪后自然降温"]
            ),
        }

    # ---- 设备离线告警规则 -------------------------------------------------

    def _analyze_device_offline(self, ctx: AlertContext) -> Dict[str, Any]:
        battery = self._get_sensor_value(ctx, "battery", 100)
        signal = self._get_sensor_value(ctx, "signal_strength", 0)
        anomaly = ctx.anomaly_score

        if battery <= 10:
            cause = f"设备因电量过低 ({battery}%) 离线，需更换电池"
            confidence = 0.95
            severity = "medium"
            urgency = "medium"
        elif signal <= -90:
            cause = f"设备信号强度 {signal}dBm 极弱，可能超出网关范围"
            confidence = 0.85
            severity = "medium"
            urgency = "medium"
        elif anomaly >= self._ANOMALY_HIGH:
            cause = "设备可能被物理破坏或移除，ML 异常评分高"
            confidence = 0.80
            severity = "high"
            urgency = "high"
        else:
            cause = "设备离线，可能是短暂网络波动或设备休眠"
            confidence = 0.40
            severity = "low"
            urgency = "low"

        return {
            "root_cause_analysis": {
                "primary_cause": cause,
                "confidence": confidence,
                "contributing_factors": (
                    [f"电池电量: {battery}%", f"信号强度: {signal}dBm"]
                    + (["异常评分高，可能设备故障"] if anomaly >= self._ANOMALY_HIGH else [])
                ),
                "evidence": self._build_evidence_list(
                    ctx, f"电池: {battery}%", f"信号: {signal}dBm",
                ),
                "is_false_alarm": False,
                "false_alarm_reason": None,
            },
            "impact_assessment": {
                "severity": severity,
                "affected_rooms": [ctx.room_name],
                "affected_devices": [ctx.device_name],
                "potential_consequences": (
                    ["安防监控盲区", "无法接收该设备告警", "设备可能已被移除"]
                    if severity == "high"
                    else ["该区域暂时失去监控", "可能错过后续告警"]
                ),
                "estimated_scope": "localized",
            },
            "remediation_steps": (
                [
                    {"step": 1, "action": "前往设备位置检查设备是否存在", "urgency": "immediate",
                     "expected_outcome": "确认设备是否被移除", "requires_manual_intervention": True},
                    {"step": 2, "action": "如设备仍在但离线，尝试重启设备或重新配对", "urgency": "short_term",
                     "expected_outcome": "恢复设备连接", "requires_manual_intervention": True},
                ] if severity == "high"
                else [
                    {"step": 1, "action": "更换电池", "urgency": "short_term",
                     "expected_outcome": "恢复设备供电", "requires_manual_intervention": True},
                ] if battery <= 10
                else [
                    {"step": 1, "action": "检查网关与设备的距离，考虑增加中继", "urgency": "long_term",
                     "expected_outcome": "改善信号覆盖", "requires_manual_intervention": False},
                ] if signal <= -90
                else [
                    {"step": 1, "action": "观察设备是否自动恢复上线", "urgency": "short_term",
                     "expected_outcome": "等待自动恢复", "requires_manual_intervention": False},
                ]
            ),
            "urgency_level": urgency,
            "recommended_actions": (
                ["检查设备物理状态", "尝试重新配对"]
                if severity == "high"
                else ["更换电池"] if battery <= 10
                else ["添加中继设备"] if signal <= -90
                else ["等待自动恢复，如持续离线则手动检查"]
            ),
        }

    # ---- 门磁告警规则 -----------------------------------------------------

    def _analyze_contact(self, ctx: AlertContext) -> Dict[str, Any]:
        anomaly = ctx.anomaly_score
        behavior = self._get_behavior_activity(ctx)
        similar_count = self._count_recent_similar_events(ctx)

        is_false_alarm = False
        false_reason = None
        if behavior in ("coming_home", "leaving", "entering", "exiting"):
            is_false_alarm = True
            false_reason = f"行为分析显示正常出入: {behavior}"
        elif anomaly < self._ANOMALY_MEDIUM and similar_count <= 2:
            is_false_alarm = True
            false_reason = "低频告警且异常评分低，属于正常开关门"

        if anomaly >= self._ANOMALY_HIGH and behavior == "sleeping":
            cause = "深夜时段门磁触发，ML 异常评分高，可能存在非法入侵"
            confidence = 0.90
            severity = "high"
            urgency = "high"
        elif anomaly >= self._ANOMALY_HIGH and behavior == "away":
            cause = "家中无人时门磁触发，可能存在非法入侵"
            confidence = 0.90
            severity = "critical"
            urgency = "critical"
        elif is_false_alarm:
            cause = f"正常出入导致门磁触发: {behavior}"
            confidence = 0.85
            severity = "low"
            urgency = "low"
        else:
            cause = "门磁触发，需确认是正常出入还是安全事件"
            confidence = 0.45
            severity = "medium"
            urgency = "medium"

        return {
            "root_cause_analysis": {
                "primary_cause": cause,
                "confidence": confidence,
                "contributing_factors": [f"当前活动: {behavior}", f"24h 同类事件: {similar_count} 次"],
                "evidence": self._build_evidence_list(ctx, f"行为分析: {behavior}"),
                "is_false_alarm": is_false_alarm,
                "false_alarm_reason": false_reason,
            },
            "impact_assessment": {
                "severity": severity,
                "affected_rooms": [ctx.room_name],
                "affected_devices": [ctx.device_name],
                "potential_consequences": (
                    ["可能存在非法入侵", "财产安全受威胁", "人身安全风险"]
                    if severity in ("critical", "high")
                    else ["无安全威胁"]
                ),
                "estimated_scope": "localized",
            },
            "remediation_steps": (
                [
                    {"step": 1, "action": "立即检查是否有陌生人进入", "urgency": "immediate",
                     "expected_outcome": "确认安全状况", "requires_manual_intervention": True},
                    {"step": 2, "action": "如确认非法入侵，立即报警并确保自身安全", "urgency": "immediate",
                     "expected_outcome": "保障人身安全", "requires_manual_intervention": True},
                ] if severity in ("critical", "high")
                else [
                    {"step": 1, "action": "确认门是否正常关闭", "urgency": "short_term",
                     "expected_outcome": "确认门状态", "requires_manual_intervention": True},
                ]
            ),
            "urgency_level": urgency,
            "recommended_actions": (
                ["立即报警", "确认自身安全", "不要直接对抗"]
                if severity == "critical"
                else ["检查周边安全", "确认门窗是否锁好"] if severity == "high"
                else ["确认门已关好"]
            ),
        }

    # ---- 移动/人体检测告警规则 -------------------------------------------------

    def _analyze_motion(self, ctx: AlertContext) -> Dict[str, Any]:
        anomaly = ctx.anomaly_score
        behavior = self._get_behavior_activity(ctx)

        is_false_alarm = behavior != "away"
        false_reason = f"行为分析显示人员在室内 ({behavior})，移动检测正常" if is_false_alarm else None

        if behavior == "away" and anomaly >= self._ANOMALY_HIGH:
            cause = "家中无人但检测到移动，可能存在非法入侵"
            confidence = 0.90
            severity = "critical"
            urgency = "critical"
        elif behavior == "away" and anomaly >= self._ANOMALY_MEDIUM:
            cause = "家中无人时检测到移动，可能是宠物活动或非法入侵"
            confidence = 0.70
            severity = "high"
            urgency = "high"
        elif behavior == "sleeping" and ctx.anomaly_score >= self._ANOMALY_HIGH:
            cause = "深夜检测到移动且异常评分高，可能存在安全风险"
            confidence = 0.80
            severity = "high"
            urgency = "high"
        elif is_false_alarm:
            cause = f"人员在室内活动 ({behavior})，移动检测正常"
            confidence = 0.95
            severity = "low"
            urgency = "low"
        else:
            cause = "检测到移动，需确认来源"
            confidence = 0.50
            severity = "medium"
            urgency = "medium"

        return {
            "root_cause_analysis": {
                "primary_cause": cause,
                "confidence": confidence,
                "contributing_factors": [f"当前活动: {behavior}", f"异常评分: {anomaly:.2f}"],
                "evidence": self._build_evidence_list(ctx, f"行为: {behavior}"),
                "is_false_alarm": is_false_alarm,
                "false_alarm_reason": false_reason,
            },
            "impact_assessment": {
                "severity": severity,
                "affected_rooms": [ctx.room_name],
                "affected_devices": [ctx.device_name],
                "potential_consequences": (
                    ["可能非法入侵"] if severity in ("critical", "high")
                    else ["无安全威胁，正常活动"]
                ),
                "estimated_scope": "localized",
            },
            "remediation_steps": (
                [
                    {"step": 1, "action": "立即通过摄像头或远程查看确认情况", "urgency": "immediate",
                     "expected_outcome": "确认是否有非法入侵", "requires_manual_intervention": True},
                    {"step": 2, "action": "如确认入侵，立即报警", "urgency": "immediate",
                     "expected_outcome": "保障安全", "requires_manual_intervention": True},
                ] if severity in ("critical", "high")
                else [{"step": 1, "action": "正常活动，无需额外处理", "urgency": "short_term",
                        "expected_outcome": "无需处理", "requires_manual_intervention": False}]
            ),
            "urgency_level": urgency,
            "recommended_actions": (
                ["远程查看家中情况", "必要时报警"] if severity in ("critical", "high")
                else ["无需处理"]
            ),
        }

    # ---- 通用/未知告警规则 -------------------------------------------------

    def _analyze_generic(self, ctx: AlertContext) -> Dict[str, Any]:
        anomaly = ctx.anomaly_score
        behavior = self._get_behavior_activity(ctx)

        if anomaly >= self._ANOMALY_HIGH:
            cause = f"告警类型 {ctx.event_type} 配合 ML 异常高分，需关注"
            confidence = 0.75
            severity = "high"
            urgency = "high"
        elif anomaly >= self._ANOMALY_MEDIUM:
            cause = f"告警类型 {ctx.event_type}，ML 异常中等评分"
            confidence = 0.55
            severity = "medium"
            urgency = "medium"
        else:
            cause = f"告警类型 {ctx.event_type}，ML 异常低分，可能是正常波动"
            confidence = 0.40
            severity = "low"
            urgency = "low"

        return {
            "root_cause_analysis": {
                "primary_cause": cause,
                "confidence": confidence,
                "contributing_factors": [f"异常评分: {anomaly:.2f}", f"行为: {behavior}"],
                "evidence": self._build_evidence_list(ctx),
                "is_false_alarm": anomaly < self._ANOMALY_MEDIUM,
                "false_alarm_reason": "ML 评分低于阈值，疑似误报" if anomaly < self._ANOMALY_MEDIUM else None,
            },
            "impact_assessment": {
                "severity": severity,
                "affected_rooms": [ctx.room_name],
                "affected_devices": [ctx.device_name],
                "potential_consequences": ["需要人工评估"],
                "estimated_scope": "localized",
            },
            "remediation_steps": [
                {"step": 1, "action": f"检查 {ctx.device_name} 的告警详情", "urgency": "short_term",
                 "expected_outcome": "确认告警具体原因", "requires_manual_intervention": True},
            ],
            "urgency_level": urgency,
            "recommended_actions": ["查看告警详情", "确认是否需要进一步处理"],
        }

    # ---- 数据库存储 -------------------------------------------------------

    def _store_result(self, result: AlertAnalysisResult) -> None:
        """将分析结果存入数据库。"""
        try:
            with self._db.get_connection() as conn:
                conn.execute(
                    f"""INSERT INTO {self.DEFAULT_TABLE}
                        (analysis_id, event_id, alert_type,
                         root_cause, impact, remediation,
                         urgency_level, recommended_actions,
                         raw_response, model_used, success, created_at_ms)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.analysis_id,
                        result.event_id,
                        result.alert_type,
                        json.dumps(result.root_cause_analysis, ensure_ascii=False),
                        json.dumps(result.impact_assessment, ensure_ascii=False),
                        json.dumps(result.remediation_steps, ensure_ascii=False),
                        result.urgency_level,
                        json.dumps(result.recommended_actions, ensure_ascii=False),
                        json.dumps({"analysis_mode": result.analysis_mode}, ensure_ascii=False),
                        "rule_engine",
                        1 if result.success else 0,
                        result.created_at_ms,
                    ),
                )
                conn.commit()
                logger.info("[AlertAnalyzer] Stored analysis %s to DB", result.analysis_id)
        except Exception as e:
            logger.error("[AlertAnalyzer] Failed to store analysis: %s", e, exc_info=True)

    # ---- 查询方法 ---------------------------------------------------------

    def get_by_id(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._db.get_connection() as conn:
                row = conn.execute(
                    f"SELECT * FROM {self.DEFAULT_TABLE} WHERE analysis_id = ?",
                    (analysis_id,),
                ).fetchone()
                if row:
                    return self._row_to_dict(row)
        except Exception as e:
            logger.error("[AlertAnalyzer] Query by id failed: %s", e, exc_info=True)
        return None

    def get_by_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._db.get_connection() as conn:
                row = conn.execute(
                    f"SELECT * FROM {self.DEFAULT_TABLE} WHERE event_id = ? "
                    "ORDER BY created_at_ms DESC LIMIT 1",
                    (event_id,),
                ).fetchone()
                if row:
                    return self._row_to_dict(row)
        except Exception as e:
            logger.error("[AlertAnalyzer] Query by event failed: %s", e, exc_info=True)
        return None

    def list_analyses(
        self,
        page: int = 1,
        page_size: int = 20,
        alert_type: Optional[str] = None,
        urgency_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            with self._db.get_connection() as conn:
                where_parts = ["success = 1"]
                params: List[Any] = []
                if alert_type:
                    where_parts.append("alert_type = ?")
                    params.append(alert_type)
                if urgency_level:
                    where_parts.append("urgency_level = ?")
                    params.append(urgency_level)
                where = " WHERE " + " AND ".join(where_parts)

                total_row = conn.execute(
                    f"SELECT COUNT(*) FROM {self.DEFAULT_TABLE}{where}",
                    tuple(params),
                ).fetchone()
                total = total_row[0] if total_row else 0

                offset = (page - 1) * page_size
                rows = conn.execute(
                    f"SELECT * FROM {self.DEFAULT_TABLE}{where} "
                    "ORDER BY created_at_ms DESC LIMIT ? OFFSET ?",
                    (*params, page_size, offset),
                ).fetchall()

                items = [self._row_to_dict(r) for r in rows]
                total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

                return {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "items": items,
                }
        except Exception as e:
            logger.error("[AlertAnalyzer] List analyses failed: %s", e, exc_info=True)
            return {"total": 0, "page": page, "page_size": page_size, "total_pages": 1, "items": []}

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        keys = [
            "id", "analysis_id", "event_id", "alert_type",
            "root_cause", "impact", "remediation",
            "urgency_level", "recommended_actions",
            "raw_response", "model_used", "success", "created_at_ms", "created_at",
        ]
        result = dict(zip(keys, row))
        for field in ("root_cause", "impact", "remediation", "recommended_actions", "raw_response"):
            val = result.get(field)
            if isinstance(val, str):
                try:
                    result[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    result[field] = val
        return result


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_alert_analyzer: Optional[AlertAnalyzer] = None


def get_alert_analyzer() -> AlertAnalyzer:
    global _alert_analyzer
    if _alert_analyzer is None:
        raise RuntimeError("AlertAnalyzer not initialized. Call init_alert_analyzer() first.")
    return _alert_analyzer


def init_alert_analyzer(db, llm_client=None, decision_engine=None) -> AlertAnalyzer:
    global _alert_analyzer
    _alert_analyzer = AlertAnalyzer(db=db)
    logger.info("[AlertAnalyzer] Global singleton initialized (rule-engine mode)")
    return _alert_analyzer
