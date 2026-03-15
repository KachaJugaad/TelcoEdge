"""Smoke tests for RAN-Intel live map platform."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the src package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ran_intel.app import app  # noqa: E402

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_sites_returns_six():
    resp = client.get("/api/sites")
    assert resp.status_code == 200
    sites = resp.json()
    assert isinstance(sites, list)
    assert len(sites) == 6


def test_sites_have_required_fields():
    resp = client.get("/api/sites")
    sites = resp.json()
    required = {"name", "lat", "lon", "terrain_type"}
    for site in sites:
        assert required.issubset(site.keys()), f"Missing fields in {site}"


def test_sites_include_bc():
    resp = client.get("/api/sites")
    sites = resp.json()
    bc_sites = [s for s in sites if "BC" in s["name"]]
    assert len(bc_sites) >= 1, "Expected at least one British Columbia site"


def test_radar_returns_wms_url():
    resp = client.get("/api/weather/radar")
    assert resp.status_code == 200
    data = resp.json()
    assert "wms_url" in data
    assert "geo.weather.gc.ca" in data["wms_url"]


def test_index_serves_leaflet_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "leaflet" in resp.text.lower()
