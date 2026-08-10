# verify_move1_qc_pressure_grad_2026-08-10.py
# FRAGO MOVE-1 smoke test — run after edits, before commit.
# Expectations encoded from the FRAGO: None propagation, legit-zero preserved,
# first-turn defaults unchanged, empty-trajectory -> None, grad key present.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import py_compile
import dewey_pipeline as dp

py_compile.compile("app.py", doraise=True)
py_compile.compile("dewey_pipeline.py", doraise=True)
print("COMPILE_OK")

r1 = dp.compute_envelope_metrics(
    {"qc_envelope": {}},
    {"qc_envelope": {"qc_pressure": 0.3, "qc_stability": 0.9, "qc_drift": 0.1}},
)
print("missing->", r1)
assert r1 == {"stability_trend": None, "drift_trend": None, "pressure_trend": None}, r1

r2 = dp.compute_envelope_metrics(
    {"qc_envelope": {"qc_pressure": 0.0, "qc_stability": 0.8, "qc_drift": 0.2}},
    {"qc_envelope": {"qc_pressure": 0.0, "qc_stability": 0.8, "qc_drift": 0.2}},
)
print("legit0 ->", r2)
assert r2 == {"stability_trend": 0.0, "drift_trend": 0.0, "pressure_trend": 0.0}, r2

r3 = dp.compute_envelope_metrics(None, {"qc_envelope": {}})
print("first  ->", r3)
assert r3 == {"stability_trend": 0.0, "drift_trend": 0.0, "pressure_trend": 0.0}, r3

steps, summary = dp.generate_trajectory([], 0, [])
print("empty  ->", steps, summary["pressure_score"], summary["stability_score"])
assert steps == [] and summary["pressure_score"] is None
assert summary["stability_score"] == 0.0 and summary["drift_score"] == 0.0

v, qc, dom = dp.step_state_forward([], [])
print("emptyfw->", qc)
assert qc["qc_pressure_grad"] is None and qc["qc_pressure"] == 0.0

print("ALL_5_PASS")
