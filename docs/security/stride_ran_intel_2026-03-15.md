# STRIDE Threat Model -- RAN-Intel Map-to-API Boundaries

> **Date:** 2026-03-15
> **Scope:** RAN-Intel live map platform (`src/ran_intel/app.py`) and its
> boundary with the MSC GeoMet weather API (`api.weather.gc.ca`),
> the O-RAN E2 interface, and downstream policy engines.
>
> **Classification reference:** Canadian PROTECTED-B
> **O-RAN reference:** O-RAN E2SM-RC v1.03

---

## 1. Spoofing

**Threat:** Weather API responses from `api.weather.gc.ca` could be spoofed by
a man-in-the-middle attacker, feeding false precipitation data into the policy
engine and causing incorrect MCS or beam adjustments.

**Mitigation:**
- All requests to `api.weather.gc.ca` use HTTPS (TLS 1.2+).
- Verify the TLS certificate chain terminates at a Government of Canada CA.
- The `WeatherGCAdapter` (`src/adapters/weather_gc_adapter.py`) uses Python's
  default `ssl` context which validates the server certificate.
- RAN-Intel `/api/weather` proxy endpoint (`src/ran_intel/app.py`) uses
  `httpx.AsyncClient` with default TLS verification enabled.

**Residual risk:** Low. Certificate pinning is not currently implemented; a
compromised CA could still allow spoofing. Consider adding certificate pinning
in Phase 2 if the deployment moves to PROTECTED-B operational status.

---

## 2. Tampering

**Threat:** Policy decisions (MCS drop, beam widening) could be tampered with
in transit between the xApp and the E2 Node (gNB/eNB), causing the RAN to
apply incorrect radio parameters.

**Mitigation:**
- The O-RAN E2 interface provides integrity protection per O-RAN E2SM-RC v1.03,
  Section 7.6.
- E2 Control Request messages carry an integrity check value that the E2 Node
  validates before applying any control action.
- All policy objects (`RCControlAction`, `BeamControlAction`) are immutable
  dataclasses with validation in `__post_init__` to reject out-of-range values
  before they reach the E2 interface.

**Residual risk:** Medium. E2 integrity depends on the near-RT RIC platform
configuration. Verify that the OSC RIC j-release-2025 deployment enables E2AP
integrity protection. Recommend human audit of RIC deployment configuration.

---

## 3. Repudiation

**Threat:** A malicious actor or software defect triggers a policy action
(e.g., MCS drop on a defence cell) but there is no audit trail to trace
the cause.

**Mitigation:**
- Every API call to `api.weather.gc.ca` is logged to `data/api_logs/` with
  timestamp, URL, and response metadata (`WeatherGCAdapter._log_call()`).
- Logs follow the naming convention `weather_gc_{ISO_timestamp}.json`.
- Policy evaluation results (action taken, reason string, cell ID, weather
  input) are captured in benchmark reports under `reports/`.
- All `RCControlAction` and `BeamControlAction` objects carry a `reason`
  field that documents why the action was triggered.

**Residual risk:** Low. Current logging is file-based. For production
PROTECTED-B deployment, integrate with a centralized, tamper-evident log
aggregator (e.g., SIEM).

---

## 4. Information Disclosure

**Threat:** Raw RF measurement data (KPM reports, path loss values, cell IDs)
could leak outside Canadian jurisdiction, violating data sovereignty
requirements.

**Mitigation:**
- No raw RF data leaves Canada. All channel simulation and policy evaluation
  runs locally within the deployment boundary.
- The only external network call is to `api.weather.gc.ca`, which is a
  Government of Canada service hosted within Canada.
- Weather adapter requests contain only geographic bounding boxes (public
  coordinate data), not RF measurements or cell identifiers.
- Channel plugins (`src/channel_plugins/`) process all path loss data locally
  and write results only to local `reports/` and `data/` directories.
- Defence cells (`dnd_*`) are handled by a separate priority queue policy
  (planned Phase 3) with additional access controls.

**Residual risk:** Low. Verify at deployment time that no third-party
analytics or telemetry libraries are included that could exfiltrate data.

---

## 5. Denial of Service (DoS)

**Threat:** The MSC GeoMet weather API becomes unavailable (rate-limited,
overloaded, or network partition), causing the policy engine to stall or
make decisions without weather context.

**Mitigation:**
- 3-second exponential backoff on HTTP 429 or 5xx responses, up to 3 retries
  (`WeatherGCAdapter._get_with_retry()`).
- Circuit breaker pattern: after `MAX_RETRIES` (3) consecutive failures,
  raise `WeatherAPIError` and fall back to cached/default weather data.
- Policy engine treats missing weather data as "clear sky" (no action),
  which is the safe default -- it does not degrade service, it simply
  forgoes the proactive MCS adjustment.
- 10-second connection timeout prevents hanging on unresponsive endpoints.

**Residual risk:** Medium. A prolonged API outage during heavy rain would
cause the policy to miss proactive adjustments. Consider adding a local
weather data cache with a 15-minute TTL in Phase 2.

---

## 6. Elevation of Privilege

**Threat:** An attacker or software defect escalates from weather-triggered
policy actions to overriding defence cell (`dnd_*`) radio parameters without
authorization.

**Mitigation:**
- Defence cells (`dnd_*`) require explicit human approval for any policy
  change. The `BeamControlAction.requires_human_review` flag is set for
  high-wind scenarios, and the planned `dnd_priority_queue.py` (Phase 3)
  will enforce mandatory human-in-the-loop approval.
- Policy classes are scoped per vertical -- `WeatherMCSPolicy` and
  `BeamAdaptationPolicy` cannot address cells outside their configured
  scope.
- MCS and beam parameter ranges are hard-clamped by dataclass validation:
  MCS 0-28 (3GPP TS 38.214), beam step 0-3, tilt 0-15 degrees.

**Residual risk:** Medium. The `dnd_priority_queue.py` policy is not yet
implemented (Phase 3). Until then, defence cells must be excluded from
the automated policy scope via RIC subscription filtering.

---

## References

- O-RAN E2SM-RC v1.03, Section 7.6 (Control Procedure)
- O-RAN E2SM-KPM v3.0, Table 7.4.3-1
- 3GPP TS 38.214 Table 5.1.3.1-1 (MCS index table)
- Canadian PROTECTED-B classification guidelines
- ITU-R P.838-3 (rain attenuation)
- OSC RICAPP: j-release-2025 (pinned in specs/versions.lock)

---

*DRAFT -- Requires human security review before operational deployment.*
