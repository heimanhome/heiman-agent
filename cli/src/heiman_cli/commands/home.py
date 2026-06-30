"""家庭管理命令。"""

import click

from heiman_cli.client import api_get
from heiman_cli.output import print_result


@click.group("home")
def home_group():
    """家庭管理。"""


@home_group.command("list")
@click.option("--pretty", is_flag=True)
def list_cmd(pretty):
    """列出所有家庭。"""
    result = api_get("/api/homes")
    print_result({"homes": result}, pretty)


@home_group.command("get")
@click.argument("home_id")
@click.option("--pretty", is_flag=True)
def get_cmd(home_id, pretty):
    """获取家庭详情。"""
    result = api_get(f"/api/homes/{home_id}")
    print_result(result, pretty)