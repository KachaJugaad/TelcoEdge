/**
 * app.js — Signal Forecast Application Controller
 *
 * Wires together the postal lookup, tower data, weather adapter, and
 * signal model into a single-page app that runs entirely in the browser.
 *
 * Flow:
 *   1. User enters postal code
 *   2. Geocode → lat/lon (static lookup)
 *   3. Load tower data for all 3 carriers (static JSON)
 *   4. Find nearest towers per carrier
 *   5. Fetch weather forecast from MSC GeoMet (or use scenario)
 *   6. Run signal model for 24h forecast per carrier
 *   7. Render: carrier cards, charts, map
 */

// ============================================================================
// State
// ============================================================================

/** Application state — single source of truth */
const state = {
  lat: null,
  lon: null,
  fsa: null,
  towers: { bell: null, rogers: null, telus: null },
  towersLoaded: false,
  results: null,
  currentScenario: "live",  // "live" or weather scenario name
};

/** Carrier config */
const CARRIERS = [
  { key: "bell",   name: "Bell",   color: "#0066A4", file: "data/towers_bell.json" },
  { key: "rogers", name: "Rogers", color: "#DA291C", file: "data/towers_rogers.json" },
  { key: "telus",  name: "TELUS",  color: "#4B286D", file: "data/towers_telus.json" },
];

// ============================================================================
// Tower Data Loading
// ============================================================================

/**
 * Load tower data for all carriers (lazy — only loads once).
 * Files are pre-sorted by latitude for efficient binary search.
 */
async function loadTowers() {
  if (state.towersLoaded) return;

  setStatus("Loading tower data (32,756 sites)...", "loading");

  const promises = CARRIERS.map(async (c) => {
    try {
      const resp = await fetch(c.file);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      state.towers[c.key] = await resp.json();
    } catch (err) {
      console.error(`Failed to load ${c.name} towers:`, err);
      state.towers[c.key] = [];
    }
  });

  await Promise.all(promises);
  state.towersLoaded = true;

  const total = Object.values(state.towers).reduce((s, t) => s + t.length, 0);
  console.log(`Loaded ${total.toLocaleString()} tower sites`);
}

// ============================================================================
// Main Forecast Pipeline
// ============================================================================

/**
 * Run the full forecast pipeline for a postal code.
 *
 * @param {string} postalCode - Canadian postal code
 */
async function runForecast(postalCode) {
  // Step 1: Geocode
  const location = postalToCoords(postalCode);
  if (!location) {
    setStatus("Invalid postal code. Try format: K1A 0B1", "error");
    return;
  }

  state.lat = location.lat;
  state.lon = location.lon;
  state.fsa = location.fsa;

  setStatus(`Found ${location.fsa} (${location.accuracy}). Loading towers...`, "loading");

  // Step 2: Load towers
  await loadTowers();

  setStatus("Fetching weather forecast...", "loading");

  // Step 3: Get weather
  let weatherData;
  if (state.currentScenario === "live") {
    weatherData = await getWeatherForecast(state.lat, state.lon);
  } else {
    const hourly = generateScenario(state.currentScenario);
    weatherData = {
      hourly,
      source: `Scenario: ${state.currentScenario}`,
      temp_c: hourly[0].temp_c,
      condition: hourly[0].condition,
    };
  }

  setStatus("Computing signal predictions...", "loading");

  // Step 4: Find nearest towers and predict signal for each carrier
  const results = {};
  for (const carrier of CARRIERS) {
    const towers = state.towers[carrier.key];
    if (!towers || towers.length === 0) {
      results[carrier.key] = { carrier: carrier.name, noData: true };
      continue;
    }

    // Find nearest towers (top 5 within 50 km)
    const nearest = findNearestTowers(towers, state.lat, state.lon, 5, 50);

    if (nearest.length === 0) {
      results[carrier.key] = {
        carrier: carrier.name,
        noTowers: true,
        nearestAny: findNearestTowers(towers, state.lat, state.lon, 1, 500),
      };
      continue;
    }

    // Use the nearest tower for the primary forecast
    const bestTower = nearest[0].tower;
    const forecast = forecastSignal24h(bestTower, state.lat, state.lon, weatherData.hourly);

    // Current signal (hour 0)
    const current = forecast[0];

    results[carrier.key] = {
      carrier: carrier.name,
      color: carrier.color,
      tower: bestTower,
      distance_km: nearest[0].distance_km,
      nearestTowers: nearest.slice(0, 3),
      forecast,
      current,
      weather: weatherData,
    };
  }

  state.results = results;

  // Step 5: Render
  renderResults(results, weatherData);
  renderMap(results);
  setStatus("");
  document.querySelector(".results").classList.add("visible");

  // Update URL hash for sharing
  history.replaceState(null, "", `#${postalCode.replace(/\s/g, "")}`);
}

