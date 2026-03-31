#!/usr/bin/env node
/**
 * test-postal-lookup.js — Tests for Canadian postal code geocoder
 *
 * Validates FSA lookup accuracy and edge case handling.
 *
 * Run: node tests/test-postal-lookup.js
 */

const { postalToCoords, FSA_COORDS, PROVINCE_FALLBACK } = require("../js/postal-lookup.js");

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
// Valid Postal Codes
// ============================================================================

section("Valid Postal Code Lookups");

// Ottawa — Parliament Hill
const ottawa = postalToCoords("K1A 0B1");
assert(ottawa !== null, "K1A 0B1 resolves");
assert(Math.abs(ottawa.lat - 45.42) < 0.1, `Ottawa lat ≈ 45.42 (got ${ottawa.lat})`);
assert(Math.abs(ottawa.lon - (-75.70)) < 0.1, `Ottawa lon ≈ -75.70 (got ${ottawa.lon})`);
assert(ottawa.fsa === "K1A", "FSA = K1A");
assert(ottawa.accuracy.includes("FSA"), "Accuracy mentions FSA");

// Toronto — CN Tower area
const toronto = postalToCoords("M5V3L9");
assert(toronto !== null, "M5V3L9 resolves (no space)");
assert(Math.abs(toronto.lat - 43.64) < 0.1, `Toronto lat ≈ 43.64 (got ${toronto.lat})`);

// Montreal
const montreal = postalToCoords("H3A 0G4");
assert(montreal !== null, "H3A 0G4 resolves");
assert(Math.abs(montreal.lat - 45.50) < 0.1, `Montreal lat ≈ 45.50 (got ${montreal.lat})`);

// Vancouver
const vancouver = postalToCoords("V6B 1A1");
assert(vancouver !== null, "V6B 1A1 resolves");
assert(Math.abs(vancouver.lat - 49.28) < 0.1, `Vancouver lat ≈ 49.28 (got ${vancouver.lat})`);

// Calgary
const calgary = postalToCoords("T2P 1J9");
assert(calgary !== null, "T2P 1J9 resolves");
assert(Math.abs(calgary.lat - 51.05) < 0.1, `Calgary lat ≈ 51.05 (got ${calgary.lat})`);

// Halifax
const halifax = postalToCoords("B3J 1S9");
assert(halifax !== null, "B3J resolves");

// Lowercase input
const lower = postalToCoords("k1a 0b1");
assert(lower !== null, "Lowercase input works");
assert(lower.fsa === "K1A", "Uppercase normalization");

// ============================================================================
// Province Fallback
// ============================================================================

section("Province Fallback for Unknown FSAs");

// Unknown FSA in known province
const unknownFsa = postalToCoords("K9Z 0A0");
assert(unknownFsa !== null, "Unknown FSA K9Z still resolves");
assert(unknownFsa.accuracy.includes("Province"), "Falls back to province centroid");
assert(Math.abs(unknownFsa.lat - 45.42) < 1, "Province fallback gives Ontario coords");

// Yukon
const yukon = postalToCoords("Y1A 1A1");
assert(yukon !== null, "Yukon Y1A resolves");
assert(yukon.lat > 60, `Yukon lat > 60 (got ${yukon.lat})`);

// NWT
const nwt = postalToCoords("X1A 1A1");
assert(nwt !== null, "NWT X1A resolves");
assert(nwt.lat > 60, `NWT lat > 60 (got ${nwt.lat})`);

// ============================================================================
// Edge Cases
// ============================================================================

section("Edge Cases");

assert(postalToCoords("") === null, "Empty string → null");
assert(postalToCoords("123") === null, "Numeric only → null");
assert(postalToCoords("ABCDEF") === null, "All alpha → null");
assert(postalToCoords(null) === null, "null → null");
assert(postalToCoords(undefined) === null, "undefined → null");
assert(postalToCoords("K") === null, "Single char → null");
assert(postalToCoords("90210") === null, "US ZIP → null");

// ============================================================================
// Coverage Check
// ============================================================================

section("FSA Table Coverage");

const totalFSAs = Object.keys(FSA_COORDS).length;
assert(totalFSAs >= 400, `FSA table has ${totalFSAs} entries (≥ 400)`);

const provinces = Object.keys(PROVINCE_FALLBACK).length;
assert(provinces >= 15, `Province fallback covers ${provinces} provinces (≥ 15)`);

// Every FSA should have valid Canadian coordinates
let invalidCoords = 0;
for (const [fsa, [lat, lon]] of Object.entries(FSA_COORDS)) {
  if (lat < 41 || lat > 84 || lon < -141 || lon > -52) {
    invalidCoords++;
    console.error(`    Invalid coords for ${fsa}: [${lat}, ${lon}]`);
  }
}
assert(invalidCoords === 0, `All FSA coordinates are valid Canadian (${invalidCoords} invalid)`);

// ============================================================================
// Summary
// ============================================================================

console.log(`\n═══════════════════════════════════════`);
console.log(`  TOTAL: ${passCount + failCount} tests`);
console.log(`  PASS:  ${passCount}`);
console.log(`  FAIL:  ${failCount}`);
console.log(`═══════════════════════════════════════`);

process.exit(failCount > 0 ? 1 : 0);
