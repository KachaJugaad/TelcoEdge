#!/usr/bin/env python3
"""Update the CanEdge test dashboard with latest benchmark + test results.

Reads reports/latest_benchmark.json, runs pytest to collect test results,
and generates docs/canedge-testview.html.

Standalone: python tools/update_dashboard.py
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_FILE = ROOT / "reports" / "latest_benchmark.json"
DASHBOARD_FILE = ROOT / "docs" / "canedge-testview.html"
PHASE_FILE = ROOT / ".canedge" / "phase_status.json"


def load_benchmark():
    if not BENCHMARK_FILE.exists():
        print("FAIL: reports/latest_benchmark.json not found — run benchmark first")
        sys.exit(1)
    return json.loads(BENCHMARK_FILE.read_text())


def load_phase():
    if PHASE_FILE.exists():
        return json.loads(PHASE_FILE.read_text())
    return {"phase": "unknown", "pct_complete": 0}


def run_tests():
    """Run pytest and parse results per module."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=no"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    output = result.stdout
    modules = {}
    for line in output.splitlines():
        if "::" in line and ("PASSED" in line or "FAILED" in line):
            path_part = line.split("::")[0].strip()
            status = "PASSED" if "PASSED" in line else "FAILED"
            if path_part not in modules:
                modules[path_part] = {"passed": 0, "failed": 0, "tests": []}
            if status == "PASSED":
                modules[path_part]["passed"] += 1
            else:
                modules[path_part]["failed"] += 1
            test_name = line.split("::")[-1].split(" ")[0]
            modules[path_part]["tests"].append({"name": test_name, "status": status})

    total_passed = sum(m["passed"] for m in modules.values())
    total_failed = sum(m["failed"] for m in modules.values())
    return {
        "modules": modules,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total": total_passed + total_failed,
        "all_green": total_failed == 0,
        "returncode": result.returncode,
    }


def generate_html(benchmark: dict, phase: dict, test_results: dict) -> str:
    improved = benchmark.get("ber_improvement_pct", 0)
    status_color = "#27ae60" if benchmark.get("adaptive_is_better") else "#e74c3c"
    status_text = "PASS" if benchmark.get("adaptive_is_better") else "FAIL"
    pipeline_color = "#27ae60" if test_results["all_green"] else "#e74c3c"
    pipeline_text = "ALL GREEN" if test_results["all_green"] else f"{test_results['total_failed']} FAILING"

    # Build test module rows
    module_rows = ""
    for path, data in sorted(test_results["modules"].items()):
        short = path.replace("tests/", "")
        count = data["passed"] + data["failed"]
        if data["failed"] == 0:
            badge = f'<span style="color:#27ae60">&#10003; {count}/{count}</span>'
        else:
            badge = f'<span style="color:#e74c3c">&#10007; {data["passed"]}/{count}</span>'
        module_rows += f"      <tr><td>{short}</td><td>{badge}</td></tr>\n"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CanEdge AI-RAN — Test Dashboard</title>
