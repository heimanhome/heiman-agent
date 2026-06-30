"""``heiman-cli task`` 子命令组：任务管理。"""

from __future__ import annotations

import sys
import json

import click

from heiman_cli.client import api_get, api_post, api_put, api_delete
from heiman_cli.output import print_result


@click.group("task")
def task_group():
    """任务管理：list / get / create / delete / pause / resume / progress / session / event。"""


@task_group.command("list")
@click.option("--pretty", is_flag=True)
@click.option("--status", type=click.Choice(["active", "paused"]), help="按状态过滤")
def task_list(pretty, status):
    """列出所有任务。"""
    params = {}
    if status:
        params["status"] = status
    result = api_get("/api/tasks", params=params)
    print_result({"tasks": result}, pretty)


@task_group.command("get")
@click.argument("task_id")
@click.option("--pretty", is_flag=True)
def task_get(task_id, pretty):
    """获取任务详情。"""
    result = api_get(f"/api/tasks/{task_id}")
    print_result(result, pretty)


@task_group.command("create")
@click.option("--description", required=True, help="任务描述")
@click.option("--kind", required=True, type=click.Choice(["progress", "duration", "event"]), help="任务类型")
@click.option("--target", type=int, help="目标值（progress/duration 必填）")
@click.option("--unit", default="", help="单位（progress 必填）")
@click.option("--window", type=click.Choice(["day", "week", "month", "longterm"]), help="时间窗口（progress 必填）")
@click.option("--pretty", is_flag=True)
def task_create(description, kind, target, unit, window, pretty):
    """创建任务。"""
    body = {
        "description": description,
        "kind": kind,
    }
    if kind == "progress":
        if target is None or not unit or not window:
            print(
                json.dumps(
                    {"error": "progress 类型任务必须提供 --target, --unit, --window"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        body["target"] = target
        body["unit"] = unit
        body["window"] = window
    elif kind == "duration":
        if target is None:
            print(
                json.dumps({"error": "duration 类型任务必须提供 --target（分钟）"}, ensure_ascii=False),
                file=sys.stderr,
            )
            sys.exit(1)
        body["target_minutes"] = target

    result = api_post("/api/tasks", body=body)
    print_result(result, pretty)


@task_group.command("delete")
@click.argument("task_id")
@click.option("--pretty", is_flag=True)
@click.confirmation_option(prompt="确认删除该任务?")
def task_delete(task_id, pretty):
    """删除任务。"""
    result = api_delete(f"/api/tasks/{task_id}")
    print_result(result, pretty)


@task_group.command("pause")
@click.argument("task_id")
@click.option("--pretty", is_flag=True)
def task_pause(task_id, pretty):
    """暂停任务。"""
    result = api_post(f"/api/tasks/{task_id}/pause")
    print_result(result, pretty)


@task_group.command("resume")
@click.argument("task_id")
@click.option("--pretty", is_flag=True)
def task_resume(task_id, pretty):
    """恢复任务。"""
    result = api_post(f"/api/tasks/{task_id}/resume")
    print_result(result, pretty)


@task_group.command("progress")
@click.argument("task_id")
@click.option("--delta", type=int, required=True, help="递增步长（可为负）")
@click.option("--pretty", is_flag=True)
def task_progress(task_id, delta, pretty):
    """进度型任务：递增进度。"""
    result = api_post(f"/api/tasks/{task_id}/progress/increment", body={"delta": delta})
    print_result(result, pretty)


@task_group.command("session")
@click.argument("task_id")
@click.argument("action", type=click.Choice(["start", "end"]))
@click.option("--pretty", is_flag=True)
def task_session(task_id, action, pretty):
    """时长型任务：开始或结束会话。"""
    result = api_post(f"/api/tasks/{task_id}/session/{action}")
    print_result(result, pretty)


@task_group.command("event")
@click.argument("task_id")
@click.option("--description", required=True, help="事件描述")
@click.option("--pretty", is_flag=True)
def task_event(task_id, description, pretty):
    """事件型任务：追加事件。"""
    result = api_post(f"/api/tasks/{task_id}/event/append", body={"description": description})
    print_result(result, pretty)


@task_group.command("link")
@click.argument("task_id")
@click.option("--kind", required=True, type=click.Choice(["rule", "cron"]), help="关联类型")
@click.option("--ref", required=True, help="关联引用（rule_id 或 cron 表达式）")
@click.option("--pretty", is_flag=True)
def task_link(task_id, kind, ref, pretty):
    """添加任务关联。"""
    result = api_post(
        f"/api/tasks/{task_id}/links",
        body={"link_kind": kind, "link_ref": ref},
    )
    print_result(result, pretty)
