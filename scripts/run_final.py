"""Final run: 0.7deg pipeline ONCE, then sweep spatial radius x temporal lookback.

The expensive pipeline runs a single time; validation (cheap) is repeated across
match radii and early-warning lookbacks, so you get a whole grid of recall /
precision numbers from one heavy run.

    python scripts/run_final.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import warnings
warnings.filterwarnings("ignore")

from climate_capacitor.util import lower_priority
lower_priority()

import matplotlib
matplotlib.use("Agg")
import numpy as np

from climate_capacitor.config import load_config
from climate_capacitor.pipeline import run_pipeline
from climate_capacitor.data.disasters import load_disasters
from climate_capacitor.analysis import validation

RADII = [100, 250, 500]          # km
LOOKBACKS = [2, 7, 15, 30]       # days of early-warning lead time
LOOKAHEAD = 2                    # days after the disaster still tolerated


def main() -> None:
    cfg = load_config()
    print(f"=== FINAL RUN @ {cfg['domain']['resolution_deg']} deg, eps_min {cfg['permittivity']['eps_min']} ===")
    res = run_pipeline(cfg, verbose=True, keep_temp=False)
    cat = res["catalog"]
    dis = load_disasters(cfg)
    dis = dis[(dis.date_start >= cfg["time"]["start"]) & (dis.date_start <= cfg["time"]["end"])]
    print(f"\npredicted events: {len(cat)}   disaster-locations: {len(dis)}")

    # --- recall% grid (rows = radius, cols = lookback) ---
    print("\nRECALL %  (rows = match radius km, cols = lookback days)")
    print("         " + "".join(f"{lb:>9}d" for lb in LOOKBACKS))
    best = (0.0, None)
    grid = {}
    for radius in RADII:
        cells = []
        for lb in LOOKBACKS:
            r = validation.validate(cat, dis, cfg, radius_km=radius,
                                    lookback_days=lb, lookahead_days=LOOKAHEAD)
            grid[(radius, lb)] = r
            cells.append(f"{r['recall']*100:8.2f}")
            if r["recall"] > best[0]:
                best = (r["recall"], (radius, lb))
        print(f"{radius:6d}km " + "".join(f"{c:>10}" for c in cells))

    # --- precision% grid ---
    print("\nPRECISION %  (rows = radius, cols = lookback)")
    print("         " + "".join(f"{lb:>9}d" for lb in LOOKBACKS))
    for radius in RADII:
        cells = [f"{grid[(radius, lb)]['precision']*100:8.2f}" for lb in LOOKBACKS]
        print(f"{radius:6d}km " + "".join(f"{c:>10}" for c in cells))

    # --- best cell detail ---
    br, bl = best[1]
    rb = grid[(br, bl)]
    s = cfg["validation"]["success"]
    print(f"\nBest recall: {rb['recall']*100:.2f}% at radius {br}km / lookback {bl}d "
          f"(precision {rb['precision']*100:.2f}%, p={rb['p_value']:.1e})")
    print(f"Targets: recall>{s['min_recall']*100:.0f}%  precision>{s['min_precision']*100:.0f}%  p<{s['max_pvalue']}")
    print("Note: wider lookback mechanically raises recall (more time to overlap);")
    print("      the p-value's null already accounts for the window span.")

    outdir = REPO / cfg["run"]["output_dir"] / "final"
    outdir.mkdir(parents=True, exist_ok=True)
    cat.to_csv(outdir / "predicted_events_0p7.csv", index=False)
    print(f"\ncatalog -> {outdir / 'predicted_events_0p7.csv'}")


if __name__ == "__main__":
    main()
