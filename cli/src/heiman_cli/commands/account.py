"""``heiman-cli account`` 子命令组：账户管理。"""

from __future__ import annotations

import json
import sys

import click

from heiman_cli.client import api_get, api_post, api_delete
from heiman_cli.output import print_result


@click.group("account")
def account_group():
    """账户管理：login / logout / token / info / refresh。"""


@account_group.command("login")
@click.option("--pretty", is_flag=True)
def account_login(pretty):
    """OAuth2 登录。"""
    try:
        result = api_get("/api/auth/login")
        print_result(result, pretty)
    except Exception:
        print(json.dumps({
            "message": "请访问认证页面完成登录",
            "hint": "浏览器打开: http://localhost:1912/api/auth/login",
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@account_group.command("logout")
@click.option("--pretty", is_flag=True)
def account_logout(pretty):
    """登出并清除本地 token。"""
    try:
        result = api_post("/api/auth/logout")
        print_result(result, pretty)
    except Exception as e:
        print(json.dumps({"error": f"logout failed: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@account_group.command("token")
@click.option("--pretty", is_flag=True)
@click.option(
    "--value-only",
    is_flag=True,
    help="仅输出 token 值本身(裸文本), 方便脚本使用",
)
def account_token(pretty, value_only):
    """获取当前 token。"""
    result = api_get("/api/auth/token")
    if value_only:
        token = result.get("access_token", "")
        print(token)
        return
    print_result(result, pretty)


@account_group.command("refresh")
@click.option("--pretty", is_flag=True)
def account_refresh(pretty):
    """刷新 token。"""
    result = api_post("/api/auth/refresh")
    print_result(result, pretty)


@account_group.command("info")
@click.option("--pretty", is_flag=True)
def account_info(pretty):
    """获取当前账户信息。"""
    try:
        result = api_get("/api/auth/me")
        print_result(result, pretty)
    except Exception as e:
        print(json.dumps({"error": f"failed to get account info: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)