#!/usr/bin/env node
/**
 * test-e2e-pipeline.js — End-to-end integration test for Signal Forecast
 *
 * Tests the full pipeline: postal code → towers → weather → signal prediction.
 * Validates physical plausibility at each stage.
 *
 * Run: node tests/test-e2e-pipeline.js
 */

const fs = require("fs");
const path = require("path");
const { postalToCoords } = require("../js/postal-lookup.js");
const {
  findNearestTowers,
  forecastSignal24h,
  predictSignal,
  SIGNAL_THRESHOLDS,
} = require("../js/signal-model.js");
const {
  conditionToWeatherParams,
  synthesize24hForecast,
  generateScenario,
} = require("../js/weather-adapter.js");

let passCount = 0;
let failCount = 0;

function assert(condition, testName, detail = "") {
  if (condition) {
    passCount++;
    console.log(`  ✓ ${testName}`);
  } else {
    failCount++;
    console.error(`  ✗ ${testName} ${detail}`);
  }
}

function section(name) {
  console.log(`\n─── ${name} ───`);
}

// ============================================================================
// Load Real Tower Data
// ============================================================================

section("Tower Data Loading");

const dataDir = path.join(__dirname, "..", "data");

function loadTowerFile(filename) {
  const fpath = path.join(dataDir, filename);
  assert(fs.existsSync(fpath), `${filename} exists`);
  const data = JSON.parse(fs.readFileSync(fpath, "utf-8"));
  assert(Array.isArray(data), `${filename} is array`);
  assert(data.length > 100, `${filename} has ${data.length} sites (> 100)`);
  return data;
}

const bellTowers = loadTowerFile("towers_bell.json");
const rogersTowers = loadTowerFile("towers_rogers.json");
const telusTowers = loadTowerFile("towers_telus.json");

// Verify sorted by latitude (required for binary search)
function isSorted(arr) {
  for (let i = 1; i < arr.length; i++) {
    if (arr[i].lt < arr[i - 1].lt) return false;
  }
  return true;
}
assert(isSorted(bellTowers), "Bell towers sorted by latitude");
assert(isSorted(rogersTowers), "Rogers towers sorted by latitude");
assert(isSorted(telusTowers), "TELUS towers sorted by latitude");

// ============================================================================
// E2E Pipeline: Toronto
// ============================================================================

section("E2E Pipeline: Toronto (M5V 3L9)");

// Step 1: Geocode
const toronto = postalToCoords("M5V 3L9");
assert(toronto !== null, "Toronto geocoded");

// Step 2: Find towers
const bellNear = findNearestTowers(bellTowers, toronto.lat, toronto.lon, 3, 20);
const rogersNear = findNearestTowers(rogersTowers, toronto.lat, toronto.lon, 3, 20);
const telusNear = findNearestTowers(telusTowers, toronto.lat, toronto.lon, 3, 20);

assert(bellNear.length >= 1, `Bell: ${bellNear.length} towers within 20km`);
assert(rogersNear.length >= 1, `Rogers: ${rogersNear.length} towers within 20km`);
assert(telusNear.length >= 1, `TELUS: ${telusNear.length} towers within 20km`);

// Nearest tower should be within 5 km for downtown Toronto
if (bellNear.length > 0)
  assert(bellNear[0].distance_km < 5,
    `Bell nearest = ${bellNear[0].distance_km.toFixed(1)} km (< 5)`);
if (rogersNear.length > 0)
  assert(rogersNear[0].distance_km < 5,
    `Rogers nearest = ${rogersNear[0].distance_km.toFixed(1)} km (< 5)`);
if (telusNear.length > 0)
  assert(telusNear[0].distance_km < 5,
    `TELUS nearest = ${telusNear[0].distance_km.toFixed(1)} km (< 5)`);

// Step 3: Weather forecast
const clearWx = synthesize24hForecast(
  conditionToWeatherParams("Clear", 15), 15
);
assert(clearWx.length === 24, "24-hour forecast generated");

// Step 4: Signal prediction
if (bellNear.length > 0) {
  const forecast = forecastSignal24h(bellNear[0].tower, toronto.lat, toronto.lon, clearWx);
  assert(forecast.length === 24, "Bell 24h forecast has 24 entries");
  assert(forecast[0].rsrp_dbm > -120, `Bell RSRP = ${forecast[0].rsrp_dbm} dBm (> -120)`);
  assert(forecast[0].rsrp_dbm < 0, `Bell RSRP = ${forecast[0].rsrp_dbm} dBm (< 0, physically valid)`);
}

