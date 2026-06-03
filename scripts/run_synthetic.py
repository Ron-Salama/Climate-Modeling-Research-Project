"""Phase 1 smoke test: run the full physics pipeline on synthetic data.

    temperature  ->  anomaly  ->  charge  ->  breakdown field  ->  flagged zones

No downloads, no real data. Produces PNG maps in outputs/phase1/ so you can SEE
each stage, and prints a summary confirming the planted heatwave lights up the
breakdown field.

Run from the repo root:
    python scripts/run_synthetic.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def _in_spyder() -> bool:
    """True when running inside Spyder (so we can show plots inline)."""
    return "spyder_kernels" in sys.modules or bool(os.environ.get("SPY_PYTHONPATH"))


# In Spyder -> inline plots. In a plain terminal -> headless, just save PNGs.
SHOW_PLOTS = _in_spyder()
import matplotlib
if not SHOW_PLOTS:
    matplotlib.use("Agg")

import numpy as np

from climate_capacitor.config import load_config
from climate_capacitor.data.synthetic import make_synthetic
from climate_capacitor.physics import anomaly, breakdown, charge, permittivity
from climate_capacitor.viz.maps import plot_field


def main() -> None:
    cfg = load_config()

    # --- Small, fast synthetic domain for the demo (config knobs still drive
    #     the physics; we just shrink grid+time so it runs in seconds). ---
    domain = dict(cfg["domain"])
    domain["resolution_deg"] = 2.0
    start, end = "2015-01-01", "2016-12-31"

    print(f"Generating synthetic world @ {domain['resolution_deg']} deg, {start}..{end} ...")
    temp, elev, slope, event = make_synthetic(domain, start, end, seed=cfg["run"]["seed"])
    print(f"  temperature cube: {dict(temp.sizes)}")

    # --- Physics pipeline ---
    print("Computing anomaly -> charge -> permittivity -> breakdown ...")
    anom = anomaly.compute_anomaly(temp, smooth_days=cfg["charge"]["climatology_smooth_days"])
    Q = charge.accumulate_charge(
        anom,
        window_days=cfg["charge"]["window_days"],
        decay_per_day=cfg["charge"]["decay_per_day"],
    )
    eps = permittivity.compute_permittivity(elev, slope, cfg["permittivity"])
    eps = eps.rename("permittivity")
    E = breakdown.breakdown_field(Q, eps)
    mask, thr = breakdown.flag_zones(
        E,
        threshold_mode=cfg["breakdown"]["threshold_mode"],
        threshold_value=cfg["breakdown"]["threshold_value"],
    )

    # --- Pick the timestep at the planted event's peak to visualize ---
    peak_t = int(event["peak_doy_index"])
    tsel = temp["time"].values[peak_t]
    tstr = np.datetime_as_string(tsel, unit="D")
    outdir = REPO / cfg["run"]["output_dir"] / "phase1"

    where = "inline (Spyder)" if SHOW_PLOTS else str(outdir)
    print(f"Rendering maps for planted-event peak ({tstr}) -> {where} ...")
    plot_field(temp.isel(time=peak_t), f"Temperature (K) — {tstr}", outdir / "1_temperature.png",
               cmap="inferno", diverging=False, show=SHOW_PLOTS)
    plot_field(anom.isel(time=peak_t), f"Temperature anomaly — {tstr}", outdir / "2_anomaly.png",
               show=SHOW_PLOTS)
    plot_field(Q.isel(time=peak_t), f"Accumulated thermal charge — {tstr}", outdir / "3_charge.png",
               show=SHOW_PLOTS)
    plot_field(eps, "Terrain permittivity (epsilon)", outdir / "4_permittivity.png",
               cmap="viridis", diverging=False, show=SHOW_PLOTS)
    plot_field(E.isel(time=peak_t), f"Breakdown field — {tstr}", outdir / "5_breakdown.png",
               cmap="magma", diverging=False, zones=mask.isel(time=peak_t), show=SHOW_PLOTS)

    # --- Sanity check: does the planted event actually light up? ---
    eblob = E.isel(time=peak_t).sel(
        lat=slice(event["lat"] - 8, event["lat"] + 8),
        lon=slice(event["lon"] - 8, event["lon"] + 8),
    )
    global_E = E.isel(time=peak_t)
    n_flagged = int(mask.isel(time=peak_t).sum())
    print("\n=== Phase 1 summary ===")
    print(f"  breakdown threshold ({cfg['breakdown']['threshold_mode']}): {thr:.4f}")
    print(f"  flagged cells at event peak: {n_flagged}")
    print(f"  max E near planted event:    {float(eblob.max()):.4f}")
    print(f"  median E globally:           {float(global_E.median()):.4f}")
    ratio = float(eblob.max()) / (float(global_E.median()) + 1e-9)
    print(f"  event-peak / global-median:  {ratio:.1f}x  "
          f"({'event stands out [OK]' if ratio > 3 else 'weak signal - tune knobs'})")
    print(f"\nMaps written to: {outdir}")


if __name__ == "__main__":
    main()
