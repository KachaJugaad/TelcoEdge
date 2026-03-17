"""Smoke tests for PROTECTED-B compliance checks.

Validates Canadian PROTECTED-B data flow rules including geographic
restrictions, encryption requirements, and classification handling.
"""
import pytest

from src.defence.protected_b import ComplianceResult, ProtectedBCheck


@pytest.fixture
def checker():
    return ProtectedBCheck()


class TestProtectedBCompliance:
    """PROTECTED-B data flow compliance tests."""

    def test_canadian_destination_passes(self, checker):
        """PROTECTED_B data to a Canadian destination is compliant."""
        result = checker.check_data_flow(
            source="edge-node-toronto",
            destination="ca-central-1",
            data_class="PROTECTED_B",
            encrypted=True,
        )
        assert result.compliant is True
        assert result.violations == []

    def test_us_destination_with_protected_b_fails(self, checker):
        """PROTECTED_B data to a US destination is non-compliant."""
        result = checker.check_data_flow(
            source="edge-node-toronto",
            destination="us-east-1",
            data_class="PROTECTED_B",
            encrypted=True,
        )
        assert result.compliant is False
        assert any("Canadian infrastructure" in v for v in result.violations)

    def test_unencrypted_protected_b_transit_fails(self, checker):
        """PROTECTED_B data in unencrypted transit is non-compliant."""
        result = checker.check_data_flow(
            source="edge-node-ottawa",
            destination="ca-central-1",
            data_class="PROTECTED_B",
            encrypted=False,
        )
        assert result.compliant is False
        assert any("encrypted" in v for v in result.violations)

    def test_unclassified_data_to_us_passes(self, checker):
        """UNCLASSIFIED data to a US destination is compliant."""
        result = checker.check_data_flow(
            source="edge-node-toronto",
            destination="us-east-1",
            data_class="UNCLASSIFIED",
            encrypted=True,
        )
        assert result.compliant is True
        assert result.violations == []

    def test_violations_list_populated_on_failure(self, checker):
        """Violations list is populated with specific failure reasons."""
        result = checker.check_data_flow(
            source="edge-node-toronto",
            destination="eu-west-1",
            data_class="PROTECTED_B",
            encrypted=False,
        )
        assert result.compliant is False
        assert len(result.violations) >= 2  # geo + encryption violations
        assert len(result.recommendations) >= 2