// ============================================================================
// Rendering
// ============================================================================

/**
 * Render forecast results into carrier cards with charts.
 */
function renderResults(results, weather) {
  // Location summary
  const summary = document.getElementById("location-summary");
  summary.innerHTML = `
    <h2>Signal Forecast for ${state.fsa}</h2>
    <div class="weather-info">
      ${weather.condition} | ${weather.temp_c}°C |
      Source: ${weather.source}
    </div>
  `;

  // Carrier cards
  const container = document.getElementById("carrier-cards");
  container.innerHTML = "";

  for (const carrier of CARRIERS) {
    const r = results[carrier.key];
    const card = document.createElement("div");
    card.className = `carrier-card ${carrier.key}`;

    if (r.noData || r.noTowers) {
      card.innerHTML = `
        <div class="card-header">
          <span class="carrier-name">${carrier.name}</span>
          <span class="signal-badge none">No Coverage</span>
        </div>
        <div class="card-body">
          <p style="color:var(--text-muted);text-align:center;padding:var(--space-lg) 0">
            ${r.noData ? "Tower data unavailable" :
              `No towers within 50 km. Nearest: ${
                r.nearestAny && r.nearestAny[0]
                  ? Math.round(r.nearestAny[0].distance_km) + " km"
                  : "Unknown"
              }`
            }
          </p>
        </div>
      `;
      container.appendChild(card);
      continue;
    }

    // Signal quality badge
    const current = r.current;

    card.innerHTML = `
      <div class="card-header">
        <span class="carrier-name">${carrier.name}</span>
        <span class="signal-badge ${current.quality}">${current.quality}</span>
      </div>
      <div class="card-body">
        <div class="signal-stats">
          <div class="stat">
            <div class="stat-value">${current.rsrp_dbm}</div>
            <div class="stat-label">RSRP (dBm)</div>
          </div>
          <div class="stat">
            <div class="stat-value">${r.distance_km.toFixed(1)}</div>
            <div class="stat-label">Distance (km)</div>
          </div>
          <div class="stat">
            <div class="stat-value">${current.freq_mhz}</div>
            <div class="stat-label">Band (MHz)</div>
          </div>
        </div>
        <div class="chart-container">
          <canvas id="chart-${carrier.key}"></canvas>
        </div>
        <div class="weather-breakdown">
          ${current.breakdown.rain_db > 0
            ? `<span class="wx-item">Rain: <span class="wx-val">-${current.breakdown.rain_db} dB</span></span>` : ""}
          ${current.breakdown.snow_db > 0
            ? `<span class="wx-item">Snow: <span class="wx-val">-${current.breakdown.snow_db} dB</span></span>` : ""}
          ${current.breakdown.fog_db > 0
            ? `<span class="wx-item">Fog: <span class="wx-val">-${current.breakdown.fog_db} dB</span></span>` : ""}
          ${current.breakdown.smoke_db > 0
            ? `<span class="wx-item">Smoke: <span class="wx-val">-${current.breakdown.smoke_db} dB</span></span>` : ""}
          ${current.breakdown.wind_db > 0
            ? `<span class="wx-item">Wind: <span class="wx-val">-${current.breakdown.wind_db} dB</span></span>` : ""}
          ${current.weather_loss_db === 0
            ? `<span class="wx-item">No weather impact</span>` : ""}
        </div>
      </div>
    `;

    container.appendChild(card);

    // Render chart (after card is in DOM)
    renderChart(carrier.key, carrier.color, r.forecast);
  }
}

/**
 * Render a 24-hour signal forecast chart using Chart.js.
 */
