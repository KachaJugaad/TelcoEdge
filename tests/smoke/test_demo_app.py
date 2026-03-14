"""Smoke tests for the WeatherRAN Phase 1 demo FastAPI app.

Tests the FastAPI endpoints using TestClient (no Docker needed).
Paired test for: deployment/demo-app/main.py

Run:
    pytest tests/smoke/test_demo_app.py -v
"""
import sys
from pathlib import Path

import pytest

# Add project root and demo-app to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_demo_app_path = str(PROJECT_ROOT / "deployment" / "demo-app")
if _demo_app_path not in sys.path:
    sys.path.insert(0, _demo_app_path)

# Import the demo app module — must happen after path setup
import main as demo_main  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def patched_client():
    """Create a test client with the demo app routes, no background loop.

    Builds a bare FastAPI app with the same routes but skips the lifespan
    context manager, so the background demo_loop never starts.
    """
    bare_app = FastAPI(title="test")
    for route in demo_main.app.routes:
        bare_app.routes.append(route)

    with TestClient(bare_app) as tc:
        yield tc


@pytest.fixture(autouse=True)
def reset_state():
    """Reset shared demo state before each test."""
    demo_main.state = demo_main.DemoState()
    demo_main._mock_idx = 0
    yield


# ---- /health ----

class TestHealthEndpoint:
    def test_health_returns_200(self, patched_client):
        resp = patched_client.get("/health")
        assert resp.status_code == 200

    def test_health_has_required_fields(self, patched_client):
        data = patched_client.get("/health").json()
        assert data["status"] == "ok"
        assert data["service"] == "weatherran-demo"
        assert "cycle_count" in data
        assert "last_update" in data


# ---- /metrics ----

class TestMetricsEndpoint:
    def test_metrics_returns_200(self, patched_client):
        assert patched_client.get("/metrics").status_code == 200

    def test_metrics_has_weather_section(self, patched_client):
        weather = patched_client.get("/metrics").json()["weather"]
        assert "rain_mm_per_hr" in weather
        assert "source" in weather

    def test_metrics_has_policy_section(self, patched_client):
        policy = patched_client.get("/metrics").json()["policy"]
        assert "mcs_baseline" in policy
        assert "mcs_adjusted" in policy
        assert "action" in policy

    def test_metrics_has_ber_section(self, patched_client):
        ber = patched_client.get("/metrics").json()["ber"]
        assert "baseline" in ber
        assert "adaptive" in ber
        assert "improvement_pct" in ber

    def test_metrics_has_meta_section(self, patched_client):
        meta = patched_client.get("/metrics").json()["meta"]
        assert "cycle_count" in meta
        assert "last_update" in meta


# ---- /action-log ----

class TestActionLogEndpoint:
    def test_action_log_returns_200(self, patched_client):
        assert patched_client.get("/action-log").status_code == 200

    def test_action_log_returns_list(self, patched_client):
        assert isinstance(patched_client.get("/action-log").json(), list)


# ---- / (root) ----

class TestRootEndpoint:
    def test_root_returns_200(self, patched_client):
        assert patched_client.get("/").status_code == 200

    def test_root_returns_ok(self, patched_client):
        assert patched_client.get("/").json()["status"] == "ok"


# ---- POST /search ----

class TestGrafanaSearchEndpoint:
    def test_search_returns_200(self, patched_client):
        assert patched_client.post("/search").status_code == 200

    def test_search_returns_metric_names(self, patched_client):
        data = patched_client.post("/search").json()
        assert isinstance(data, list)
        for name in ("weather", "policy", "ber", "action_log"):
            assert name in data


# ---- POST /query ----

class TestGrafanaQueryEndpoint:
    def test_query_weather(self, patched_client):
        data = patched_client.post("/query", json={
            "targets": [{"target": "weather"}]
        }).json()
        assert len(data) >= 1
        assert data[0]["target"] == "rain_mm_per_hr"

    def test_query_ber(self, patched_client):
        data = patched_client.post("/query", json={
            "targets": [{"target": "ber"}]
        }).json()
        targets = [d["target"] for d in data]
        assert "ber_baseline" in targets
        assert "ber_adaptive" in targets

    def test_query_policy(self, patched_client):
        data = patched_client.post("/query", json={
            "targets": [{"target": "policy"}]
        }).json()
        targets = [d["target"] for d in data]
        assert "mcs_baseline" in targets
        assert "mcs_adjusted" in targets

    def test_query_action_log_table(self, patched_client):
        demo_main.state.action_log = [{
            "time": "2026-03-14T00:00:00Z",
            "rain_mm_hr": 10.0,
            "source": "mock_fallback",
            "action": "rain_preemptive: 10.0 mm/hr > 5.0 threshold",
            "mcs_baseline": 15,
            "mcs_adjusted": 13,
            "ber_baseline": "1.00e-03",
            "ber_adaptive": "5.00e-04",
            "improvement_pct": "50.0%",
        }]
        data = patched_client.post("/query", json={
            "targets": [{"target": "action_log"}]
        }).json()
        assert len(data) >= 1
        table = data[0]
        assert table["type"] == "table"
        assert len(table["columns"]) == 9
        assert len(table["rows"]) == 1

    def test_query_empty_targets(self, patched_client):
        data = patched_client.post("/query", json={"targets": []}).json()
        assert data == []


# ---- BER estimation ----

class TestBEREstimation:
    def test_estimate_ber_low_path_loss(self):
        ber = demo_main.estimate_ber(80.0, 15)
        assert ber < 0.01

    def test_estimate_ber_high_path_loss(self):
        ber = demo_main.estimate_ber(160.0, 15)
        assert ber > 1e-10

    def test_lower_mcs_reduces_ber(self):
        ber_high = demo_main.estimate_ber(120.0, 20)
        ber_low = demo_main.estimate_ber(120.0, 5)
        assert ber_low <= ber_high

    def test_run_ber_comparison(self):
        result = demo_main.run_ber_comparison(
            rain_mm_per_hr=10.0,
            mcs_baseline=15,
            mcs_adjusted=13,
            n_runs=5,
            seed=42,
        )
        assert "ber_baseline" in result
        assert "ber_adaptive" in result
        assert "improvement_pct" in result
        assert result["n_runs"] == 5
        assert result["ber_adaptive"] <= result["ber_baseline"] + 1e-15


# ---- Mock weather fallback ----

class TestMockWeatherFallback:
    def test_mock_weather_cycles(self):
        seen = set()
        for _ in range(len(demo_main.MOCK_WEATHER_SCENARIOS)):
            wd = demo_main._get_mock_weather()
            seen.add(wd.rain_mm_per_hr)
        assert len(seen) > 1

    def test_mock_weather_wraps_around(self):
        n = len(demo_main.MOCK_WEATHER_SCENARIOS)
        results = [demo_main._get_mock_weather() for _ in range(n + 1)]
        assert results[0].rain_mm_per_hr == results[n].rain_mm_per_hr


# ---- State initialization ----

class TestDemoStateInitialization:
    def test_initial_state(self):
        fresh = demo_main.DemoState()
        assert fresh.rain_mm_per_hr == 0.0
        assert fresh.mcs_baseline == demo_main.BASELINE_MCS
        assert fresh.mcs_adjusted == demo_main.BASELINE_MCS
        assert fresh.policy_action == "no_action"
        assert fresh.action_log == []
        assert fresh.cycle_count == 0
