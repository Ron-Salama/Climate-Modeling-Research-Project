"""Edge-case sweep: compare daily statistic (mean vs max vs min) against disasters.

Runs the full 1.5deg pipeline once per statistic (pulling the max/min cubes on
first use, then cached) and validates each against GDIS disasters. Light + safe:
~2 GB per run, one at a time.

    python scripts/run_stat_sweep.py
"""
from __future__ import annotations
import os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import warnings; warnings.filterwarnings("ignore")
from climate_capacitor.util import lower_priority; lower_priority()
import matplotlib; matplotlib.use("Agg")

from climate_capacitor.config import load_config
from climate_capacitor.pipeline import run_pipeline
from climate_capacitor.data.disasters import load_disasters
from climate_capacitor.analysis import validation

STATS = ["mean", "max", "min"]
RADII = [100, 250, 500]


def main() -> None:
    cfg = load_config()
    dis = load_disasters(cfg)
    dis = dis[(dis.date_start >= cfg["time"]["start"]) & (dis.date_start <= cfg["time"]["end"])]
    print(f"disasters in window: {len(dis)}\n")

    print(f"{'daily stat':>10} {'#events':>8}  " + "  ".join(f"r{r}km: rec%/prec%/p" for r in RADII))
    print("-" * 78)
    for stat in STATS:
        cfg["data"]["era5"]["daily_statistic"] = stat
        print(f"[{stat}] loading/aggregating (first max/min pull downloads once)...", flush=True)
        res = run_pipeline(cfg, verbose=False, keep_temp=False)
        cat = res["catalog"]
        cells = []
        for radius in RADII:
            r = validation.validate(cat, dis, cfg, radius_km=radius)
            cells.append(f"{r['recall']*100:4.2f}/{r['precision']*100:4.2f}/{r['p_value']:.0e}")
        print(f"{stat:>10} {len(cat):8d}  " + "  ".join(f"{c:>18}" for c in cells), flush=True)

    print("\nRead: recall% / precision% / p-value at each match radius.")
    print("If max/min don't beat mean, the choice of daily statistic doesn't rescue the model.")


if __name__ == "__main__":
    main()
