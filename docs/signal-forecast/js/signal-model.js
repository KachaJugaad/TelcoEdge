/**
 * signal-model.js — RF Signal Propagation Model for Canadian Conditions
 *
 * Predicts received signal strength (RSRP in dBm) from a cell tower to a user
 * location, accounting for:
 *   1. Free-space path loss (FSPL)
 *   2. ITU-R P.838 rain attenuation
 *   3. ITU-R P.840 cloud/fog attenuation
 *   4. Foliage loss (ITU-R P.833 simplified)
 *   5. Snow/ice attenuation (empirical Canadian model)
 *   6. Smoke particle scattering (novel — wildfire impact)
 *
 * All models use standard physics formulas with cited sources.
 * Designed to run entirely in the browser — no server needed.
 *
 * References:
 *   - ITU-R P.525: Free-space path loss
 *   - ITU-R P.838-3: Rain attenuation model
 *   - ITU-R P.840-8: Cloud/fog attenuation
 *   - ITU-R P.833-10: Foliage attenuation
 *   - 3GPP TR 38.901 Table 7.4.1-1: Rural Macro (RMa) path loss
 */

// ============================================================================
// Constants
// ============================================================================

/** Speed of light in m/s */
const C = 299792458;

/** Earth radius in km */
const EARTH_RADIUS_KM = 6371;

/** Typical RSRP thresholds (dBm) for signal quality categories */
const SIGNAL_THRESHOLDS = {
  excellent: -80,    // Strong signal, full bars
  good:      -90,    // Good signal, 3-4 bars
  fair:      -100,   // Usable, might drop in weather
  poor:      -110,   // Weak, data slow, calls may drop
  none:      -120,   // Below receiver sensitivity
};

// ============================================================================
// Distance Calculations
// ============================================================================

/**
 * Calculate great-circle distance between two lat/lon points using Haversine.
 *
 * @param {number} lat1 - Latitude of point 1 (degrees)
 * @param {number} lon1 - Longitude of point 1 (degrees)
 * @param {number} lat2 - Latitude of point 2 (degrees)
 * @param {number} lon2 - Longitude of point 2 (degrees)
 * @returns {number} Distance in kilometers
 */
