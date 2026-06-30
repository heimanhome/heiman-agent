"""ai 命令组：AI智能分析服务。"""

from __future__ import annotations

import click

from heiman_cli.client import api_get
from heiman_cli.output import print_result


@click.group("ai")
def ai_group():
    """AI智能分析：异常检测、舒适度评估、行为识别、智能建议。"""


@ai_group.command("analyze")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", help="指定家庭ID")
def ai_analyze(pretty, home_id):
    """全面分析家庭状态，包括异常检测、舒适度评估、活动识别和智能建议。"""
    params = {}
    if home_id:
        params["home_id"] = home_id
    data = api_get("/api/ai/analyze", params=params)
    print_result(data, pretty)


@ai_group.command("anomaly")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", help="指定家庭ID")
def ai_anomaly(pretty, home_id):
    """检测设备离线、环境异常、行为异常等问题。"""
    params = {}
    if home_id:
        params["home_id"] = home_id
    data = api_get("/api/ai/anomaly", params=params)
    print_result(data, pretty)


@ai_group.command("comfort")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", help="指定家庭ID")
@click.option("--temperature", type=float, help="温度值")
@click.option("--humidity", type=float, help="湿度值")
@click.option("--co2", type=int, help="CO2浓度")
@click.option("--pm25", type=int, help="PM2.5浓度")
@click.option("--hcho", type=float, help="甲醛浓度")
def ai_comfort(pretty, home_id, temperature, humidity, co2, pm25, hcho):
    """评估室内环境舒适度。"""
    params = {}
    if home_id:
        params["home_id"] = home_id
    if temperature is not None:
        params["temperature"] = temperature
    if humidity is not None:
        params["humidity"] = humidity
    if co2 is not None:
        params["co2"] = co2
    if pm25 is not None:
        params["pm25"] = pm25
    if hcho is not None:
        params["hcho"] = hcho
    data = api_get("/api/ai/comfort", params=params)
    print_result(data, pretty)


@ai_group.command("activity")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", help="指定家庭ID")
@click.option("--room-id", help="指定房间ID")
def ai_activity(pretty, home_id, room_id):
    """识别用户当前活动状态。"""
    params = {}
    if home_id:
        params["home_id"] = home_id
    if room_id:
        params["room_id"] = room_id
    data = api_get("/api/ai/activity", params=params)
    print_result(data, pretty)


@ai_group.command("routine")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", help="指定家庭ID")
@click.option("--date", help="指定日期 (YYYY-MM-DD)")
def ai_routine(pretty, home_id, date):
    """获取用户日常作息规律。"""
    params = {}
    if home_id:
        params["home_id"] = home_id
    if date:
        params["date"] = date
    data = api_get("/api/ai/activity/routine", params=params)
    print_result(data, pretty)


@ai_group.command("suggest")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", help="指定家庭ID")
def ai_suggest(pretty, home_id):
    """获取基于当前状态的智能建议。"""
    params = {}
    if home_id:
        params["home_id"] = home_id
    data = api_get("/api/ai/suggest", params=params)
    print_result(data, pretty)


@ai_group.command("summary")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", help="指定家庭ID")
def ai_summary(pretty, home_id):
    """生成最近事件的自然语言摘要。"""
    params = {}
    if home_id:
        params["home_id"] = home_id
    data = api_get("/api/ai/summary", params=params)
    print_result(data, pretty)


@ai_group.command("health")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def ai_health(pretty):
    """检查AI服务健康状态。"""
    data = api_get("/api/ai/health")
    print_result(data, pretty)


@ai_group.command("habits")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--user-id", default="default", help="指定用户ID")
def ai_habits(pretty, user_id):
    """获取用户习惯数据。"""
    params = {"user_id": user_id}
    data = api_get("/api/ai/habits", params=params)
    print_result(data, pretty)


@ai_group.command("suggestions")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--user-id", default="default", help="指定用户ID")
@click.option("--home-id", default="default", help="指定家庭ID")
def ai_suggestions(pretty, user_id, home_id):
    """获取基于用户习惯的智能建议。"""
    params = {"user_id": user_id, "home_id": home_id}
    data = api_get("/api/ai/suggestions", params=params)
    print_result(data, pretty)


@ai_group.command("perception")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", default="default", help="指定家庭ID")
@click.option("--limit", default=20, help="返回事件数量")
def ai_perception(pretty, home_id, limit):
    """获取感知事件数据。"""
    params = {"home_id": home_id, "limit": limit}
    data = api_get("/api/ai/perception/events", params=params)
    print_result(data, pretty)


@ai_group.command("identity")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", default="default", help="指定家庭ID")
def ai_identity(pretty, home_id):
    """获取身份识别信息。"""
    params = {"home_id": home_id}
    data = api_get("/api/ai/perception/identity", params=params)
    print_result(data, pretty)


@ai_group.command("fused")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", default="default", help="指定家庭ID")
def ai_fused(pretty, home_id):
    """融合多模态感知数据分析。"""
    params = {"home_id": home_id}
    data = api_get("/api/ai/analyze/fused", params=params)
    print_result(data, pretty)


@ai_group.command("respond")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
@click.option("--home-id", default="default", help="指定家庭ID")
@click.argument("query")
def ai_respond(pretty, home_id, query):
    """基于场景上下文的自然语言响应。"""
    params = {"home_id": home_id, "query": query}
    data = api_get("/api/ai/intent/respond", params=params)
    print_result(data, pretty)
