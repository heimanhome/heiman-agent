"""CLI 命令注册与基础结构测试。"""

import sys
sys.path.insert(0, "/Users/haiman/Documents/trae_projects/heiman-agent/cli/src")

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from heiman_cli.main import cli


class TestCLIRegistration:
    """确认 ANALYSIS_REPORT.md 中标记的缺失命令已注册。"""

    def test_all_required_commands_registered(self):
        required = {
            "auth", "device", "event", "rule", "health",
            "person", "task",  # P2 缺失项
            "config", "admin", "monitor", "doctor", "account", "service",
        }
        registered = set(cli.commands.keys())
        missing = required - registered
        assert not missing, f"Missing commands: {missing}"

    def test_person_group_has_subcommands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["person", "--help"])
        assert result.exit_code == 0
        for sub in ["list", "get", "create", "update", "delete"]:
            assert sub in result.output, f"person {sub} not in help"

    def test_task_group_has_subcommands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "--help"])
        assert result.exit_code == 0
        for sub in ["list", "get", "create", "delete", "pause", "resume", "progress", "session", "event", "link"]:
            assert sub in result.output, f"task {sub} not in help"

    def test_health_group_has_subcommands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "--help"])
        assert result.exit_code == 0
        for sub in ["check", "status"]:
            assert sub in result.output


class TestPersonCLIExecution:
    @patch("heiman_cli.commands.person.api_get")
    def test_person_list(self, mock_get):
        mock_get.return_value = [{"id": "p1", "name": "Alice"}]
        runner = CliRunner()
        result = runner.invoke(cli, ["person", "list"])
        assert result.exit_code == 0
        assert "Alice" in result.output
        mock_get.assert_called_once_with("/api/persons")

    @patch("heiman_cli.commands.person.api_post")
    def test_person_create(self, mock_post):
        mock_post.return_value = {"id": "p2", "name": "Bob", "role": "father"}
        runner = CliRunner()
        result = runner.invoke(cli, ["person", "create", "--name", "Bob", "--role", "father"])
        assert result.exit_code == 0
        mock_post.assert_called_once_with("/api/persons", body={"name": "Bob", "role": "father"})


class TestTaskCLIExecution:
    @patch("heiman_cli.commands.task.api_get")
    def test_task_list(self, mock_get):
        mock_get.return_value = []
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "list"])
        assert result.exit_code == 0
        mock_get.assert_called_once()

    @patch("heiman_cli.commands.task.api_post")
    def test_task_create_progress_missing_fields_fails(self, mock_post):
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "create", "--description", "daily steps", "--kind", "progress"])
        assert result.exit_code == 1
        assert "target" in result.output or "unit" in result.output
        mock_post.assert_not_called()

    @patch("heiman_cli.commands.task.api_post")
    def test_task_create_progress_success(self, mock_post):
        mock_post.return_value = {"task_id": "t1", "kind": "progress"}
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "task", "create",
                "--description", "daily steps",
                "--kind", "progress",
                "--target", "10000",
                "--unit", "steps",
                "--window", "day",
            ],
        )
        assert result.exit_code == 0
        body = mock_post.call_args.kwargs["body"]
        assert body["target"] == 10000
        assert body["unit"] == "steps"
        assert body["window"] == "day"

    @patch("heiman_cli.commands.task.api_post")
    def test_task_session_start(self, mock_post):
        mock_post.return_value = {"task_id": "t1", "status": "active"}
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "session", "t1", "start"])
        assert result.exit_code == 0
        mock_post.assert_called_once_with("/api/tasks/t1/session/start")
