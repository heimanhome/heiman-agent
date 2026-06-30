"""``heiman-cli event`` 子命令组：事件管理。"""

from __future__ import annotations

import json
import sys

import click

from heiman_cli.client import api_get, api_post, api_delete
from heiman_cli.output import print_result


@click.group("event")
def event_group():
    """事件管理：list / get / ack / ack-all / delete / stats。"""


@event_group.command("list")
@click.option("--pretty", is_flag=True)
@click.option("--type", "-t", help="按事件类型过滤")
@click.option("--sensor", "-s", help="按传感器 ID 过滤")
@click.option("--unack", is_flag=True, help="仅显示未确认事件")
@click.option("--limit", default=50, help="返回数量限制")
def event_list(pretty, type, sensor, unack, limit):
    """列出事件。"""
    params = {}
    if type:
        params["type"] = type
    if sensor:
        params["sensor_id"] = sensor
    if unack:
        params["unacknowledged"] = "true"
    if limit:
        params["limit"] = limit

    result = api_get("/api/events", params=params)
    print_result({"events": result}, pretty)


@event_group.command("get")
@click.argument("event_id")
@click.option("--pretty", is_flag=True)
def event_get(event_id, pretty):
    """获取事件详情。"""
    result = api_get(f"/api/events/{event_id}")
    print_result(result, pretty)


@event_group.command("ack")
@click.argument("event_id")
@click.option("--pretty", is_flag=True)
def event_ack(event_id, pretty):
    """确认单个事件。"""
    result = api_post(f"/api/events/{event_id}/acknowledge")
    print_result(result, pretty)


@event_group.command("ack-all")
@click.option("--type", "-t", help="按事件类型过滤")
@click.option("--pretty", is_flag=True)
def event_ack_all(type, pretty):
    """确认所有事件。"""
    params = {}
    if type:
        params["type"] = type
    result = api_post("/api/events/acknowledge", body=params)
    print_result(result, pretty)


@event_group.command("delete")
@click.argument("event_id")
@click.option("--pretty", is_flag=True)
def event_delete(event_id, pretty):
    """删除事件。"""
    result = api_delete(f"/api/events/{event_id}")
    print_result(result, pretty)


@event_group.command("stats")
@click.option(
    "--period",
    type=click.Choice(["today", "week", "month"]),
    default="today",
    show_default=True,
    help="统计周期",
)
@click.option("--pretty", is_flag=True)
def event_stats(period, pretty):
    """事件统计。"""
    result = api_get(f"/api/events/stats?period={period}")
    print_result(result, pretty)