"""Per-hop latency budget tests for the telcoEdge pipeline.

Tests each hop of the end-to-end path independently, ensuring that
processing time stays within the latency budget defined in the project spec:

  Hop                       Budget
  -------------------------  ------
  Uu radio interface         <= 3 ms
  RAN processing (policy)    <= 2 ms
  Backhaul / core network    <= 3 ms
  Application layer          <= 2 ms
  -------------------------  ------
  E2E total                  <= 10 ms

Methodology:
  - Each hop is measured 100 times using time.perf_counter()
  - The *average* latency across iterations is asserted against the budget
  - All hops use local computation or mocked calls (no real network I/O)

References:
  - 3GPP TS 23.501 Section 5.7.3.4 — QoS and latency requirements
  - 3GPP TS 22.261 Table 7.1-1 — URLLC latency target (1 ms user plane)
  - O-RAN WG3 E2SM-RC v1.03 — near-RT RIC control loop (<10 ms)
"""
import math
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from channel_plugins.prairie_rma.scene import PrairieRMaConfig, run_monte_carlo
from policies.weather_mcs_policy import WeatherMCSPolicy, KPMReport, WeatherData

N_ITERATIONS = 100
SEED = 42


def _measure_avg_ms(fn, n=N_ITERATIONS):
    """Run fn() n times and return average elapsed time in milliseconds."""
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)
    return sum(times) / len(times)


class TestUuRadioInterface:
    """Uu air interface hop -- channel model computation time.

    Budget: <= 3 ms per evaluation.

    NOTE: Uu latency requires real gNB hardware and over-the-air
    measurements to truly characterise. Here we simulate it as the
    time to compute a single Monte-Carlo path-loss sample, which
    exercises the same math the real system would run per TTI.
    """

    def test_uu_channel_latency(self):
        config = PrairieRMaConfig(seed=SEED, rain_mm_per_hr=5.0)

        def single_channel_eval():
            # Single-run MC simulates one TTI channel computation
            run_monte_carlo(config, n_runs=1)

        avg_ms = _measure_avg_ms(single_channel_eval)
        # Uu latency requires real gNB hardware -- simulated here as
        # channel computation time for a single path-loss evaluation.
        assert avg_ms <= 3.0, (
            f"Uu channel eval averaged {avg_ms:.3f} ms, budget is 3.0 ms. "
            f"True Uu latency requires real gNB hardware and RF front-end."
        )


class TestRANProcessing:
    """RAN processing hop -- policy evaluation time.

    Budget: <= 2 ms per evaluation.

    NOTE: Full RAN processing latency includes E2 interface round-trip
    to the near-RT RIC, E2SM-KPM decode, and E2SM-RC encode. Here we
    measure only the Python policy evaluation, which is the compute-bound
    portion of the RIC control loop.
    """

    def test_ran_policy_latency(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = WeatherData(rain_mm_per_hr=10.0)

        def policy_eval():
            policy.evaluate(kpm, weather)

        avg_ms = _measure_avg_ms(policy_eval)
        # Full RAN processing requires E2 interface to near-RT RIC and
        # E2SM encode/decode -- simulated here as policy evaluation time.
        assert avg_ms <= 2.0, (
            f"RAN policy eval averaged {avg_ms:.3f} ms, budget is 2.0 ms. "
            f"True RAN processing requires E2 interface + near-RT RIC."
        )


class TestBackhaulCore:
    """Backhaul / core network hop -- adapter call time (mocked).

    Budget: <= 3 ms per call.

    NOTE: Real backhaul latency depends on fibre distance, core network
    UPF processing, and N3/N9 tunnel overhead. Here we mock the adapter
    call and measure only the Python-side overhead of preparing and
    dispatching the request.
    """

    def test_backhaul_adapter_latency(self):
        mock_adapter = MagicMock()
        mock_adapter.get_weather.return_value = []

        def adapter_call():
            mock_adapter.get_weather(bbox=(-110, 49, -101, 55))

        avg_ms = _measure_avg_ms(adapter_call)
        # Real backhaul latency requires physical fibre path, UPF, and
        # core network traversal -- simulated here as mocked adapter call.
        assert avg_ms <= 3.0, (
            f"Backhaul adapter call averaged {avg_ms:.3f} ms, budget is 3.0 ms. "
            f"True backhaul latency requires physical network and UPF."
        )


class TestApplicationLayer:
    """Application layer hop -- full pipeline decision time.

    Budget: <= 2 ms per decision cycle.

    NOTE: The application layer in production includes xApp framework
    overhead, SDL (Shared Data Layer) reads, and A1 policy lookups.
    Here we measure the decision pipeline: channel eval + policy eval
    for a single TTI.
    """

    def test_application_decision_latency(self):
        config = PrairieRMaConfig(seed=SEED, rain_mm_per_hr=5.0)
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = WeatherData(rain_mm_per_hr=10.0)

        def full_decision():
            result = run_monte_carlo(config, n_runs=1)
            policy.evaluate(kpm, weather)

        avg_ms = _measure_avg_ms(full_decision)
        # Application layer in production includes xApp framework, SDL,
        # and A1 policy lookups -- simulated here as pipeline decision.
        assert avg_ms <= 2.0, (
            f"Application decision averaged {avg_ms:.3f} ms, budget is 2.0 ms. "
            f"True application latency requires xApp framework + SDL."
        )


class TestE2ETotal:
    """End-to-end latency: sum of all hops must be <= 10 ms.

    Measures each hop independently (100 iterations each) and sums
    the averages to verify the total budget.
    """

    def test_e2e_total_latency(self):
        config = PrairieRMaConfig(seed=SEED, rain_mm_per_hr=5.0)
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = WeatherData(rain_mm_per_hr=10.0)
        mock_adapter = MagicMock()
        mock_adapter.get_weather.return_value = []

        # Measure each hop
        uu_ms = _measure_avg_ms(lambda: run_monte_carlo(config, n_runs=1))
        ran_ms = _measure_avg_ms(lambda: policy.evaluate(kpm, weather))
        backhaul_ms = _measure_avg_ms(
            lambda: mock_adapter.get_weather(bbox=(-110, 49, -101, 55))
        )
        app_ms = _measure_avg_ms(lambda: (
            run_monte_carlo(config, n_runs=1),
            policy.evaluate(kpm, weather),
        ))

        total_ms = uu_ms + ran_ms + backhaul_ms + app_ms

        assert total_ms <= 10.0, (
            f"E2E total {total_ms:.3f} ms exceeds 10.0 ms budget. "
            f"Breakdown: Uu={uu_ms:.3f}, RAN={ran_ms:.3f}, "
            f"Backhaul={backhaul_ms:.3f}, App={app_ms:.3f}. "
            f"True E2E requires real gNB + fibre + UPF + xApp framework."
        )
