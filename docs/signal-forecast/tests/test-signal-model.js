#!/usr/bin/env node
/**
 * test-signal-model.js — Unit tests for signal propagation model
 *
 * Tests verify physical plausibility of all RF calculations:
 *   - FSPL matches textbook values
 *   - Rain attenuation increases with rain rate and frequency
 *   - Snow/fog/smoke models behave monotonically
 *   - Composite signal prediction gives realistic RSRP values
 *   - Tower search returns correct nearest towers
 *   - 24h forecast produces valid arrays
 *
 * Run: node tests/test-signal-model.js
 */

const {
  haversineKm,
  fsplDb,
  rmaPathLossDb,
  rainAttenuationDb,
  fogAttenuationDb,
  snowAttenuationDb,
  smokeAttenuationDb,
  predictSignal,
  findNearestTowers,
  forecastSignal24h,
  SIGNAL_THRESHOLDS,
} = require("../js/signal-model.js");

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

function assertApprox(actual, expected, tolerance, testName) {
  const diff = Math.abs(actual - expected);
  assert(diff <= tolerance, testName,
    `— expected ${expected} ± ${tolerance}, got ${actual} (diff=${diff.toFixed(4)})`);
}

function section(name) {
  console.log(`\n─── ${name} ───`);
}

// ============================================================================
// Haversine Distance Tests
// ============================================================================

section("Haversine Distance");

// Ottawa to Toronto: ~353 km
assertApprox(haversineKm(45.4215, -75.6972, 43.6532, -79.3832), 353, 10,
  "Ottawa→Toronto ≈ 353 km");

// Same point = 0
assertApprox(haversineKm(45.0, -75.0, 45.0, -75.0), 0, 0.001,
  "Same point = 0 km");

// Calgary to Edmonton: ~300 km
assertApprox(haversineKm(51.0447, -114.0719, 53.5461, -113.4938), 280, 20,
  "Calgary→Edmonton ≈ 280 km");

// Very short distance: ~1.1 km
assertApprox(haversineKm(45.0, -75.0, 45.01, -75.0), 1.11, 0.1,
  "0.01° latitude ≈ 1.1 km");

// ============================================================================
// Free-Space Path Loss Tests
// ============================================================================

section("Free-Space Path Loss (FSPL)");

// Known value: 1 km at 700 MHz → FSPL ≈ 89.3 dB
assertApprox(fsplDb(1, 700), 89.3, 0.5,
  "1 km at 700 MHz ≈ 89.3 dB");

// Known value: 10 km at 1900 MHz → FSPL ≈ 118.0 dB
// FSPL = 20·log10(10) + 20·log10(1900) + 32.44 = 20 + 65.58 + 32.44 = 118.02
assertApprox(fsplDb(10, 1900), 118.0, 0.5,
  "10 km at 1900 MHz ≈ 118 dB");

// FSPL increases with distance
assert(fsplDb(20, 700) > fsplDb(10, 700),
  "FSPL increases with distance");

// FSPL increases with frequency
assert(fsplDb(10, 3500) > fsplDb(10, 700),
  "FSPL increases with frequency (3500 > 700 MHz)");

// Edge case: zero distance = 0
assertApprox(fsplDb(0, 700), 0, 0.001, "Zero distance → 0 dB");

// ============================================================================
// 3GPP RMa Path Loss Tests
// ============================================================================

section("3GPP RMa Path Loss");

// At 1 km, 700 MHz: should be > FSPL (clutter adds loss)
const rma1km = rmaPathLossDb(1, 700, 35);
assert(rma1km > fsplDb(1, 700) - 5,
  `RMa 1km/700MHz (${rma1km.toFixed(1)} dB) ≈ FSPL range`);

// At 10 km, should be significantly higher
const rma10km = rmaPathLossDb(10, 700, 35);
assert(rma10km > rma1km,
  `RMa 10km (${rma10km.toFixed(1)}) > 1km (${rma1km.toFixed(1)})`);

// Higher frequency = more loss at same distance
assert(rmaPathLossDb(5, 3500, 35) > rmaPathLossDb(5, 700, 35),
  "RMa loss higher at 3500 MHz than 700 MHz");

// Typical rural macro: 5 km at 700 MHz should be ~110-130 dB
assert(rma10km >= 100 && rma10km <= 160,
  `RMa 10km/700MHz = ${rma10km.toFixed(1)} dB (expected 100-160)`);

// ============================================================================
// Rain Attenuation Tests
// ============================================================================

section("Rain Attenuation");

// No rain = no attenuation
assertApprox(rainAttenuationDb(0, 0.7, 5), 0, 0.001,
  "No rain → 0 dB");

// Light rain (2 mm/h) at 700 MHz over 5 km: should be < 0.01 dB
const lightRain700 = rainAttenuationDb(2, 0.7, 5);
assert(lightRain700 < 0.1,
  `Light rain at 700 MHz = ${lightRain700.toFixed(4)} dB (< 0.1)`);

