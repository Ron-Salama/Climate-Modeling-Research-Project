"""Phase 2 deliverable: run the full physics pipeline on the REAL Earth.

Same chain as run_synthetic.py (anomaly -> charge -> permittivity -> breakdown),
but fed real ERA5 temperature + real terrain instead of a fabricated world.

    python scripts/run_real.py

Needs the multi-year ERA5 cube cached first (a multi-year climatology is what
makes anomalies meaningful). Produces real-world maps in outputs/phase2_real/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def _in_spyder() -> bool:
    return "spyder_kernels" in sys.modules or bool(os.environ.get("SPY_PYTHONPATH"))


SHOW_PLOTS = _in_spyder()
import matplotlib
if not SHOW_PLOTS:
    matplotlib.use("Agg")

import numpy as np

from climate_capacitor.config import load_config
from climate_capacitor.data.era5 import load_era5
from climate_capacitor.data.topography import load_topography
from climate_capacitor.physics import anomaly, breakdown, charge, permittivity
from climate_capacitor.viz.maps import plot_field

# A day to visualize. 2010-08-05 sits in the famous 2010 Russian heatwave.
SHOW_DATE = "2010-08-05"


def main() -> None:
    cfg = load_config()
    start, end = cfg["time"]["start"], cfg["time"]["end"]

    print(f"Loading real ERA5 {start}..{end} (cache if available) ...")
    temp = load_era5(cfg, start, end)
    print(f"  temperature cube: {dict(temp.sizes)}")

    print("Loading real terrain ...")
    topo = load_topography(cfg)

    print("Running anomaly -> charge -> permittivity -> breakdown ...")
    anom = anomaly.compute_anomaly(temp, smooth_days=cfg["charge"]["climatology_smooth_days"])
    Q = charge.accumulate_charge(anom, cfg["charge"]["window_days"], cfg["charge"]["decay_per_day"])
    eps = permittivity.compute_permittivity(topo["elevation"], topo["slope"], cfg["permittivity"])
    E = breakdown.breakdown_field(Q, eps)
    mask, thr = breakdown.flag_zones(E, cfg["breakdown"]["threshold_mode"],
                                     cfg["breakdown"]["threshold_value"])

    outdir = REPO / cfg["run"]["output_dir"] / "phase2_real"
    print(f"Rendering real-Earth maps for {SHOW_DATE} -> {outdir} ...")
    plot_field(temp.sel(time=SHOW_DATE), f"ERA5 temperature (K) — {SHOW_DATE}",
               outdir / "1_temperature.png", cmap="inferno", diverging=False, show=SHOW_PLOTS)
    plot_field(anom.sel(time=SHOW_DATE), f"Temperature anomaly — {SHOW_DATE}",
               outdir / "2_anomaly.png", show=SHOW_PLOTS)
    plot_field(Q.sel(time=SHOW_DATE), f"Accumulated thermal charge — {SHOW_DATE}",
               outdir / "3_charge.png", show=SHOW_PLOTS)
    plot_field(eps, "Terrain permittivity (epsilon)", outdir / "4_permittivity.png",
               cmap="viridis", diverging=False, show=SHOW_PLOTS)
    plot_field(E.sel(time=SHOW_DATE), f"Breakdown field — {SHOW_DATE}",
               outdir / "5_breakdown.png", cmap="magma", diverging=False,
               zones=mask.sel(time=SHOW_DATE), show=SHOW_PLOTS)

    print("\n=== Phase 2 real-Earth summary ===")
    print(f"  breakdown threshold: {thr:.4f}")
    print(f"  flagged cells on {SHOW_DATE}: {int(mask.sel(time=SHOW_DATE).sum())}")
    print(f"  maps -> {outdir}")


if __name__ == "__main__":
    main()
