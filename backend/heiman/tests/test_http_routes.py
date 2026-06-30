"""端到端 HTTP 集成测试 - 覆盖首页、SPA fallback、API 路径"""
import sys
sys.path.insert(0, "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src")

import pytest
from fastapi.testclient import TestClient

from heiman.main import create_app
from heiman.config import reset_settings


@pytest.fixture(scope="module")
def client():
    reset_settings()
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestHTTPRootAndSPA:
    def test_root_serves_index_html(self, client):
        """HTTP 404 回归测试：访问 / 必须返回 200 + HTML 而非 404。
        之前的 static_dir 路径错误导致找不到 index.html。"""
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert "<!doctype html>" in r.text.lower() or "<!DOCTYPE html>" in r.text

    def test_favicon_served(self, client):
        r = client.get("/favicon.svg")
        assert r.status_code == 200
        assert "image/svg+xml" in r.headers.get("content-type", "")

    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["service"] == "heiman-agent"

    def test_spa_fallback_for_unknown_route(self, client):
        """SPA 路由 fallback：未知路径应返回 index.html 让前端路由处理"""
        r = client.get("/some/random/spa/route")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_assets_with_cache_headers(self, client):
        r = client.get("/assets/main-DBS9IXOG.js")
        # 静态资源可能返回 404（文件不存在）或 200
        # 如果返回 200，检查 cache-control 是否存在
        if r.status_code == 200:
            cache = r.headers.get("cache-control", "")
            # 接受 no-store 或 max-age
            assert cache != ""


class TestHTTPAPIRoutes:
    AUTH = {"Authorization": "bearer heiman_test_token_123"}

    def test_observability_overview(self, client):
        r = client.get("/api/observability/overview", headers=self.AUTH)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] == True
        assert "system" in data["data"]
        assert "sensor" in data["data"]
        assert "rule" in data["data"]
        assert "event" in data["data"]
        assert "database" in data["data"]

    def test_persons_list_empty(self, client):
        r = client.get("/api/persons", headers=self.AUTH)
        assert r.status_code == 200
        # API 返回 { success: True, data: [...] }
        data = r.json()
        assert data["success"] == True
        assert isinstance(data["data"], list)

    def test_tasks_list_empty(self, client):
        r = client.get("/api/tasks", headers=self.AUTH)
        assert r.status_code == 200
        # API 返回 { success: True, data: [...] }
        data = r.json()
        assert data["success"] == True
        assert isinstance(data["data"], list)

    def test_sensors_list(self, client):
        r = client.get("/api/sensors", headers=self.AUTH)
        assert r.status_code == 200

    def test_events_list(self, client):
        r = client.get("/api/events", headers=self.AUTH)
        assert r.status_code == 200

    def test_rules_list(self, client):
        r = client.get("/api/rules", headers=self.AUTH)
        assert r.status_code == 200