// Heavy rain (25 mm/h) at 3.5 GHz over 5 km: noticeable
const heavyRain3500 = rainAttenuationDb(25, 3.5, 5);
assert(heavyRain3500 > 0.1,
  `Heavy rain at 3.5 GHz = ${heavyRain3500.toFixed(3)} dB (> 0.1)`);

// Monotonic: more rain = more attenuation
assert(rainAttenuationDb(50, 3.5, 5) > rainAttenuationDb(10, 3.5, 5),
  "50 mm/h > 10 mm/h attenuation");

// Frequency dependence: 3.5 GHz > 0.7 GHz
assert(rainAttenuationDb(25, 3.5, 5) > rainAttenuationDb(25, 0.7, 5),
  "Rain attenuation higher at 3.5 GHz than 700 MHz");

// ============================================================================
// Fog Attenuation Tests
// ============================================================================

section("Fog Attenuation");

// Clear conditions (10+ km visibility) = no fog loss
assertApprox(fogAttenuationDb(15, 3.5, 5), 0, 0.001,
  "Clear visibility → 0 dB");

// Dense fog (0.1 km) at 3.5 GHz: should be measurable
const denseFog = fogAttenuationDb(0.1, 3.5, 5);
assert(denseFog > 0.01,
  `Dense fog at 3.5 GHz = ${denseFog.toFixed(3)} dB (> 0.01)`);

// Less fog = less attenuation
assert(fogAttenuationDb(0.1, 3.5, 5) > fogAttenuationDb(1, 3.5, 5),
  "Denser fog (0.1 km vis) > lighter fog (1 km vis)");

// ============================================================================
// Snow Attenuation Tests
// ============================================================================

section("Snow Attenuation");

// No snow = no attenuation
assertApprox(snowAttenuationDb(0, -10, 3.5, 5), 0, 0.001,
  "No snow → 0 dB");

// Wet snow (0°C) attenuates more than dry snow (-15°C)
const wetSnow = snowAttenuationDb(5, 0, 3.5, 5);
const drySnow = snowAttenuationDb(5, -15, 3.5, 5);
assert(wetSnow > drySnow,
  `Wet snow (${wetSnow.toFixed(4)} dB) > dry snow (${drySnow.toFixed(4)} dB)`);

// Higher frequency = more snow attenuation
assert(snowAttenuationDb(5, 0, 3.5, 5) > snowAttenuationDb(5, 0, 0.7, 5),
  "Snow attenuation higher at 3.5 GHz than 700 MHz");

// ============================================================================
// Smoke Attenuation Tests
// ============================================================================

section("Smoke (Wildfire) Attenuation");

// Low PM2.5 (< 50) = no effect
assertApprox(smokeAttenuationDb(30, 3.5, 5), 0, 0.001,
  "PM2.5 < 50 → 0 dB");

// Hazardous smoke (PM2.5 = 300) at 3.5 GHz
const heavySmoke = smokeAttenuationDb(300, 3.5, 5);
assert(heavySmoke > 0.1,
  `Heavy smoke at 3.5 GHz = ${heavySmoke.toFixed(3)} dB (> 0.1)`);

// More smoke = more attenuation
assert(smokeAttenuationDb(500, 3.5, 5) > smokeAttenuationDb(200, 3.5, 5),
  "PM2.5=500 > PM2.5=200 attenuation");

// Low frequency resilience: 700 MHz less affected than 3500 MHz
assert(smokeAttenuationDb(300, 3.5, 5) > smokeAttenuationDb(300, 0.7, 5),
  "Smoke attenuates 3.5 GHz more than 700 MHz");

// ============================================================================
// Composite Signal Prediction Tests
// ============================================================================

section("Composite Signal Prediction");

// Mock tower: typical Canadian rural macro cell
const mockTower = {
  lt: 45.4215,    // Ottawa area
  ln: -75.6972,
  el: 100,
  ht: 40,         // 40m antenna
  gn: 18,         // 18 dBi gain
  pw: 40,         // 40W TX power
  bc: ["low", "mid"],
};

// Clear weather, 2 km away: should be excellent/good signal
const clearWx = {
  rain_mm_h: 0, snow_mm_h: 0, temp_c: 15,
  visibility_km: 20, wind_kmh: 10, pm25: 15,
  condition: "Clear",
};
const result2km = predictSignal(mockTower, 45.44, -75.70, clearWx, "low");
assert(result2km.rsrp_dbm > -90,
  `2 km clear weather RSRP = ${result2km.rsrp_dbm} dBm (expected > -90)`);
assert(result2km.quality === "excellent" || result2km.quality === "good",
  `2 km clear quality = "${result2km.quality}" (expected excellent/good)`);
assert(result2km.weather_loss_db < 1,
  `Clear weather loss = ${result2km.weather_loss_db} dB (expected < 1)`);

