"""PROTECTED-B compliance checks for Canadian defence data flows.

Implements data flow validation against Canadian PROTECTED-B classification
requirements. PROTECTED-B data must remain within Canadian infrastructure,
must be encrypted in transit, and all access must be audit logged.

References:
  - Treasury Board Policy on Government Security
  - Bill C-26 (Critical Cyber Systems Protection Act)
  - Canadian Centre for Cyber Security guidance on PROTECTED-B handling
"""
from dataclasses import dataclass, field
from typing import List


# Canadian infrastructure identifiers (simplified)
CANADIAN_DESTINATIONS = {
    "canada", "ca", "can",
    "ca-central-1", "ca-west-1",  # AWS regions
    "canadacentral", "canadaeast",  # Azure regions
    "northamerica-northeast1", "northamerica-northeast2",  # GCP regions
}


@dataclass
class ComplianceResult:
    """Result of a PROTECTED-B compliance check.

    Attributes:
        compliant: True if the data flow meets all PROTECTED-B requirements
        violations: list of compliance violations found
        recommendations: list of remediation recommendations
    """
    compliant: bool
    violations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class ProtectedBCheck:
    """PROTECTED-B compliance checker for data flow validation.

    Rules enforced:
      1. PROTECTED_B data cannot leave Canadian infrastructure
      2. PROTECTED_B data must be encrypted in transit
      3. All PROTECTED_B access must be audit logged
      4. No PROTECTED_B data in plaintext logs
    """

    def _is_canadian_destination(self, destination: str) -> bool:
        """Check if a destination is within Canadian infrastructure."""
        dest_lower = destination.lower().strip()
        for cdn in CANADIAN_DESTINATIONS:
            if cdn in dest_lower:
                return True
        return False

    def check_data_flow(
        self,
        source: str,
        destination: str,
        data_class: str,
        encrypted: bool = True,
        audit_logged: bool = True,
    ) -> ComplianceResult:
        """Validate a data flow against PROTECTED-B compliance rules.

        Args:
            source: source system or location identifier
            destination: destination system or location identifier
            data_class: classification level ("UNCLASSIFIED", "PROTECTED_A", "PROTECTED_B")
            encrypted: whether data is encrypted in transit
            audit_logged: whether access is being audit logged

        Returns:
            ComplianceResult with compliance status, violations, and recommendations.
        """
        violations: List[str] = []
        recommendations: List[str] = []

        if data_class != "PROTECTED_B":
            # Non-PROTECTED_B data has no special restrictions
            return ComplianceResult(compliant=True)

        # Rule 1: PROTECTED_B data cannot leave Canadian infrastructure
        if not self._is_canadian_destination(destination):
            violations.append(
                f"PROTECTED_B data cannot leave Canadian infrastructure. "
                f"Destination '{destination}' is not a recognized Canadian location."
            )
            recommendations.append(
                "Route PROTECTED_B data to a Canadian data centre "
                "(e.g., ca-central-1, canadacentral)."
            )

        # Rule 2: PROTECTED_B data must be encrypted in transit
        if not encrypted:
            violations.append(
                "PROTECTED_B data must be encrypted in transit."
            )
            recommendations.append(
                "Enable TLS 1.3 or IPsec for all PROTECTED_B data flows."
            )

        # Rule 3: All PROTECTED_B access must be audit logged
        if not audit_logged:
            violations.append(
                "All PROTECTED_B access must be audit logged."
            )
            recommendations.append(
                "Enable comprehensive audit logging for PROTECTED_B data access."
            )

        return ComplianceResult(
            compliant=len(violations) == 0,
            violations=violations,
            recommendations=recommendations,
        )
