"""Phase 3: run the full pipeline on real data and print the event catalog.

    python scripts/run_detect.py

Saves the catalog to outputs/phase3/predicted_events.csv and prints the
strongest predicted events with their inception point and trigger type.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import warnings
warnings.filterwarnings("ignore")

from climate_capacitor.config import load_config
from climate_capacitor.pipeline import run_pipeline


def main() -> None:
    cfg = load_config()
    res = run_pipeline(cfg)
    cat = res["catalog"]

    outdir = REPO / cfg["run"]["output_dir"] / "phase3"
    outdir.mkdir(parents=True, exist_ok=True)
    cat.to_csv(outdir / "predicted_events.csv", index=False)

    print("\n=== Predicted event catalog (top 15 by peak stress) ===")
    cols = ["event_id", "date_start", "duration_days", "incept_lat", "incept_lon",
            "peak_E", "max_cells", "trigger"]
    with_pd_opts(lambda: print(cat[cols].head(15).to_string(index=False)))

    print(f"\n  total predicted events: {len(cat)}")
    print(f"  heat-driven: {(cat.trigger=='heat-driven').sum()}  |  "
          f"terrain-driven: {(cat.trigger=='terrain-driven').sum()}")
    print(f"  saved -> {outdir / 'predicted_events.csv'}")


def with_pd_opts(fn):
    import pandas as pd
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        fn()


if __name__ == "__main__":
    main()
