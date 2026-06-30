"""``heiman-cli rule`` 子命令组：规则管理。"""

from __future__ import annotations

import json
import sys

import click

from heiman_cli.client import api_get, api_post, api_put, api_delete
from heiman_cli.output import print_result


@click.group("rule")
def rule_group():
    """规则管理：list / get / create / update / delete / enable / disable / test。"""


@rule_group.command("list")
@click.option("--pretty", is_flag=True)
@click.option("--enabled", type=bool, help="按启用状态过滤")
def rule_list(pretty, enabled):
    """列出所有规则。"""
    params = {}
    if enabled is not None:
        params["enabled"] = str(enabled).lower()
    result = api_get("/api/rules", params=params)
    print_result({"rules": result}, pretty)


@rule_group.command("get")
@click.argument("rule_id")
@click.option("--pretty", is_flag=True)
def rule_get(rule_id, pretty):
    """获取规则详情。"""
    result = api_get(f"/api/rules/{rule_id}")
    print_result(result, pretty)


@rule_group.command("create")
@click.option("--name", required=True, help="规则名称")
@click.option("--description", help="规则描述")
@click.option("--enabled/--disabled", default=True, help="是否启用")
@click.option("--cooldown", default=5, help="冷却时间(分钟)")
@click.option("--trigger", help="触发条件 JSON 字符串,例: '{\"did\":\"xxx\",\"property\":\"CONC\",\"operator\":\">=\",\"threshold\":120}'")
@click.option("--action-config", help="动作配置 JSON 字符串,例: '{\"title\":\"告警\",\"message\":\"浓度超标\"}'")
@click.option("--pretty", is_flag=True)
def rule_create(name, description, enabled, cooldown, trigger, action_config, pretty):
    """创建新规则。

    示例:
        heiman-cli rule create --name "CO告警" --cooldown 30 \\
            --trigger '{"did":"1943496617308098560","property":"CONC","operator":">=","threshold":120}' \\
            --action-config '{"title":"⚠️ CO告警","message":"浓度超标"}'
    """
    params = {
        "name": name,
        "description": description or "",
        "enabled": str(enabled).lower() if enabled is not None else "true",
        "cooldown_minutes": str(cooldown),
    }

    if trigger:
        params["trigger"] = trigger
    if action_config:
        params["action_config"] = action_config

    result = api_post("/api/rules", params=params)
    print_result(result, pretty)


@rule_group.command("update")
@click.argument("rule_id")
@click.option("--name", help="规则名称")
@click.option("--description", help="规则描述")
@click.option("--enabled/--disabled", help="是否启用")
@click.option("--cooldown", help="冷却时间(分钟)")
@click.option("--pretty", is_flag=True)
def rule_update(rule_id, name, description, enabled, cooldown, pretty):
    """更新规则。"""
    updates = {}
    if name is not None:
        updates["name"] = name
    if description is not None:
        updates["description"] = description
    if enabled is not None:
        updates["enabled"] = enabled
    if cooldown is not None:
        updates["cooldown_minutes"] = cooldown

    if not updates:
        print(json.dumps({"error": "至少需要提供一个更新字段"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    result = api_put(f"/api/rules/{rule_id}", body=updates)
    print_result(result, pretty)


@rule_group.command("delete")
@click.argument("rule_id")
@click.option("--pretty", is_flag=True)
def rule_delete(rule_id, pretty):
    """删除规则。"""
    result = api_delete(f"/api/rules/{rule_id}")
    print_result(result, pretty)


@rule_group.command("enable")
@click.argument("rule_id")
@click.option("--pretty", is_flag=True)
def rule_enable(rule_id, pretty):
    """启用规则。"""
    result = api_put(f"/api/rules/{rule_id}/enable")
    print_result(result, pretty)


@rule_group.command("disable")
@click.argument("rule_id")
@click.option("--pretty", is_flag=True)
def rule_disable(rule_id, pretty):
    """禁用规则。"""
    result = api_put(f"/api/rules/{rule_id}/disable")
    print_result(result, pretty)


@rule_group.command("test")
@click.argument("rule_id")
@click.option("--pretty", is_flag=True)
def rule_test(rule_id, pretty):
    """测试规则。"""
    result = api_post(f"/api/rules/{rule_id}/test")
    print_result(result, pretty)


@rule_group.command("stats")
@click.option("--pretty", is_flag=True)
def rule_stats(pretty):
    """规则执行统计。"""
    result = api_get("/api/rules/stats")
    print_result(result, pretty)