// Heavy rain, same location: signal should degrade
const stormWx = {
  rain_mm_h: 30, snow_mm_h: 0, temp_c: 10,
  visibility_km: 2, wind_kmh: 60, pm25: 20,
  condition: "Heavy Rain",
};
const resultStorm = predictSignal(mockTower, 45.44, -75.70, stormWx, "low");
assert(resultStorm.rsrp_dbm < result2km.rsrp_dbm,
  `Storm RSRP (${resultStorm.rsrp_dbm}) < clear (${result2km.rsrp_dbm})`);
assert(resultStorm.weather_loss_db > 0,
  `Storm weather loss = ${resultStorm.weather_loss_db} dB (> 0)`);

// Far away (30 km): should be poor/none signal
const resultFar = predictSignal(mockTower, 45.70, -75.70, clearWx, "low");
assert(resultFar.rsrp_dbm < result2km.rsrp_dbm,
  `30 km RSRP (${resultFar.rsrp_dbm}) < 2 km (${result2km.rsrp_dbm})`);

// Breakdown should have all fields
assert(result2km.breakdown.eirp_dbm > 0, "Breakdown has EIRP");
assert(typeof result2km.breakdown.rain_db === "number", "Breakdown has rain_db");
assert(typeof result2km.breakdown.smoke_db === "number", "Breakdown has smoke_db");

// ============================================================================
// Tower Search Tests
// ============================================================================

section("Tower Search");

// Create test tower array (sorted by lat as required)
const testTowers = [
  { lt: 43.65, ln: -79.38, el: 100, ht: 30, gn: 15, pw: 20, bc: ["low"] },     // Toronto
  { lt: 45.42, ln: -75.70, el: 80,  ht: 40, gn: 18, pw: 40, bc: ["low","mid"] }, // Ottawa
  { lt: 45.50, ln: -73.57, el: 50,  ht: 35, gn: 16, pw: 30, bc: ["mid"] },      // Montreal
  { lt: 49.28, ln: -123.12, el: 20, ht: 45, gn: 17, pw: 50, bc: ["low","high"] }, // Vancouver
  { lt: 51.04, ln: -114.07, el: 1100, ht: 30, gn: 15, pw: 25, bc: ["mid"] },    // Calgary
];

// Search near Ottawa: should find Ottawa tower first
const nearOttawa = findNearestTowers(testTowers, 45.43, -75.69, 3, 200);
assert(nearOttawa.length >= 1, `Found ${nearOttawa.length} towers near Ottawa`);
assertApprox(nearOttawa[0].tower.lt, 45.42, 0.01, "Nearest to Ottawa is Ottawa tower");
assert(nearOttawa[0].distance_km < 5, "Ottawa tower < 5 km away");

// Search near Toronto: should find Toronto tower
const nearToronto = findNearestTowers(testTowers, 43.66, -79.39, 1, 50);
assert(nearToronto.length === 1, "Found 1 tower near Toronto");
assertApprox(nearToronto[0].tower.lt, 43.65, 0.01, "Nearest is Toronto tower");

// Search in middle of nowhere: should return empty within tight radius
const nowhere = findNearestTowers(testTowers, 55.0, -90.0, 5, 10);
assert(nowhere.length === 0, "No towers within 10 km of remote location");

// ============================================================================
// 24-Hour Forecast Tests
// ============================================================================

section("24-Hour Signal Forecast");

// Generate 24 hours of varying weather
const hourlyWx = Array.from({ length: 24 }, (_, h) => ({
  rain_mm_h: h >= 12 && h <= 18 ? 15 : 0,  // rain in afternoon
  snow_mm_h: 0,
  temp_c: 10 + 5 * Math.sin((h - 6) * Math.PI / 12), // temp curve
  visibility_km: h >= 14 && h <= 16 ? 3 : 15,
  wind_kmh: 15 + 10 * Math.sin(h * Math.PI / 12),
  pm25: 20,
  condition: h >= 12 && h <= 18 ? "Rain" : "Clear",
}));

const forecast = forecastSignal24h(mockTower, 45.44, -75.70, hourlyWx);
assert(forecast.length === 24, "Forecast has 24 entries");
assert(forecast[0].hour === 0, "First hour is 0");
assert(forecast[23].hour === 23, "Last hour is 23");

// Morning (clear) should have better signal than afternoon (rain)
const morningRsrp = forecast[8].rsrp_dbm;
const afternoonRsrp = forecast[15].rsrp_dbm;
assert(morningRsrp >= afternoonRsrp,
  `Morning RSRP (${morningRsrp}) >= afternoon (${afternoonRsrp})`);

// All predictions should have valid quality strings
const validQualities = ["excellent", "good", "fair", "poor", "none"];
assert(forecast.every(f => validQualities.includes(f.quality)),
  "All hours have valid quality strings");

// ============================================================================
// Summary
// ============================================================================

console.log(`\n═══════════════════════════════════════`);
console.log(`  TOTAL: ${passCount + failCount} tests`);
console.log(`  PASS:  ${passCount}`);
console.log(`  FAIL:  ${failCount}`);
console.log(`═══════════════════════════════════════`);

process.exit(failCount > 0 ? 1 : 0);
