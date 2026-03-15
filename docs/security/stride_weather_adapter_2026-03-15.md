# STRIDE Threat Model -- Weather Adapter (MSC GeoMet API Boundary)

> **Date:** 2026-03-15
> **Scope:** `src/adapters/weather_gc_adapter.py` -- the adapter that fetches
> weather observations from the Government of Canada MSC GeoMet OGC API
> (`https://api.weather.gc.ca`).
>
> **Key point:** The MSC GeoMet API is anonymous. There is no API key, no
> OAuth token, no authentication credential of any kind. This eliminates
> credential-theft attack vectors but means responses must be rigorously
> validated since there is no authenticated session to trust.
>
> **Classification reference:** Canadian PROTECTED-B
> **O-RAN reference:** O-RAN E2SM-RC v1.03

---

## 1. Spoofing

**Threat:** An attacker performs a DNS hijack or BGP route injection to
redirect `api.weather.gc.ca` to a malicious server that returns fabricated
weather data (e.g., reporting clear sky during a downpour), causing the
policy engine to skip protective MCS adjustments.

**Mitigation:**
- All requests use HTTPS. The adapter (`WeatherGCAdapter`) relies on Python's
  default SSL context, which validates the TLS certificate against the system
  trust store.
- The `api.weather.gc.ca` TLS certificate is issued by a Government of Canada
  CA -- verify the certificate chain terminates at the expected CA.
- DNS-over-HTTPS (DoH) is recommended for deployment environments to mitigate
  DNS spoofing.

**Residual risk:** Low. No API key to steal. The primary vector is TLS
interception via compromised CA, which is mitigated by standard certificate
validation. Consider certificate pinning for production.

---

## 2. Tampering

**Threat:** API responses are modified in transit (e.g., a proxy strips or
alters the `rain_mm_per_hr` field in the GeoJSON response), causing the
policy engine to receive incorrect weather data.

**Mitigation:**
- HTTPS provides transport-layer integrity -- responses cannot be modified
  without breaking TLS.
- The adapter's `_parse_features()` method validates response structure:
  it checks for `features`, `properties`, and `geometry` keys before
  extracting values.
- Numeric fields are cast via `float()` with `try/except` -- malformed
  values are silently skipped rather than crashing the adapter.
- The adapter checks multiple possible field names for precipitation
  (`precipitation_intensity`, `rain_mm_per_hr`, `precip_amount`, etc.)
  to handle schema variations.

**Residual risk:** Low. The adapter does not currently validate that
precipitation values are within physically plausible bounds (e.g.,
0-300 mm/hr). Consider adding range validation in a future iteration.

---

## 3. Repudiation

**Threat:** A weather API call returns bad data that triggers an incorrect
policy action, but there is no record of what the API actually returned.

**Mitigation:**
- Every API call is logged to `data/api_logs/weather_gc_{ISO_timestamp}.json`
  by the `_log_call()` method.
- Log entries include: request URL, ISO timestamp, service identifier
  (`MSC-GeoMet-OGC-anonymous`), auth method (`none`), and number of
  features returned.
- The `LOG_DIR` path is configurable but defaults to `data/api_logs/`
  relative to the project root.

**Residual risk:** Low. Current logs do not store the full response body
(to save disk space). For PROTECTED-B audit requirements, consider logging
a hash of the response body or storing full responses in a compressed
archive with a retention policy.

---

## 4. Information Disclosure

**Threat:** The adapter leaks sensitive data (cell IDs, RF measurements,
internal network topology) to the external weather API.

**Mitigation:**
- The adapter sends only geographic bounding box coordinates in the
  query string (e.g., `?bbox=-110,49,-101,55`). These are public
  geographic coordinates, not sensitive data.
- No request headers contain internal identifiers, cell IDs, or RF data.
- No `Authorization` header is sent -- the API is anonymous.
- No POST body is sent -- all requests are plain GET.
- No raw RF data leaves Canada. All processing is local.

**Residual risk:** Very low. The bounding box could theoretically reveal
approximate tower locations, but these are already public information
(ISED antenna site registry).

---

## 5. Denial of Service (DoS)

**Threat:** The MSC GeoMet API becomes unavailable due to overload,
maintenance, or network issues, preventing the policy engine from
obtaining weather data for proactive adjustments.

**Mitigation:**
- 3-second base exponential backoff (`BACKOFF_BASE = 3`) on HTTP 429
  or 5xx responses, with up to `MAX_RETRIES = 3` attempts.
- 10-second connection timeout (`TIMEOUT = 10`) prevents indefinite
  blocking on unresponsive endpoints.
- After all retries are exhausted, `WeatherAPIError` is raised. The
  calling policy engine treats this as "no weather data available" and
  falls back to the safe default (no MCS adjustment = clear sky
  assumption).
- Circuit breaker: the retry loop exits cleanly after `MAX_RETRIES`,
  preventing unbounded retry storms.

**Residual risk:** Medium. During a prolonged outage coinciding with
heavy rain, the policy will not proactively adjust MCS. Consider adding
a local cache with a 15-minute TTL that serves the last successful
observation as a fallback.

---

## 6. Elevation of Privilege

**Threat:** An attacker exploits the weather adapter to gain unauthorized
access to the policy engine or RAN control plane.

**Mitigation:**
- The adapter is a read-only client. It makes GET requests and returns
  parsed `WeatherObservation` dataclass objects. It does not execute
  any control actions itself.
- The adapter has no write access to the RAN control plane -- it is
  separated from the E2 interface by the policy evaluation layer.
- There is no authentication to compromise (anonymous API), so there
  are no credentials to escalate.
- Defence cells (`dnd_*`) require human approval for any policy change
  regardless of what weather data the adapter returns.

**Residual risk:** Very low. The adapter is a simple HTTP GET client
with no ability to modify system state beyond logging.

---

## References

- MSC GeoMet OGC API: `https://api.weather.gc.ca` (anonymous, no auth)
- O-RAN E2SM-RC v1.03, Section 7.6 (Control Procedure)
- Canadian PROTECTED-B classification guidelines
- ITU-R P.838-3 (rain attenuation model used by downstream policies)
- OSC RICAPP: j-release-2025 (pinned in specs/versions.lock)

---

*DRAFT -- Requires human security review before operational deployment.*
