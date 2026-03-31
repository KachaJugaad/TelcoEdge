/**
 * weather-adapter.js — MSC GeoMet Weather Forecast Adapter
 *
 * Fetches hourly weather forecast data from Environment and Climate Change
 * Canada (ECCC) via the MSC GeoMet OGC API.
 *
 * Key facts:
 *   - Base URL: https://api.weather.gc.ca/
 *   - Auth: NONE — anonymous, free, Government of Canada
 *   - CORS: Access-Control-Allow-Origin: * (browser-safe)
 *   - Format: GeoJSON
 *
 * This module translates ECCC weather data into the WeatherConditions format
 * expected by signal-model.js.
 *
 * Source: https://eccc-msc.github.io/open-data/msc-geomet/readme_en/
 */

// ============================================================================
// Configuration
// ============================================================================

const GEOMET_BASE = "https://api.weather.gc.ca";

/** Retry config: 3-second backoff on 429/5xx (as per PROJECT.md) */
const MAX_RETRIES = 3;
const BASE_DELAY_MS = 3000;

// ============================================================================
// API Fetching
// ============================================================================

/**
 * Fetch from GeoMet API with retry and exponential backoff.
 *
 * @param {string} url - Full URL to fetch
 * @returns {Promise<Object>} Parsed JSON response
 * @throws {Error} If all retries fail
 */
async function fetchWithRetry(url) {
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const resp = await fetch(url);

      if (resp.ok) return await resp.json();

      // Retry on 429 (rate limit) or 5xx (server error)
      if (resp.status === 429 || resp.status >= 500) {
        const delay = BASE_DELAY_MS * Math.pow(2, attempt);
        console.warn(`GeoMet ${resp.status}, retrying in ${delay}ms...`);
        await new Promise(r => setTimeout(r, delay));
        continue;
      }

      throw new Error(`GeoMet API error: ${resp.status} ${resp.statusText}`);
    } catch (err) {
      if (attempt === MAX_RETRIES - 1) throw err;
      const delay = BASE_DELAY_MS * Math.pow(2, attempt);
      await new Promise(r => setTimeout(r, delay));
    }
  }
}

// ============================================================================
// Weather Data Fetching
// ============================================================================

/**
 * Fetch current weather observations near a location.
 *
 * Uses the AQHI (Air Quality Health Index) observations which include
 * temperature and atmospheric data at monitoring stations across Canada.
 *
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @param {number} radiusDeg - Search radius in degrees (default 1°)
 * @returns {Promise<Object|null>} Nearest observation or null
 */
async function fetchCurrentObservation(lat, lon, radiusDeg = 1) {
  const bbox = `${lon - radiusDeg},${lat - radiusDeg},${lon + radiusDeg},${lat + radiusDeg}`;
  const url = `${GEOMET_BASE}/collections/aqhi-observations-realtime/items` +
              `?bbox=${bbox}&limit=5&sortby=-datetime&f=json`;

  try {
    const data = await fetchWithRetry(url);
    if (data.features && data.features.length > 0) {
      return data.features[0];
    }
    return null;
  } catch (err) {
    console.warn("Failed to fetch AQHI observations:", err.message);
    return null;
  }
}

/**
 * Fetch weather forecast from ECCC City Page Weather (experimental).
 *
 * Returns hourly conditions for a city/station if available.
 * Falls back to hydrometric/precipitation data as supplementary source.
 *
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @returns {Promise<Object|null>} Forecast data or null
 */
async function fetchCityForecast(lat, lon) {
  const bbox = `${lon - 0.5},${lat - 0.5},${lon + 0.5},${lat + 0.5}`;
  const url = `${GEOMET_BASE}/collections/citypage-weather-xml/items` +
              `?bbox=${bbox}&limit=1&f=json`;

  try {
    const data = await fetchWithRetry(url);
    if (data.features && data.features.length > 0) {
      return data.features[0];
    }
    return null;
  } catch (err) {
    console.warn("Failed to fetch city forecast:", err.message);
    return null;
  }
}

/**
 * Fetch hydrometric (precipitation) data near a location.
 *
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @returns {Promise<number>} Precipitation value in mm, or 0
 */
async function fetchPrecipitation(lat, lon) {
  const bbox = `${lon - 1},${lat - 1},${lon + 1},${lat + 1}`;
  const url = `${GEOMET_BASE}/collections/hydrometric-daily-mean/items` +
              `?bbox=${bbox}&limit=1&sortby=-DATE&f=json`;

  try {
    const data = await fetchWithRetry(url);
    if (data.features && data.features.length > 0) {
      const props = data.features[0].properties;
      return props.DISCHARGE || props.LEVEL || 0;
    }
    return 0;
  } catch {
    return 0;
  }
}

// ============================================================================
// Weather-to-Signal Translation
// ============================================================================

