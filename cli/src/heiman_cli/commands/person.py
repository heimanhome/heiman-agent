"""``heiman-cli person`` 子命令组：人员管理。"""

from __future__ import annotations

import sys
import json

import click

from heiman_cli.client import api_get, api_post, api_put, api_delete
from heiman_cli.output import print_result


@click.group("person")
def person_group():
    """人员管理：list / get / create / update / delete。"""


@person_group.command("list")
@click.option("--pretty", is_flag=True)
def person_list(pretty):
    """列出所有人员。"""
    result = api_get("/api/persons")
    print_result({"persons": result}, pretty)


@person_group.command("get")
@click.argument("person_id")
@click.option("--pretty", is_flag=True)
def person_get(person_id, pretty):
    """获取人员详情。"""
    result = api_get(f"/api/persons/{person_id}")
    print_result(result, pretty)


@person_group.command("create")
@click.option("--name", required=True, help="人员姓名")
@click.option("--role", default="", help="家庭角色（如 father/mother/child/grandpa）")
@click.option("--pretty", is_flag=True)
def person_create(name, role, pretty):
    """创建新人员。"""
    body = {"name": name, "role": role}
    result = api_post("/api/persons", body=body)
    print_result(result, pretty)


@person_group.command("update")
@click.argument("person_id")
@click.option("--name", help="新姓名")
@click.option("--role", help="新角色")
@click.option("--pretty", is_flag=True)
def person_update(person_id, name, role, pretty):
    """更新人员信息。"""
    updates = {}
    if name is not None:
        updates["name"] = name
    if role is not None:
        updates["role"] = role

    if not updates:
        print(json.dumps({"error": "至少需要提供一个更新字段"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    result = api_put(f"/api/persons/{person_id}", body=updates)
    print_result(result, pretty)


@person_group.command("delete")
@click.argument("person_id")
@click.option("--pretty", is_flag=True)
@click.confirmation_option(prompt="确认删除该人员?")
def person_delete(person_id, pretty):
    """删除人员。"""
    result = api_delete(f"/api/persons/{person_id}")
    print_result(result, pretty)
