#!/usr/bin/env node
/**
 * test-weather-adapter.js — Unit tests for MSC GeoMet weather adapter
 *
 * Tests the weather condition translation, forecast synthesis, and
 * seasonal defaults — all offline (no API calls).
 *
 * Run: node tests/test-weather-adapter.js
 */

const {
  conditionToWeatherParams,
  synthesize24hForecast,
  getSeasonalDefault,
  generateScenario,
} = require("../js/weather-adapter.js");

// ============================================================================
// Test Harness
// ============================================================================

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
// Condition Translation Tests
// ============================================================================

section("Condition → Weather Parameters");

// Clear conditions
const clear = conditionToWeatherParams("Clear", 20);
assert(clear.rain_mm_h === 0, "Clear → no rain");
assert(clear.snow_mm_h === 0, "Clear → no snow");
assert(clear.visibility_km >= 10, "Clear → good visibility");
assert(clear.pm25 < 50, "Clear → low PM2.5");

// Heavy rain
const heavyRain = conditionToWeatherParams("Heavy Rain", 15);
assert(heavyRain.rain_mm_h >= 20, `Heavy rain rate = ${heavyRain.rain_mm_h} mm/h (≥ 20)`);
assert(heavyRain.visibility_km <= 5, "Heavy rain → reduced visibility");

// Light rain
const lightRain = conditionToWeatherParams("Light Rain", 12);
assert(lightRain.rain_mm_h > 0 && lightRain.rain_mm_h < 5,
  `Light rain rate = ${lightRain.rain_mm_h} mm/h (0-5)`);

// Thunderstorm
const tstorm = conditionToWeatherParams("Thunderstorm with Heavy Rain", 25);
assert(tstorm.rain_mm_h >= 25, "Thunderstorm → heavy rain");
assert(tstorm.wind_kmh >= 40, "Thunderstorm → strong wind");

// Snow
const snow = conditionToWeatherParams("Snow", -5);
assert(snow.snow_mm_h > 0, "Snow → snow rate > 0");
assert(snow.rain_mm_h === 0, "Snow → no rain");

// Blizzard
const blizzard = conditionToWeatherParams("Blizzard", -20);
assert(blizzard.snow_mm_h >= 8, `Blizzard snow = ${blizzard.snow_mm_h} mm/h (≥ 8)`);
assert(blizzard.visibility_km <= 1, "Blizzard → very low visibility");
assert(blizzard.wind_kmh >= 50, "Blizzard → strong wind");

// Fog
const fog = conditionToWeatherParams("Fog", 5);
assert(fog.visibility_km <= 1, `Fog visibility = ${fog.visibility_km} km (≤ 1)`);

// Dense fog
const denseFog = conditionToWeatherParams("Dense Fog", 3);
assert(denseFog.visibility_km <= 0.2, "Dense fog → very low visibility");

// Smoke (wildfire)
const smoke = conditionToWeatherParams("Smoke and Haze", 30);
assert(smoke.pm25 >= 150, `Smoke PM2.5 = ${smoke.pm25} (≥ 150)`);
assert(smoke.visibility_km <= 5, "Smoke → reduced visibility");

// Freezing rain
const fzRain = conditionToWeatherParams("Freezing Rain", -2);
assert(fzRain.rain_mm_h > 0, "Freezing rain → has rain");
assert(fzRain.snow_mm_h > 0, "Freezing rain → also has ice");

// Unknown condition → defaults to clear-ish
const unknown = conditionToWeatherParams("Partly Cloudy", 15);
assert(unknown.rain_mm_h === 0, "Partly Cloudy → no rain");
assert(unknown.visibility_km >= 10, "Partly Cloudy → good visibility");

// ============================================================================
// Forecast Synthesis Tests
// ============================================================================

section("24-Hour Forecast Synthesis");

const baseWx = conditionToWeatherParams("Rain", 12);
baseWx.temp_c = 12;
const forecast = synthesize24hForecast(baseWx, 12);

assert(forecast.length === 24, "Forecast has 24 hours");