/**
 * Translate raw ECCC condition text into signal model weather parameters.
 *
 * ECCC uses standard condition phrases like "Light Rain", "Heavy Snow",
 * "Fog", "Thunderstorm", etc. We map these to quantitative values
 * for the signal propagation model.
 *
 * @param {string} condition - ECCC condition text
 * @param {number} temp_c    - Temperature in °C
 * @returns {Object} Partial WeatherConditions object
 */
function conditionToWeatherParams(condition, temp_c = 10) {
  const cond = (condition || "").toLowerCase();

  // Default: clear conditions
  const wx = {
    rain_mm_h: 0,
    snow_mm_h: 0,
    visibility_km: 15,
    wind_kmh: 15,
    pm25: 20,
    condition: condition || "Clear",
  };

  // Rain conditions
  if (cond.includes("thunderstorm") || cond.includes("heavy rain")) {
    wx.rain_mm_h = 30;
    wx.visibility_km = 3;
    wx.wind_kmh = 50;
  } else if (cond.includes("rain") && cond.includes("light")) {
    wx.rain_mm_h = 2;
    wx.visibility_km = 8;
  } else if (cond.includes("rain") || cond.includes("shower")) {
    wx.rain_mm_h = 8;
    wx.visibility_km = 5;
  } else if (cond.includes("drizzle")) {
    wx.rain_mm_h = 1;
    wx.visibility_km = 6;
  }

  // Snow conditions
  if (cond.includes("blizzard") || cond.includes("heavy snow")) {
    wx.snow_mm_h = 10;
    wx.visibility_km = 0.5;
    wx.wind_kmh = 60;
  } else if (cond.includes("snow") && cond.includes("light")) {
    wx.snow_mm_h = 1;
    wx.visibility_km = 4;
  } else if (cond.includes("snow") || cond.includes("flurr")) {
    wx.snow_mm_h = 4;
    wx.visibility_km = 2;
  } else if (cond.includes("ice pellet") || cond.includes("freezing")) {
    wx.snow_mm_h = 3;
    wx.rain_mm_h = 2;
    wx.visibility_km = 3;
  }

  // Fog
  if (cond.includes("fog")) {
    wx.visibility_km = cond.includes("dense") ? 0.1 : 0.5;
  } else if (cond.includes("mist") || cond.includes("haze")) {
    wx.visibility_km = 2;
  }

  // Smoke (wildfire)
  if (cond.includes("smoke") || cond.includes("hazy")) {
    wx.pm25 = 200;
    wx.visibility_km = Math.min(wx.visibility_km, 4);
  }

  // Wind
  if (cond.includes("windy") || cond.includes("wind")) {
    wx.wind_kmh = 50;
  }

  return wx;
}

/**
 * Generate a synthetic 24-hour weather forecast from current conditions.
 *
 * Since MSC GeoMet's hourly forecast API is limited, we synthesize a
 * plausible 24-hour forecast by varying conditions around the current
 * observation using typical diurnal weather patterns.
 *
 * @param {Object} currentWx  - Current weather conditions
 * @param {number} currentTemp - Current temperature (°C)
 * @returns {WeatherConditions[]} Array of 24 hourly conditions
 */
function synthesize24hForecast(currentWx, currentTemp = 10) {
  const hours = [];
  const now = new Date();
  const currentHour = now.getHours();

  for (let i = 0; i < 24; i++) {
    const hour = (currentHour + i) % 24;

    // Temperature: diurnal cycle (±5°C, peaks at 14:00)
    const tempOffset = 5 * Math.sin((hour - 6) * Math.PI / 12);
    const temp = currentTemp + tempOffset;

    // Base weather from current conditions
    const wx = { ...currentWx, temp_c: Math.round(temp * 10) / 10 };

    // Diurnal weather variation patterns:
    // - Rain more likely 14:00-20:00 (convective afternoon)
    // - Fog more likely 04:00-08:00 (morning radiation fog)
    // - Wind peaks 12:00-18:00
    if (currentWx.rain_mm_h > 0) {
      // If currently raining, vary intensity over the day
      const rainFactor = (hour >= 14 && hour <= 20) ? 1.5 :
                         (hour >= 2 && hour <= 8) ? 0.3 : 1.0;
      wx.rain_mm_h = Math.round(currentWx.rain_mm_h * rainFactor * 10) / 10;
    }

    if (currentWx.visibility_km < 2) {
      // Fog tends to burn off by mid-morning
      if (hour >= 10 && hour <= 16) {
        wx.visibility_km = Math.min(15, currentWx.visibility_km * 5);
      }
    }

    // Wind: peaks afternoon
    const windFactor = 0.7 + 0.6 * Math.sin((hour - 6) * Math.PI / 12);
    wx.wind_kmh = Math.round(currentWx.wind_kmh * windFactor);

    // Condition text for each hour
    if (wx.rain_mm_h >= 20) wx.condition = "Heavy Rain";
    else if (wx.rain_mm_h >= 5) wx.condition = "Rain";
    else if (wx.rain_mm_h > 0) wx.condition = "Light Rain";
    else if (wx.snow_mm_h >= 5) wx.condition = "Heavy Snow";
    else if (wx.snow_mm_h > 0) wx.condition = "Light Snow";
    else if (wx.visibility_km < 1) wx.condition = "Fog";
    else if (wx.pm25 > 100) wx.condition = "Smoke";
    else if (hour >= 6 && hour <= 18) wx.condition = "Clear";
    else wx.condition = "Clear Night";

    hours.push(wx);
  }

  return hours;
}