// ============================================================================
// E2E Pipeline: Rural Saskatchewan
// ============================================================================

section("E2E Pipeline: Rural Saskatchewan (S0G 0A0)");

const ruralSK = postalToCoords("S0G 0A0");
assert(ruralSK !== null, "Rural SK geocoded");

// Towers will be further away in rural areas — use wider search radius
// Province centroid may be far from actual towers, so 200 km is reasonable
const bellRural = findNearestTowers(bellTowers, ruralSK.lat, ruralSK.lon, 3, 200);
const rogersRural = findNearestTowers(rogersTowers, ruralSK.lat, ruralSK.lon, 3, 200);
const telusRural = findNearestTowers(telusTowers, ruralSK.lat, ruralSK.lon, 3, 200);

const ruralCoverage = bellRural.length > 0 || rogersRural.length > 0 || telusRural.length > 0;
assert(ruralCoverage, "At least one carrier has coverage within 200 km");

// Rural signal should be weaker than urban
if (bellRural.length > 0 && bellNear.length > 0) {
  const ruralPred = predictSignal(bellRural[0].tower, ruralSK.lat, ruralSK.lon,
    clearWx[0], "low");
  const urbanPred = predictSignal(bellNear[0].tower, toronto.lat, toronto.lon,
    clearWx[0], "low");

  // Rural should generally have weaker signal (farther from tower)
  if (bellRural[0].distance_km > bellNear[0].distance_km) {
    assert(ruralPred.rsrp_dbm <= urbanPred.rsrp_dbm,
      `Rural RSRP (${ruralPred.rsrp_dbm}) ≤ urban (${urbanPred.rsrp_dbm})`);
  }
}

// ============================================================================
// E2E Pipeline: Weather Impact Comparison
// ============================================================================

section("E2E Pipeline: Weather Impact on Signal");

if (bellNear.length > 0) {
  const tower = bellNear[0].tower;

  // Clear weather
  const clearResult = predictSignal(tower, toronto.lat, toronto.lon,
    { rain_mm_h: 0, snow_mm_h: 0, temp_c: 15, visibility_km: 20, wind_kmh: 10, pm25: 15 },
    "high" // 3500 MHz — most weather-sensitive band
  );

  // Heavy rain
  const rainResult = predictSignal(tower, toronto.lat, toronto.lon,
    { rain_mm_h: 40, snow_mm_h: 0, temp_c: 10, visibility_km: 2, wind_kmh: 50, pm25: 20 },
    "high"
  );

  // Blizzard
  const blizzardResult = predictSignal(tower, toronto.lat, toronto.lon,
    { rain_mm_h: 0, snow_mm_h: 15, temp_c: -1, visibility_km: 0.3, wind_kmh: 70, pm25: 15 },
    "high"
  );

  // Wildfire smoke
  const smokeResult = predictSignal(tower, toronto.lat, toronto.lon,
    { rain_mm_h: 0, snow_mm_h: 0, temp_c: 30, visibility_km: 3, wind_kmh: 20, pm25: 400 },
    "high"
  );

  // Clear should be best
  assert(clearResult.rsrp_dbm >= rainResult.rsrp_dbm,
    `Clear (${clearResult.rsrp_dbm}) ≥ Rain (${rainResult.rsrp_dbm})`);

  assert(clearResult.rsrp_dbm >= blizzardResult.rsrp_dbm,
    `Clear (${clearResult.rsrp_dbm}) ≥ Blizzard (${blizzardResult.rsrp_dbm})`);

  assert(clearResult.rsrp_dbm >= smokeResult.rsrp_dbm,
    `Clear (${clearResult.rsrp_dbm}) ≥ Smoke (${smokeResult.rsrp_dbm})`);

  // Weather losses should be positive
  assert(rainResult.weather_loss_db > 0,
    `Rain weather loss = ${rainResult.weather_loss_db} dB (> 0)`);
  assert(blizzardResult.weather_loss_db > 0,
    `Blizzard weather loss = ${blizzardResult.weather_loss_db} dB (> 0)`);
  assert(smokeResult.weather_loss_db > 0,
    `Smoke weather loss = ${smokeResult.weather_loss_db} dB (> 0)`);

  // Band comparison: 700 MHz should be more resilient than 3500 MHz
  const rain700 = predictSignal(tower, toronto.lat, toronto.lon,
    { rain_mm_h: 40, snow_mm_h: 0, temp_c: 10, visibility_km: 2, wind_kmh: 50, pm25: 20 },
    "low"
  );
  assert(rain700.weather_loss_db <= rainResult.weather_loss_db,
    `700 MHz rain loss (${rain700.weather_loss_db}) ≤ 3500 MHz (${rainResult.weather_loss_db})`);
}

