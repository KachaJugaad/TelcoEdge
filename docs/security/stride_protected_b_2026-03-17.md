# STRIDE Threat Model — PROTECTED-B Compliance Module

> Module: `src/defence/protected_b.py`
> Date: 2026-03-17
> Classification floor: PROTECTED-B (Canadian government medium sensitivity)
> Reference: Bill C-26 (Critical Cyber Systems Protection Act)

## Spoofing

| Threat | A caller could spoof data classification to bypass PROTECTED-B checks |
|---|---|
| Mitigation | Classification is set at data source, not by caller. All classification changes require audit log entry. Defence device IDs validated (must start with "dnd_"). |

## Tampering

| Threat | Compliance check results could be tampered to show false "compliant" |
|---|---|
| Mitigation | ComplianceResult is immutable dataclass. All violations logged to audit trail. Human approval required for any PROTECTED-B schedule change. |

## Repudiation

| Threat | A user could deny accessing PROTECTED-B data |
|---|---|
| Mitigation | All PROTECTED-B access audit logged (audit_logged=True enforced, no exceptions). Logs written to append-only data/api_logs/. |

## Information Disclosure

| Threat | PROTECTED-B data could leak to non-Canadian infrastructure |
|---|---|
| Mitigation | check_data_flow() validates destination is Canadian. PROTECTED-B data cannot leave Canadian infrastructure. No PROTECTED-B data in plaintext logs. Encryption required in transit. |

## Denial of Service

| Threat | Compliance checks could be overwhelmed to bypass validation |
|---|---|
| Mitigation | Compliance checks are synchronous and lightweight (pure Python, no network calls). No external dependency to attack. |

## Elevation of Privilege

| Threat | A non-defence process could access PROTECTED-B data flows |
|---|---|
| Mitigation | Device ID prefix validation ("dnd_"). Human approval required for all PROTECTED-B scheduling. Defence priority queue is a separate policy class, never inlined with civilian policies. |