// Temperature should vary (diurnal cycle)
const temps = forecast.map(f => f.temp_c);
const tempRange = Math.max(...temps) - Math.min(...temps);
assert(tempRange >= 5, `Temperature range = ${tempRange.toFixed(1)}°C (≥ 5°C diurnal)`);

// All hours should have required fields
assert(forecast.every(f => typeof f.rain_mm_h === "number"), "All hours have rain_mm_h");
assert(forecast.every(f => typeof f.temp_c === "number"), "All hours have temp_c");
assert(forecast.every(f => typeof f.visibility_km === "number"), "All hours have visibility_km");
assert(forecast.every(f => typeof f.condition === "string"), "All hours have condition string");

// Rain intensity should vary across the day (not all identical)
const rainRates = forecast.map(f => f.rain_mm_h);
const uniqueRainRates = new Set(rainRates.map(r => Math.round(r * 10)));
assert(uniqueRainRates.size >= 2,
  `Rain rates vary: ${uniqueRainRates.size} unique values`);

// Clear weather forecast should have no rain
const clearForecast = synthesize24hForecast(
  conditionToWeatherParams("Clear", 20), 20
);
assert(clearForecast.every(f => f.rain_mm_h === 0), "Clear forecast → no rain any hour");

// ============================================================================
// Seasonal Default Tests
// ============================================================================

section("Seasonal Temperature Defaults");

// Southern Ontario (lat 43): should be reasonable year-round
const torontoTemp = getSeasonalDefault(43);
assert(torontoTemp >= -20 && torontoTemp <= 35,
  `Toronto default = ${torontoTemp}°C (reasonable range)`);

// Arctic (lat 70): should be colder than south
const arcticTemp = getSeasonalDefault(70);
assert(arcticTemp < torontoTemp,
  `Arctic (${arcticTemp}°C) < Toronto (${torontoTemp}°C)`);

// Edmonton (lat 53.5): between Toronto and Arctic
const edmontonTemp = getSeasonalDefault(53.5);
assert(edmontonTemp <= torontoTemp && edmontonTemp >= arcticTemp,
  `Edmonton (${edmontonTemp}°C) between Toronto and Arctic`);

// ============================================================================
// Scenario Generator Tests
// ============================================================================

section("Weather Scenario Generator");

const scenarios = ["clear", "rain", "heavy_rain", "thunderstorm",
                   "snow", "blizzard", "fog", "smoke", "ice_storm"];

for (const name of scenarios) {
  const sc = generateScenario(name);
  assert(sc.length === 24, `${name}: 24 hours`);
  assert(sc.every(h => typeof h.temp_c === "number"), `${name}: all hours have temp`);
}

// Clear scenario: no precipitation
const clearSc = generateScenario("clear");
assert(clearSc.every(h => h.rain_mm_h === 0 && h.snow_mm_h === 0),
  "Clear scenario: no precipitation");

// Blizzard: should have snow and low visibility
const blizzardSc = generateScenario("blizzard");
assert(blizzardSc.some(h => h.snow_mm_h > 5),
  "Blizzard scenario: has significant snow");
assert(blizzardSc.some(h => h.visibility_km < 2),
  "Blizzard scenario: has low visibility periods");

// Smoke: should have high PM2.5
const smokeSc = generateScenario("smoke");
assert(smokeSc.every(h => h.pm25 >= 100),
  "Smoke scenario: all hours have high PM2.5");

// Custom temperature override
const customTemp = generateScenario("rain", -3);
assert(customTemp.some(h => h.temp_c < 0),
  "Temperature override works (sub-zero rain)");

// ============================================================================
// Summary
// ============================================================================

console.log(`\n═══════════════════════════════════════`);
console.log(`  TOTAL: ${passCount + failCount} tests`);
console.log(`  PASS:  ${passCount}`);
console.log(`  FAIL:  ${failCount}`);
console.log(`═══════════════════════════════════════`);

process.exit(failCount > 0 ? 1 : 0);
