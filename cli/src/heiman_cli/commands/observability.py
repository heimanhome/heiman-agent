"""observability 命令组：查看可观测性数据。"""

from __future__ import annotations

import click

from heiman_cli.client import api_get
from heiman_cli.output import print_result


@click.group("observability")
def observability_group():
    """可观测性：查看 traces、agent runs、events 等数据。"""


@observability_group.command("overview")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def observability_overview(pretty):
    """获取可观测性概览（系统、传感器、规则、事件、数据库指标）。"""
    data = api_get("/api/observability/overview")
    print_result(data, pretty)


@observability_group.command("traces")
@click.option("--limit", type=int, default=20, help="返回条数")
@click.option("--since", type=int, help="起始时间（Unix ms）")
@click.option("--until", type=int, help="结束时间（Unix ms）")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def observability_traces(limit, since, until, pretty):
    """获取 traces 列表。"""
    params = []
    if limit:
        params.append(f"limit={limit}")
    if since:
        params.append(f"since={since}")
    if until:
        params.append(f"until={until}")
    url = "/api/observability/traces"
    if params:
        url += "?" + "&".join(params)
    data = api_get(url)
    print_result(data, pretty)


@observability_group.command("trace")
@click.argument("trace_id")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def observability_trace(trace_id, pretty):
    """获取单个 trace 详情。"""
    data = api_get(f"/api/observability/traces/{trace_id}")
    print_result(data, pretty)


@observability_group.command("agent-runs")
@click.option("--limit", type=int, default=20, help="返回条数")
@click.option("--since", type=int, help="起始时间（Unix ms）")
@click.option("--until", type=int, help="结束时间（Unix ms）")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def observability_agent_runs(limit, since, until, pretty):
    """获取 agent runs 列表。"""
    params = []
    if limit:
        params.append(f"limit={limit}")
    if since:
        params.append(f"since={since}")
    if until:
        params.append(f"until={until}")
    url = "/api/observability/agent-runs"
    if params:
        url += "?" + "&".join(params)
    data = api_get(url)
    print_result(data, pretty)


@observability_group.command("agent-run")
@click.argument("run_id")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def observability_agent_run(run_id, pretty):
    """获取单个 agent run 详情。"""
    data = api_get(f"/api/observability/agent-runs/{run_id}")
    print_result(data, pretty)





@observability_group.command("stats")
@click.argument("name")
@click.option("--bucket", type=str, default="1h", help="时间桶")
@click.option("--since", type=int, help="起始时间（Unix ms）")
@click.option("--until", type=int, help="结束时间（Unix ms）")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def observability_stats(name, bucket, since, until, pretty):
    """获取统计数据（trace_count/agent_run_count/event_count/token_usage）。"""
    params = [f"bucket={bucket}"]
    if since:
        params.append(f"since={since}")
    if until:
        params.append(f"until={until}")
    url = f"/api/observability/stats/{name}?" + "&".join(params)
    data = api_get(url)
    print_result(data, pretty)


@observability_group.command("token-usage")
@click.option("--since", type=int, help="起始时间（Unix ms）")
@click.option("--until", type=int, help="结束时间（Unix ms）")
@click.option("--limit", type=int, help="返回条数")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def observability_token_usage(since, until, limit, pretty):
    """获取 token 使用记录。"""
    params = []
    if since:
        params.append(f"since={since}")
    if until:
        params.append(f"until={until}")
    if limit:
        params.append(f"limit={limit}")
    url = "/api/observability/token-usage"
    if params:
        url += "?" + "&".join(params)
    data = api_get(url)
    print_result(data, pretty)


@observability_group.command("token-usage-daily")
@click.option("--since", type=str, help="起始日期（YYYY-MM-DD）")
@click.option("--until", type=str, help="结束日期（YYYY-MM-DD）")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def observability_token_usage_daily(since, until, pretty):
    """获取 token 使用日统计。"""
    params = []
    if since:
        params.append(f"since={since}")
    if until:
        params.append(f"until={until}")
    url = "/api/observability/token-usage/daily"
    if params:
        url += "?" + "&".join(params)
    data = api_get(url)
    print_result(data, pretty)