<style>
  body {{ font-family: 'Courier New', monospace; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 20px; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }}
  h2 {{ color: #ff6b35; margin-top: 30px; }}
  .card {{ background: #16213e; border: 1px solid #0f3460; border-radius: 8px; padding: 20px; margin: 15px 0; }}
  .metric {{ display: inline-block; width: 200px; margin: 10px; text-align: center; }}
  .metric .value {{ font-size: 2em; font-weight: bold; color: #00d4ff; }}
  .metric .label {{ font-size: 0.85em; color: #888; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #0f3460; }}
  th {{ color: #00d4ff; }}
  .refs {{ font-size: 0.85em; color: #888; }}
  .footer {{ margin-top: 40px; padding-top: 10px; border-top: 1px solid #333; font-size: 0.8em; color: #555; }}
  .big-status {{ font-size: 1.4em; font-weight: bold; padding: 8px 20px; border-radius: 6px; display: inline-block; }}
</style>
</head>
<body>
<div class="container">
  <h1>CanEdge AI-RAN — Test Dashboard</h1>
  <p>Phase {phase.get('phase', '?')} — {phase.get('pct_complete', 0)}% complete
  | Next: {phase.get('next_demo', 'N/A')}</p>

  <h2>Pipeline Status</h2>
  <div class="card" style="text-align: center;">
    <div class="big-status" style="background: {pipeline_color}; color: white;">
      {pipeline_text} — {test_results['total_passed']}/{test_results['total']} tests passed
    </div>
  </div>

  <h2>Test Results by Module</h2>
  <div class="card">
    <table>
      <tr><th>Module</th><th>Status</th></tr>
{module_rows}    </table>
  </div>

  <h2>Benchmark: Adaptive MCS vs Fixed</h2>
  <div class="card">
    <div class="metric">
      <div class="value">{improved:.1f}%</div>
      <div class="label">BER Improvement</div>
    </div>
    <div class="metric">
      <div class="value">{benchmark['n_runs']}</div>
      <div class="label">Monte-Carlo Runs</div>
    </div>
    <div class="metric">
      <div class="value" style="color: {status_color}">{status_text}</div>
      <div class="label">Adaptive vs Fixed</div>
    </div>
    <div class="metric">
      <div class="value">{benchmark.get('pl_mean_db', 0):.1f}</div>
      <div class="label">Mean PL (dB)</div>
    </div>
  </div>

  <h2>Scenario Details</h2>
  <div class="card">
    <table>
      <tr><th>Parameter</th><th>Value</th></tr>
      <tr><td>Terrain</td><td>{benchmark.get('terrain_type', 'N/A')}</td></tr>
      <tr><td>Weather</td><td>{benchmark.get('weather_condition', 'N/A')}</td></tr>
      <tr><td>Frequency</td><td>3.5 GHz (mid-band 5G)</td></tr>
      <tr><td>TX Power</td><td>{benchmark.get('tx_power_dbm', 0)} dBm</td></tr>
      <tr><td>Bandwidth</td><td>{benchmark.get('bandwidth_mhz', 0)} MHz</td></tr>
      <tr><td>Fixed MCS</td><td>{benchmark.get('fixed_mcs', 'N/A')}</td></tr>
      <tr><td>Adaptive MCS (rain)</td><td>{benchmark.get('adaptive_mcs_when_rain', 'N/A')}</td></tr>
      <tr><td>Rain Intensity</td><td>{benchmark.get('rain_mm_per_hr', 0)} mm/hr</td></tr>
    </table>
  </div>

  <h2>BER Results</h2>
  <div class="card">
    <table>
      <tr><th>Metric</th><th>Fixed MCS</th><th>Adaptive MCS</th></tr>
      <tr>
        <td>Mean BER</td>
        <td>{benchmark.get('mean_ber_fixed_mcs', 0):.4e}</td>
        <td>{benchmark.get('mean_ber_adaptive_mcs', 0):.4e}</td>
      </tr>
      <tr>
        <td>Path Loss (mean)</td>
        <td colspan="2">{benchmark.get('pl_mean_db', 0):.1f} dB +/- {benchmark.get('pl_std_db', 0):.1f}</td>
      </tr>
    </table>
  </div>

  <h2>Spec References</h2>
  <div class="card refs">
    <ul>
      {"".join(f"<li>{ref}</li>" for ref in benchmark.get('spec_references', []))}
    </ul>
  </div>

  <div class="footer">
    Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    | Weather API: MSC GeoMet (anonymous, no key)
    | Seed: {benchmark.get('seed', 'N/A')}
    <br>Benchmark claims require legal review before external use (Rule R-9)
  </div>
</div>
</body>
</html>"""


def main():
    print("Running test suite...")
    test_results = run_tests()
    benchmark = load_benchmark()
    phase = load_phase()
    html = generate_html(benchmark, phase, test_results)

    DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_FILE.write_text(html)

    print(f"\nDashboard update summary:")
    print(f"  Tests:       {test_results['total_passed']}/{test_results['total']} passed"
          f" ({'ALL GREEN' if test_results['all_green'] else 'FAILURES DETECTED'})")
    print(f"  Modules:     {len(test_results['modules'])}")
    print(f"  Benchmark:   {benchmark.get('ber_improvement_pct', 0):.1f}% BER improvement")
    print(f"  Phase:       {phase.get('phase', '?')} ({phase.get('pct_complete', 0)}%)")
    print(f"  Output:      docs/canedge-testview.html")
    print(f"PASS: dashboard updated")


if __name__ == "__main__":
    main()