// ============================================================================
// E2E: All Weather Scenarios
// ============================================================================

section("All Weather Scenarios Generate Valid Forecasts");

const scenarios = ["clear", "rain", "heavy_rain", "thunderstorm",
                   "snow", "blizzard", "fog", "smoke", "ice_storm"];

for (const scenario of scenarios) {
  const wx = generateScenario(scenario);
  if (bellNear.length > 0) {
    const forecast = forecastSignal24h(bellNear[0].tower, toronto.lat, toronto.lon, wx);
    const allValid = forecast.every(f =>
      f.rsrp_dbm > -150 && f.rsrp_dbm < 50 &&
      typeof f.quality === "string"
    );
    assert(allValid, `${scenario}: all 24 hours have valid RSRP and quality`);
  }
}

// ============================================================================
// E2E: Multiple Cities
// ============================================================================

section("Multi-City Coverage Check");

const cities = [
  { name: "Ottawa",    code: "K1A 0B1" },
  { name: "Montreal",  code: "H3A 0G4" },
  { name: "Vancouver", code: "V6B 1A1" },
  { name: "Calgary",   code: "T2P 1J9" },
  { name: "Edmonton",  code: "T5J 0K1" },
  { name: "Winnipeg",  code: "R3C 4A5" },
  { name: "Halifax",   code: "B3H 4R2" },
];

for (const city of cities) {
  const loc = postalToCoords(city.code);
  assert(loc !== null, `${city.name} geocoded`);

  const bell = findNearestTowers(bellTowers, loc.lat, loc.lon, 1, 30);
  const rogers = findNearestTowers(rogersTowers, loc.lat, loc.lon, 1, 30);
  const telus = findNearestTowers(telusTowers, loc.lat, loc.lon, 1, 30);

  const hasAny = bell.length > 0 || rogers.length > 0 || telus.length > 0;
  assert(hasAny, `${city.name}: at least 1 carrier within 30 km`);
}

// ============================================================================
// Data Integrity
// ============================================================================

section("Tower Data Integrity");

// Check a sample of tower records have valid fields
function checkTowerIntegrity(towers, name) {
  const sample = towers.slice(0, 100);
  const allValid = sample.every(t =>
    typeof t.lt === "number" && t.lt >= 41 && t.lt <= 84 &&
    typeof t.ln === "number" && t.ln >= -141 && t.ln <= -52 &&
    typeof t.ht === "number" && t.ht >= 0 &&
    Array.isArray(t.bc) && t.bc.length > 0
  );
  assert(allValid, `${name}: first 100 records have valid fields`);
}

checkTowerIntegrity(bellTowers, "Bell");
checkTowerIntegrity(rogersTowers, "Rogers");
checkTowerIntegrity(telusTowers, "TELUS");

// Metadata file
const metaPath = path.join(dataDir, "towers_meta.json");
assert(fs.existsSync(metaPath), "towers_meta.json exists");
const meta = JSON.parse(fs.readFileSync(metaPath, "utf-8"));
assert(meta.Bell && meta.Bell.sites > 0, `Meta: Bell has ${meta.Bell.sites} sites`);
assert(meta.Rogers && meta.Rogers.sites > 0, `Meta: Rogers has ${meta.Rogers.sites} sites`);
assert(meta.TELUS && meta.TELUS.sites > 0, `Meta: TELUS has ${meta.TELUS.sites} sites`);

// ============================================================================
// Summary
// ============================================================================

console.log(`\n═══════════════════════════════════════`);
console.log(`  TOTAL: ${passCount + failCount} tests`);
console.log(`  PASS:  ${passCount}`);
console.log(`  FAIL:  ${failCount}`);
console.log(`═══════════════════════════════════════`);

process.exit(failCount > 0 ? 1 : 0);
