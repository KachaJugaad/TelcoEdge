"""RAN-Intel live map platform — FastAPI backend."""

from pathlib import Path

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="RAN-Intel", version="1.0.0")

TEMPLATE_PATH = Path(__file__).parent / "map_template.html"

DEMO_SITES = [
    {
        "name": "Saskatoon SK",
        "lat": 52.13,
        "lon": -106.67,
        "terrain_type": "prairie",
        "status": "active",
    },
    {
        "name": "Thunder Bay ON",
        "lat": 48.38,
        "lon": -89.25,
        "terrain_type": "boreal",
        "status": "active",
    },
    {
        "name": "Revelstoke BC",
        "lat": 51.00,
        "lon": -118.20,
        "terrain_type": "mountain",
        "status": "active",
    },
    {
        "name": "Whistler BC",
        "lat": 50.12,
        "lon": -122.95,
        "terrain_type": "mountain",
        "status": "active",
    },
    {
        "name": "Yellowknife NT",
        "lat": 62.45,
        "lon": -114.37,
        "terrain_type": "arctic",
        "status": "active",
    },
    {
        "name": "Iqaluit NU",
        "lat": 63.75,
        "lon": -68.52,
        "terrain_type": "arctic",
        "status": "active",
    },
]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/sites")
def get_sites():
    return DEMO_SITES


@app.get("/api/weather")
async def get_weather(bbox: str = Query(..., description="lon_min,lat_min,lon_max,lat_max")):
    """Proxy weather data from api.weather.gc.ca (anonymous, no API key)."""
    parts = [p.strip() for p in bbox.split(",")]
    if len(parts) != 4:
        return JSONResponse(status_code=400, content={"error": "bbox must have 4 values"})

    lon_min, lat_min, lon_max, lat_max = parts
    url = (
        "https://api.weather.gc.ca/collections/hydrometric-realtime/items"
        f"?bbox={lon_min},{lat_min},{lon_max},{lat_max}&limit=10&f=json"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})


@app.get("/api/weather/radar")
def get_radar():
    """Return MSC GeoMet WMS radar layer configuration."""
    return {
        "wms_url": "https://geo.weather.gc.ca/geomet",
        "layer": "RADAR_1KM_RDBR",
        "tile_url": (
            "https://geo.weather.gc.ca/geomet?"
            "SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
            "&LAYERS=RADAR_1KM_RDBR&CRS=EPSG:4326"
            "&BBOX={bbox}&WIDTH=800&HEIGHT=600&FORMAT=image/png"
        ),
        "format": "image/png",
        "transparent": True,
    }


@app.get("/", response_class=HTMLResponse)
def index():
    html = TEMPLATE_PATH.read_text()
    return HTMLResponse(content=html)