function renderChart(carrierKey, color, forecast) {
  const canvas = document.getElementById(`chart-${carrierKey}`);
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const now = new Date();
  const labels = forecast.map((f) => {
    const h = (now.getHours() + f.hour) % 24;
    return `${h.toString().padStart(2, "0")}:00`;
  });

  const rsrpData = forecast.map(f => f.rsrp_dbm);

  // Color each point by signal quality
  const pointColors = forecast.map(f => {
    switch (f.quality) {
      case "excellent": return "#22c55e";
      case "good": return "#84cc16";
      case "fair": return "#eab308";
      case "poor": return "#f97316";
      default: return "#ef4444";
    }
  });

  new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "RSRP (dBm)",
        data: rsrpData,
        borderColor: color,
        backgroundColor: color + "20",
        fill: true,
        tension: 0.3,
        pointBackgroundColor: pointColors,
        pointRadius: 3,
        pointHoverRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              const f = forecast[ctx.dataIndex];
              let tip = `Quality: ${f.quality}`;
              if (f.condition) tip += `\nWeather: ${f.condition}`;
              if (f.weather_loss_db > 0) tip += `\nWeather loss: ${f.weather_loss_db} dB`;
              return tip;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#64748b", maxTicksLimit: 8 },
          grid: { color: "#1e293b" },
        },
        y: {
          title: { display: true, text: "RSRP (dBm)", color: "#64748b" },
          ticks: { color: "#64748b" },
          grid: { color: "#1e293b" },
          suggestedMin: -120,
          suggestedMax: -60,
        },
      },
    },
  });
}

/**
 * Render tower map using Leaflet.
 */
function renderMap(results) {
  const mapEl = document.getElementById("tower-map");
  if (!mapEl) return;

  // Clear existing map
  if (window._forecastMap) {
    window._forecastMap.remove();
  }

  const map = L.map("tower-map").setView([state.lat, state.lon], 11);
  window._forecastMap = map;

  // OpenStreetMap tiles (free, no key)
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(map);

  // User location marker
  L.circleMarker([state.lat, state.lon], {
    radius: 8,
    fillColor: "#3b82f6",
    color: "#1e40af",
    weight: 2,
    fillOpacity: 0.9,
  }).addTo(map).bindPopup(`<b>You</b><br>FSA: ${state.fsa}`);

  // Tower markers per carrier
  for (const carrier of CARRIERS) {
    const r = results[carrier.key];
    if (!r || r.noData || r.noTowers) continue;

    // Show nearest 3 towers
    for (const t of r.nearestTowers) {
      const isClosest = t === r.nearestTowers[0];
      L.circleMarker([t.tower.lt, t.tower.ln], {
        radius: isClosest ? 7 : 5,
        fillColor: carrier.color,
        color: isClosest ? "#fff" : carrier.color,
        weight: isClosest ? 2 : 1,
        fillOpacity: 0.8,
      }).addTo(map).bindPopup(
        `<b>${carrier.name} Tower</b><br>` +
        `Distance: ${t.distance_km.toFixed(1)} km<br>` +
        `Bands: ${t.tower.bc.join(", ")}<br>` +
        `Height: ${t.tower.ht}m | Gain: ${t.tower.gn} dBi`
      );

      // Draw line from user to closest tower
      if (isClosest) {
        L.polyline(
          [[state.lat, state.lon], [t.tower.lt, t.tower.ln]],
          { color: carrier.color, weight: 2, dashArray: "5,5", opacity: 0.6 }
        ).addTo(map);
      }
    }
  }
}

// ============================================================================
// UI Helpers
// ============================================================================

/**
 * Set the status bar message and style.
 */
function setStatus(message, type = "") {
  const bar = document.getElementById("status-bar");
  bar.textContent = message;
  bar.className = `status-bar ${type}`;
  bar.style.display = message ? "block" : "none";
}

/**
 * Set active scenario button.
 */
function setActiveScenario(btn) {
  document.querySelectorAll(".scenario-buttons button").forEach(b =>
    b.classList.remove("active"));
  btn.classList.add("active");
}

// ============================================================================
// Event Handlers
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("postal-input");
  const btn = document.getElementById("search-btn");

  // Search on button click
  btn.addEventListener("click", () => {
    const code = input.value.trim();
    if (code) runForecast(code);
  });

  // Search on Enter key
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const code = input.value.trim();
      if (code) runForecast(code);
    }
  });

  // Quick location buttons
  document.querySelectorAll("[data-postal]").forEach(el => {
    el.addEventListener("click", () => {
      input.value = el.dataset.postal;
      runForecast(el.dataset.postal);
    });
  });

  // Scenario buttons
  document.querySelectorAll("[data-scenario]").forEach(el => {
    el.addEventListener("click", () => {
      state.currentScenario = el.dataset.scenario;
      setActiveScenario(el);
      // Re-run forecast if we already have a location
      if (state.fsa) {
        runForecast(input.value.trim() || state.fsa);
      }
    });
  });

  // Load from URL hash
  const hash = window.location.hash.substring(1);
  if (hash && hash.length >= 3) {
    input.value = hash;
    runForecast(hash);
  }
});
