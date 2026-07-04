"""Full-scope sweep: resolution x disaster-type x prediction-budget.

Runs the (expensive) pipeline ONCE per resolution, then sweeps the cheap knobs
(disaster type, prediction budget) and validates each. Prints one big table and
the best configuration. Also saves outputs/full_scope_results.csv.

    python scripts/run_all_full_scope.py

NOTE: the first run of each resolution downloads its climate data once (~0.5 GB
for 1.5deg, ~1 GB for 1.0deg), then it's cached. 0.703deg is left out by default
(needs >=32 GB RAM) — uncomment it below only on a big machine.
"""
from __future__ import annotations
import sys; from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
import warnings; warnings.filterwarnings("ignore")
from climate_capacitor.util import lower_priority; lower_priority()
import matplotlib; matplotlib.use("Agg")
import pandas as pd

from climate_capacitor.config import load_config
from climate_capacitor.pipeline import run_pipeline
from climate_capacitor.data.disasters import load_disasters
from climate_capacitor.analysis import validation

WB2 = "gs://weatherbench2/datasets/era5"
RESOLUTIONS = [
    (1.5, f"{WB2}/1959-2022-6h-240x121_equiangular_with_poles_conservative.zarr"),
    (1.0, f"{WB2}/1959-2022-6h-360x181_equiangular_with_poles_conservative.zarr"),
    # (0.703, f"{WB2}/1959-2022-6h-512x256_equiangular_conservative.zarr"),  # needs >=32 GB RAM
]
TYPES   = ["full", "thermal", "temperature"]
BUDGETS = ["all", "match"]
RADII   = [100, 250, 500]


def main() -> None:
    cfg = load_config()
    rows = []
    for res_deg, uri in RESOLUTIONS:
        cfg["domain"]["resolution_deg"] = res_deg
        cfg["data"]["era5"]["cloud_uri"] = uri
        print(f"\n### RESOLUTION {res_deg} deg — running pipeline (downloads once if new) ...")
        res = run_pipeline(cfg, verbose=True, keep_temp=False)
        catalog = res["catalog"]

        for typ in TYPES:
            cfg["data"]["disasters"]["types"] = typ
            dis = load_disasters(cfg)
            dis = dis[(dis.date_start >= cfg["time"]["start"]) & (dis.date_start <= cfg["time"]["end"])]
            for budget in BUDGETS:
                cfg["validation"]["max_predictions"] = budget
                cat_full = validation.apply_budget(catalog, len(dis), cfg)
                cat = cat_full[cat_full["active"]]
                row = {"res": res_deg, "type": typ, "budget": budget,
                       "active_preds": len(cat), "disasters": len(dis)}
                for radius in RADII:
                    r = validation.validate(cat, dis, cfg, radius_km=radius)
                    row[f"recall_{radius}"] = round(r["recall"] * 100, 2)
                    if radius == 250:
                        row["prec_250"] = round(r["precision"] * 100, 2)
                        row["p_250"] = r["p_value"]
                rows.append(row)
                print(f"    {typ:12s} budget={budget:5s} -> "
                      f"recall@250 {row['recall_250']:5.2f}%  prec@250 {row['prec_250']:5.2f}%")

    df = pd.DataFrame(rows)
    print("\n" + "=" * 78)
    print(" FULL-SCOPE RESULTS (recall % at 100/250/500 km)")
    print("=" * 78)
    show = ["res", "type", "budget", "active_preds", "recall_100", "recall_250", "recall_500", "prec_250"]
    with pd.option_context("display.width", 200, "display.max_rows", 100):
        print(df[show].to_string(index=False))

    best = df.sort_values("recall_250", ascending=False).iloc[0]
    print("\nBEST by recall@250 km:")
    print(f"  resolution {best['res']} deg | type '{best['type']}' | budget '{best['budget']}'")
    print(f"  -> recall@250 {best['recall_250']}%   precision@250 {best['prec_250']}%   "
          f"recall@500 {best['recall_500']}%")

    outdir = REPO / cfg["run"]["output_dir"]; outdir.mkdir(parents=True, exist_ok=True)
    df.to_csv(outdir / "full_scope_results.csv", index=False)
    print(f"\nfull table saved -> {outdir / 'full_scope_results.csv'}")
    print("Reminder: recall alone is gameable; check prec_250 too, and remember 'match' budget")
    print("usually lowers recall (strongest predictions align worst with disasters).")


if __name__ == "__main__":
    main()
