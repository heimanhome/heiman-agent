"""健康检查命令。"""

import click

from heiman_cli.client import api_get
from heiman_cli.output import print_result


@click.group("health")
def health_group():
    """健康检查。"""


@health_group.command("check")
@click.option("--pretty", is_flag=True)
def health_check(pretty):
    """检查 Heiman Agent 健康状态。"""
    result = api_get("/health")
    print_result(result, pretty)


@health_group.command("status")
@click.option("--pretty", is_flag=True)
def health_status(pretty):
    """获取服务状态。"""
    result = api_get("/health")
    if result.get("status") == "healthy":
        print_result({"status": "healthy", "message": "Heiman Agent is running"}, pretty)
    else:
        print_result({"status": "unhealthy", "message": "Heiman Agent is not responding"}, pretty)
