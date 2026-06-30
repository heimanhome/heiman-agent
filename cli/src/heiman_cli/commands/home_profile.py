"""home-profile 命令组：管理家庭档案。"""

from __future__ import annotations

import click

from heiman_cli.client import api_get, api_post
from heiman_cli.output import print_result


@click.group("home-profile")
def home_profile_group():
    """家庭档案：管理家庭成员画像和候选条目。"""


@home_profile_group.command("entries")
@click.option("--target", type=click.Choice(["profile", "candidates", "both"]), default="both", show_default=True, help="查询目标")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def home_profile_entries(target, pretty):
    """获取家庭档案条目列表。"""
    data = api_get(f"/api/home-profile/entries?target={target}")
    print_result(data, pretty)


@home_profile_group.command("rendered")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def home_profile_rendered(pretty):
    """获取渲染后的 Markdown 内容。"""
    data = api_get("/api/home-profile/rendered")
    print_result(data, pretty)


@home_profile_group.command("write-profile")
@click.argument("entries", type=str)
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def home_profile_write_profile(entries, pretty):
    """写入正式档案条目（JSON 字符串）。"""
    import json
    try:
        entries_data = json.loads(entries)
    except json.JSONDecodeError as e:
        raise click.BadParameter(f"Invalid JSON: {e}")
    data = api_post("/api/home-profile/profile:write", {"entries": entries_data})
    print_result(data, pretty)


@home_profile_group.command("write-candidates")
@click.argument("candidates", type=str)
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def home_profile_write_candidates(candidates, pretty):
    """写入候选条目（JSON 字符串）。"""
    import json
    try:
        candidates_data = json.loads(candidates)
    except json.JSONDecodeError as e:
        raise click.BadParameter(f"Invalid JSON: {e}")
    data = api_post("/api/home-profile/candidates:write", {"candidates": candidates_data})
    print_result(data, pretty)


@home_profile_group.command("commit")
@click.argument("entry_ids", type=str)
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def home_profile_commit(entry_ids, pretty):
    """提交候选条目到正式档案。"""
    import json
    try:
        ids = json.loads(entry_ids)
    except json.JSONDecodeError:
        ids = entry_ids.split(",")
    data = api_post("/api/home-profile/commit", {"entry_ids": ids})
    print_result(data, pretty)


@home_profile_group.command("reset")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def home_profile_reset(pretty):
    """重置家庭档案。"""
    data = api_post("/api/home-profile/reset", {})
    print_result(data, pretty)