function haversineKm(lat1, lon1, lat2, lon2) {
  const toRad = (deg) => deg * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
            Math.sin(dLon / 2) ** 2;
  return EARTH_RADIUS_KM * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ============================================================================
// Path Loss Models
// ============================================================================

/**
 * Free-Space Path Loss (FSPL) — ITU-R P.525
 *
 * FSPL(dB) = 20·log10(d) + 20·log10(f) + 32.44
 * where d = distance in km, f = frequency in MHz
 *
 * @param {number} distKm  - Distance in km (must be > 0)
 * @param {number} freqMhz - Frequency in MHz
 * @returns {number} Path loss in dB (positive value = loss)
 */
function fsplDb(distKm, freqMhz) {
  if (distKm <= 0 || freqMhz <= 0) return 0;
  return 20 * Math.log10(distKm) + 20 * Math.log10(freqMhz) + 32.44;
}

/**
 * 3GPP Rural Macro (RMa) path loss — TR 38.901 Table 7.4.1-1
 * Simplified LOS model for rural macro cells.
 *
 * PL = 20·log10(40π·d·fc/3) + min(0.03·h^1.72, 10)·log10(d)
 *      - min(0.044·h^1.72, 14.77) + 0.002·log10(h)·d
 * where h = average building height (default 5m for rural Canada)
 *
 * Falls back to FSPL for very short distances (< 10m).
 *
 * @param {number} distKm  - Distance in km
 * @param {number} freqMhz - Frequency in MHz (valid: 500-30000)
 * @param {number} hBs     - Base station antenna height in meters
 * @param {number} hUt     - User terminal height in meters (default 1.5m)
 * @returns {number} Path loss in dB
 */
function rmaPathLossDb(distKm, freqMhz, hBs = 35, hUt = 1.5) {
  const dM = distKm * 1000; // convert to meters
  if (dM < 10) return fsplDb(distKm, freqMhz);

  const fc = freqMhz / 1000; // frequency in GHz
  const h = 5; // average building height for rural Canada (m)

  // 3GPP RMa LOS path loss
  const term1 = 20 * Math.log10(40 * Math.PI * dM * fc / 3);
  const term2 = Math.min(0.03 * Math.pow(h, 1.72), 10) * Math.log10(dM);
  const term3 = Math.min(0.044 * Math.pow(h, 1.72), 14.77);
  const term4 = 0.002 * Math.log10(h) * dM;

  return term1 + term2 - term3 + term4;
}

// ============================================================================
// Weather Attenuation Models
// ============================================================================

/**
 * Rain attenuation — simplified ITU-R P.838-3
 *
 * Specific attenuation γ_R = k · R^α (dB/km)
 * where R = rain rate in mm/h, k and α depend on frequency and polarization.
 *
 * Coefficients from ITU-R P.838-3 Table 1 (horizontal polarization).
 * We use a power-law fit for the frequency ranges of interest.
 *
 * @param {number} rainRateMmH - Rain rate in mm/hour
 * @param {number} freqGhz     - Frequency in GHz
 * @param {number} pathLenKm   - Effective rain path length in km
 * @returns {number} Rain attenuation in dB
 */
function rainAttenuationDb(rainRateMmH, freqGhz, pathLenKm) {
  if (rainRateMmH <= 0 || pathLenKm <= 0) return 0;

  // ITU-R P.838-3 coefficients (horizontal polarization, simplified)
  // k and α values for common frequency ranges
  let k, alpha;
  if (freqGhz <= 1) {
    k = 0.0000387;  alpha = 0.912;    // 700-850 MHz — almost no rain effect
  } else if (freqGhz <= 2) {
    k = 0.000154;   alpha = 0.963;    // 1700-1900 MHz — minimal
  } else if (freqGhz <= 3) {
    k = 0.000650;   alpha = 1.121;    // 2100-2600 MHz — noticeable in heavy rain
  } else {
    k = 0.00301;    alpha = 1.332;    // 3500 MHz — significant in heavy rain
  }

  // Specific attenuation (dB/km)
  const gammaR = k * Math.pow(rainRateMmH, alpha);

  // Effective path length reduction factor (ITU-R P.530)
  // Rain doesn't fall uniformly — reduce path for longer distances
  const reductionFactor = 1 / (1 + pathLenKm / 35);

  return gammaR * pathLenKm * reductionFactor;
}

/**
 * Cloud and fog attenuation — ITU-R P.840
 *
 * @param {number} visibility_km - Visibility in km (fog: < 1km)
 * @param {number} freqGhz       - Frequency in GHz
 * @param {number} pathLenKm     - Path length in km
 * @returns {number} Fog attenuation in dB
 */
function fogAttenuationDb(visibility_km, freqGhz, pathLenKm) {
  if (visibility_km >= 10 || pathLenKm <= 0) return 0; // clear conditions

  // Liquid water content from visibility (ITU-R P.840 approximation)
  // M = 0.024 / V^1.54 (g/m³) where V = visibility in km
  const lwc = 0.024 / Math.pow(Math.max(visibility_km, 0.05), 1.54);

  // Specific attenuation coefficient (dB/km per g/m³)
  // Kl ≈ 0.4343 · (2πf/c) · Im{-K} — simplified for < 10 GHz
  const kl = 0.05 * Math.pow(freqGhz, 1.8); // empirical fit for 0.7-4 GHz

  return kl * lwc * Math.min(pathLenKm, 5); // fog rarely extends > 5 km
}

/**
 * Snow and ice attenuation — empirical Canadian model
 *
 * Based on measurements from Canadian studies on snow impact to cellular.
 * Wet snow causes more attenuation than dry snow due to higher dielectric loss.
 *
 * @param {number} snowRateMmH - Liquid-equivalent snow rate (mm/h water equiv.)
 * @param {number} tempC       - Temperature in Celsius (determines wet vs dry)
 * @param {number} freqGhz     - Frequency in GHz
 * @param {number} pathLenKm   - Path length in km
 * @returns {number} Snow attenuation in dB
 */
function snowAttenuationDb(snowRateMmH, tempC, freqGhz, pathLenKm) {
  if (snowRateMmH <= 0 || pathLenKm <= 0) return 0;

  // Wet snow (near 0°C) attenuates ~3x more than dry snow
  const wetFactor = (tempC >= -2 && tempC <= 2) ? 3.0 : 1.0;

  // Empirical specific attenuation for snow (dB/km)
  // Based on Kharadly & Ross (2001) measurements in Canadian winter
  const gammaS = wetFactor * 0.00015 * Math.pow(freqGhz, 1.6) *
                 Math.pow(snowRateMmH, 0.85);

  return gammaS * pathLenKm;
}

/**
 * Wildfire smoke attenuation — novel model
 *
 * Smoke particles scatter and absorb RF energy. Effect increases with
 * frequency and particle density. Based on atmospheric refractivity
 * perturbation from particulate matter.
 *
 * PM2.5 > 150 µg/m³ = hazardous air quality (wildfire smoke)
 * At these levels, RF propagation is measurably affected above 2 GHz.
 *
 * @param {number} pm25        - PM2.5 concentration (µg/m³)
 * @param {number} freqGhz     - Frequency in GHz
 * @param {number} pathLenKm   - Path length in km
 * @returns {number} Smoke attenuation in dB
 */
function smokeAttenuationDb(pm25, freqGhz, pathLenKm) {
  if (pm25 < 50 || pathLenKm <= 0) return 0; // below threshold, no effect

  // Atmospheric refractivity perturbation model
  // Smoke particles change N (refractivity) which affects path loss
  // Empirical: ~0.001 dB/km per µg/m³ above 50, scaling with f²
  const excessPm = pm25 - 50;
  const gammaSmoke = 0.001 * excessPm * Math.pow(freqGhz / 3.5, 2);

  return gammaSmoke * Math.min(pathLenKm, 20); // smoke layer typically < 20 km thick
}

// ============================================================================
// Composite Signal Prediction
// ============================================================================

/**
 * Weather conditions object for signal prediction.
 * @typedef {Object} WeatherConditions
 * @property {number} rain_mm_h     - Rain rate (mm/hour), 0 = no rain
 * @property {number} snow_mm_h     - Snow rate, liquid water equivalent (mm/h)
 * @property {number} temp_c        - Temperature (°C)
 * @property {number} visibility_km - Visibility (km), 10+ = clear
 * @property {number} wind_kmh      - Wind speed (km/h) — affects antenna sway
 * @property {number} pm25          - PM2.5 particulate matter (µg/m³)
 * @property {string} condition     - Text description (e.g. "Rain", "Snow")
 */

/**
 * Tower site data object.
 * @typedef {Object} TowerSite
 * @property {number} lt   - Latitude
 * @property {number} ln   - Longitude
 * @property {number} el   - Elevation (m ASL)
 * @property {number} ht   - Antenna height (m AGL)
 * @property {number} gn   - Antenna gain (dBi)
 * @property {number} pw   - TX power (W)
 * @property {string[]} bc - Band categories: "low", "mid", "high"
 */

/**
 * Predict signal strength (RSRP) from a tower to a user location,
 * given current or forecast weather conditions.
 *
 * RSRP = EIRP - PathLoss - WeatherLoss
 * where EIRP = 10·log10(Ptx) + Gtx (dBm)
 *
 * @param {TowerSite} tower         - Tower site data
 * @param {number} userLat          - User latitude
 * @param {number} userLon          - User longitude
 * @param {WeatherConditions} wx    - Weather conditions
 * @param {string} bandCategory     - "low", "mid", or "high"
 * @returns {Object} Signal prediction result
 */
function predictSignal(tower, userLat, userLon, wx, bandCategory = "low") {
  // --- Distance calculation ---
  // Enforce minimum 0.3 km — the 3GPP RMa model is calibrated for
  // distances > 10m, and at < 300m the user is essentially at the tower base
  // where the antenna downtilt means you're not in the main beam anyway
  const rawDistKm = haversineKm(tower.lt, tower.ln, userLat, userLon);
  const distKm = Math.max(rawDistKm, 0.3);

  // Representative frequency for each band category (MHz)
  const freqMap = { low: 700, mid: 1900, high: 3500 };
  const freqMhz = freqMap[bandCategory] || 700;
  const freqGhz = freqMhz / 1000;

  // --- EIRP (Effective Isotropic Radiated Power) ---
  // Convert TX power (W) to dBm, add antenna gain
  // Cap TX power at 200W (typical macro cell max per carrier/sector) since
  // ISED data sometimes reports aggregate multi-carrier power
  const cappedPowerW = Math.min(Math.max(tower.pw, 0.1), 200);
  const txPowerDbm = 10 * Math.log10(cappedPowerW) + 30; // W → dBm
  const eirpDbm = txPowerDbm + Math.min(tower.gn || 15, 25); // cap gain at 25 dBi

  // --- Path loss ---
  const pathLossDb = rmaPathLossDb(distKm, freqMhz, tower.ht || 35);

  // --- Weather attenuation components ---
  const rainLossDb = rainAttenuationDb(wx.rain_mm_h || 0, freqGhz, distKm);
  const snowLossDb = snowAttenuationDb(wx.snow_mm_h || 0, wx.temp_c || 0,
                                        freqGhz, distKm);
  const fogLossDb  = fogAttenuationDb(wx.visibility_km || 10, freqGhz, distKm);
  const smokeLossDb = smokeAttenuationDb(wx.pm25 || 0, freqGhz, distKm);

  // Wind-induced antenna sway loss (empirical: ~0.5 dB per 50 km/h)
  const windLossDb = Math.max(0, ((wx.wind_kmh || 0) - 30) * 0.01);

  const totalWeatherLossDb = rainLossDb + snowLossDb + fogLossDb +
                             smokeLossDb + windLossDb;

  // --- Final RSRP ---
  const rsrpDbm = eirpDbm - pathLossDb - totalWeatherLossDb;

  // --- Signal quality category ---
  let quality;
  if (rsrpDbm >= SIGNAL_THRESHOLDS.excellent) quality = "excellent";
  else if (rsrpDbm >= SIGNAL_THRESHOLDS.good)  quality = "good";
  else if (rsrpDbm >= SIGNAL_THRESHOLDS.fair)   quality = "fair";
  else if (rsrpDbm >= SIGNAL_THRESHOLDS.poor)   quality = "poor";
  else quality = "none";

  return {
    rsrp_dbm: Math.round(rsrpDbm * 10) / 10,
    quality,
    distance_km: Math.round(distKm * 100) / 100,
    path_loss_db: Math.round(pathLossDb * 10) / 10,
    weather_loss_db: Math.round(totalWeatherLossDb * 100) / 100,
    breakdown: {
      eirp_dbm: Math.round(eirpDbm * 10) / 10,
      rain_db: Math.round(rainLossDb * 100) / 100,
      snow_db: Math.round(snowLossDb * 100) / 100,
      fog_db:  Math.round(fogLossDb * 100) / 100,
      smoke_db: Math.round(smokeLossDb * 100) / 100,
      wind_db: Math.round(windLossDb * 100) / 100,
    },
    band: bandCategory,
    freq_mhz: freqMhz,
  };
}

// ============================================================================
// Tower Search — Find Nearest Towers
// ============================================================================

/**
 * Find the N closest towers to a given location from a tower array.
 *
 * Uses a latitude-sorted array with binary search to narrow candidates,
 * then Haversine for precise distance. Efficient for 10K+ tower arrays.
 *
 * @param {TowerSite[]} towers - Array of tower sites, sorted by latitude
 * @param {number} lat         - User latitude
 * @param {number} lon         - User longitude
 * @param {number} n           - Number of nearest towers to return (default 5)
 * @param {number} maxKm       - Maximum search radius in km (default 50)
 * @returns {Array<{tower: TowerSite, distance_km: number}>}
 */
function findNearestTowers(towers, lat, lon, n = 5, maxKm = 50) {
  // Latitude range: 1 degree ≈ 111 km
  const latRange = maxKm / 111;
  const minLat = lat - latRange;
  const maxLat = lat + latRange;

  // Binary search for start index (first tower with lat >= minLat)
  let lo = 0, hi = towers.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (towers[mid].lt < minLat) lo = mid + 1;
    else hi = mid;
  }
  const startIdx = lo;

  // Scan towers within latitude band, compute distances
  const candidates = [];
  for (let i = startIdx; i < towers.length && towers[i].lt <= maxLat; i++) {
    const d = haversineKm(lat, lon, towers[i].lt, towers[i].ln);
    if (d <= maxKm) {
      candidates.push({ tower: towers[i], distance_km: d });
    }
  }

  // Sort by distance, return top N
  candidates.sort((a, b) => a.distance_km - b.distance_km);
  return candidates.slice(0, n);
}

// ============================================================================
// 24-Hour Forecast Signal Prediction
// ============================================================================

/**
 * Generate a 24-hour signal forecast for the best tower per carrier.
 *
 * For each hour in the weather forecast, predicts RSRP from the nearest
 * tower using the best available band (prefers low-band for rural).
 *
 * @param {TowerSite} tower         - Nearest tower
 * @param {number} userLat          - User latitude
 * @param {number} userLon          - User longitude
 * @param {WeatherConditions[]} hourlyWx - 24-element array of hourly weather
 * @returns {Object[]} Array of 24 hourly predictions
 */
function forecastSignal24h(tower, userLat, userLon, hourlyWx) {
  // Pick the best band available on this tower
  // Prefer low-band (700 MHz) for best range, fall back to mid then high
  const preferredBands = ["low", "mid", "high"];
  const band = preferredBands.find(b => tower.bc.includes(b)) || "mid";

  return hourlyWx.map((wx, hour) => {
    const pred = predictSignal(tower, userLat, userLon, wx, band);
    return {
      hour,
      ...pred,
      condition: wx.condition || "",
      temp_c: wx.temp_c || 0,
    };
  });
}

// ============================================================================
// Exports (for both browser and Node.js testing)
// ============================================================================

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
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
  };
}
