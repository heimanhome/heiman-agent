"""``heiman-cli auth`` 子命令组：认证管理（OAuth2）。"""

from __future__ import annotations

import json
import sys
import webbrowser

import click

from heiman_cli.client import api_get, api_post
from heiman_cli.config import heiman_home, load_config
from heiman_cli.output import print_result


@click.group("auth")
def auth_group():
    """认证管理：login / logout / token / refresh / revoke。"""


@auth_group.command("login")
@click.option("--browser/--no-browser", default=True, help="是否自动打开浏览器")
@click.option("--pretty", is_flag=True)
def auth_login(browser, pretty):
    """OAuth2 登录。"""
    cfg = load_config()
    server_url = cfg["server"]["url"]
    login_url = f"{server_url.rstrip('/')}/api/auth/login"

    if browser:
        click.echo(f"Opening browser: {login_url}")
        webbrowser.open(login_url)
    else:
        click.echo(f"请访问以下 URL 完成登录:\n{login_url}")

    try:
        result = api_get("/api/auth/token")
        if result.get("access_token"):
            print_result({"message": "登录成功", "token": result}, pretty)
        else:
            print_result({"message": "等待用户完成认证..."}, pretty)
    except Exception as e:
        print(json.dumps({"error": f"login failed: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@auth_group.command("logout")
@click.option("--pretty", is_flag=True)
def auth_logout(pretty):
    """登出并清除本地 token。"""
    try:
        result = api_post("/api/auth/logout")
        print_result(result, pretty)
    except Exception as e:
        print(json.dumps({"error": f"logout failed: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@auth_group.command("token")
@click.option("--pretty", is_flag=True)
@click.option(
    "--value-only",
    is_flag=True,
    help="仅输出 access_token 值本身(裸文本), 方便脚本使用",
)
def auth_token(pretty, value_only):
    """获取当前 token 信息。"""
    result = api_get("/api/auth/token")
    if value_only:
        token = result.get("access_token", "")
        print(token)
        return
    print_result(result, pretty)


@auth_group.command("refresh")
@click.option("--pretty", is_flag=True)
def auth_refresh(pretty):
    """刷新 access token。"""
    result = api_post("/api/auth/refresh")
    print_result(result, pretty)


@auth_group.command("revoke")
@click.option("--all", is_flag=True, help="撤销所有 token")
@click.option("--pretty", is_flag=True)
def auth_revoke(all, pretty):
    """撤销当前或所有 token。"""
    try:
        if all:
            result = api_post("/api/auth/revoke/all")
        else:
            result = api_post("/api/auth/revoke")
        print_result(result, pretty)
    except Exception as e:
        print(json.dumps({"error": f"revoke failed: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@auth_group.command("status")
@click.option("--pretty", is_flag=True)
def auth_status(pretty):
    """检查认证状态。"""
    try:
        result = api_get("/api/auth/status")
        print_result(result, pretty)
    except Exception as e:
        print(json.dumps({
            "authenticated": False,
            "error": str(e),
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)