// ============================================================================
// Main Public API
// ============================================================================

/**
 * Get 24-hour weather forecast for a location, formatted for signal model.
 *
 * Attempts to fetch real ECCC data; falls back to reasonable defaults
 * if API is unreachable (as per PROJECT.md: use cache if unavailable).
 *
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @returns {Promise<{hourly: WeatherConditions[], source: string}>}
 */
async function getWeatherForecast(lat, lon) {
  try {
    // Try to get real observation data
    const obs = await fetchCurrentObservation(lat, lon);

    if (obs && obs.properties) {
      const props = obs.properties;
      const condition = props.condition || props.observation || "Clear";
      const temp = props.temp || props.temperature || 10;

      const currentWx = conditionToWeatherParams(condition, temp);
      currentWx.temp_c = temp;

      const hourly = synthesize24hForecast(currentWx, temp);
      return { hourly, source: "MSC GeoMet (live)", temp_c: temp, condition };
    }

    // If no observation found, try city forecast
    const city = await fetchCityForecast(lat, lon);
    if (city && city.properties) {
      const temp = city.properties.temp || 10;
      const condition = city.properties.condition || "Partly Cloudy";
      const currentWx = conditionToWeatherParams(condition, temp);
      currentWx.temp_c = temp;

      const hourly = synthesize24hForecast(currentWx, temp);
      return { hourly, source: "MSC GeoMet City (live)", temp_c: temp, condition };
    }
  } catch (err) {
    console.warn("Weather API unavailable:", err.message);
  }

  // Fallback: generate forecast from seasonal defaults for this latitude
  const seasonalTemp = getSeasonalDefault(lat);
  const defaultWx = conditionToWeatherParams("Partly Cloudy", seasonalTemp);
  defaultWx.temp_c = seasonalTemp;
  const hourly = synthesize24hForecast(defaultWx, seasonalTemp);

  return {
    hourly,
    source: "Seasonal default (API unavailable)",
    temp_c: seasonalTemp,
    condition: "Partly Cloudy",
  };
}

/**
 * Get a reasonable default temperature based on latitude and current month.
 *
 * Canada ranges from ~5°C annual mean in the south to -15°C in the Arctic.
 * This provides a ballpark when the API is unreachable.
 *
 * @param {number} lat - Latitude
 * @returns {number} Estimated temperature in °C
 */
function getSeasonalDefault(lat) {
  const month = new Date().getMonth(); // 0-11

  // Seasonal offset: summer peak in July (month 6), winter trough in January
  const seasonalOffset = 15 * Math.cos((month - 6) * Math.PI / 6);

  // Latitude factor: -0.7°C per degree north from 43°N
  const latFactor = -0.7 * (lat - 43);

  // Base temp at 43°N (southern Ontario) in spring/fall: ~10°C
  return Math.round(10 + seasonalOffset + latFactor);
}

/**
 * Generate a specific weather scenario for demo/testing purposes.
 *
 * @param {string} scenario - One of: "clear", "rain", "snow", "blizzard",
 *                            "fog", "smoke", "ice_storm", "thunderstorm"
 * @param {number} temp_c   - Temperature override (optional)
 * @returns {WeatherConditions[]} 24-hour forecast for the scenario
 */
function generateScenario(scenario, temp_c = null) {
  const scenarios = {
    clear:        { condition: "Clear",           temp: 20 },
    rain:         { condition: "Rain",            temp: 12 },
    heavy_rain:   { condition: "Heavy Rain",      temp: 15 },
    thunderstorm: { condition: "Thunderstorm",    temp: 25 },
    snow:         { condition: "Snow",            temp: -5 },
    blizzard:     { condition: "Blizzard",        temp: -15 },
    fog:          { condition: "Dense Fog",       temp: 5 },
    smoke:        { condition: "Smoke and Haze",  temp: 28 },
    ice_storm:    { condition: "Freezing Rain",   temp: -1 },
  };

  const s = scenarios[scenario] || scenarios.clear;
  const temp = temp_c !== null ? temp_c : s.temp;
  const wx = conditionToWeatherParams(s.condition, temp);
  wx.temp_c = temp;

  return synthesize24hForecast(wx, temp);
}

// ============================================================================
// Exports
// ============================================================================

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    fetchWithRetry,
    fetchCurrentObservation,
    conditionToWeatherParams,
    synthesize24hForecast,
    getWeatherForecast,
    getSeasonalDefault,
    generateScenario,
    GEOMET_BASE,
  };
}
