"""设备管理命令。"""

import click

from heiman_cli.client import api_get, api_post
from heiman_cli.output import print_result


@click.group("device")
def device_group():
    """设备管理。"""


@device_group.command("list")
@click.option("--pretty", is_flag=True)
@click.option("--home-id", help="按家庭ID筛选设备")
def list_cmd(pretty, home_id):
    """列出所有设备。"""
    params = {}
    if home_id:
        params["home_id"] = home_id
    result = api_get("/api/devices", params=params)
    print_result({"devices": result}, pretty)


@device_group.command("get")
@click.argument("did")
@click.option("--pretty", is_flag=True)
@click.option("--home-id", help="家庭ID")
def get_cmd(did, pretty, home_id):
    """获取设备详情。"""
    params = {}
    if home_id:
        params["home_id"] = home_id
    result = api_get(f"/api/devices/{did}", params=params if params else None)
    print_result(result, pretty)


@device_group.command("history")
@click.argument("did")
@click.option("--pretty", is_flag=True)
def history_cmd(did, pretty):
    """获取设备历史数据。"""
    result = api_get(f"/api/sensors/{did}/history")
    print_result({"history": result}, pretty)


@device_group.command("refresh")
@click.option("--pretty", is_flag=True)
def refresh_cmd(pretty):
    """刷新设备列表缓存。"""
    result = api_post("/api/devices/refresh")
    print_result(result, pretty)


@device_group.command("toggle")
@click.argument("did")
@click.option("--pretty", is_flag=True)
def toggle_cmd(did, pretty):
    """切换设备开关状态。"""
    result = api_post(f"/api/devices/{did}/toggle")
    print_result(result, pretty)