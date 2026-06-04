"""Phase 4: run the full pipeline, then validate predictions against EM-DAT.

    python scripts/run_validate.py

Prints recall / precision / p-value (overall + exact vs estimated disasters),
saves a predicted-vs-actual world map and a precision-recall curve.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import warnings
warnings.filterwarnings("ignore")

SHOW_PLOTS = "spyder_kernels" in sys.modules or bool(os.environ.get("SPY_PYTHONPATH"))
import matplotlib
if not SHOW_PLOTS:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from climate_capacitor.config import load_config
from climate_capacitor.pipeline import run_pipeline
from climate_capacitor.data.disasters import load_disasters
from climate_capacitor.analysis import validation


def main() -> None:
    cfg = load_config()
    res = run_pipeline(cfg)
    cat = res["catalog"]
    dis = load_disasters(cfg)

    # restrict disasters to the analysis time window
    dis = dis[(dis.date_start >= cfg["time"]["start"]) & (dis.date_start <= cfg["time"]["end"])]

    r = validation.validate(cat, dis, cfg)
    validation.print_report(r, cfg)

    outdir = REPO / cfg["run"]["output_dir"] / "phase4"
    outdir.mkdir(parents=True, exist_ok=True)

    # --- predicted vs actual map ---
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.scatter(cat.incept_lon, cat.incept_lat, s=6, c="red", alpha=0.25, label="predicted events")
    ex = dis[dis.geo_precision == "exact"]; es = dis[dis.geo_precision == "estimated"]
    ax.scatter(ex.lon, ex.lat, s=18, c="blue", marker="x", label="disasters (exact)")
    ax.scatter(es.lon, es.lat, s=10, c="cyan", marker=".", alpha=0.5, label="disasters (estimated)")
    ax.set_xlim(-180, 180); ax.set_ylim(-90, 90); ax.grid(True, lw=0.3, color="0.7")
    ax.set_title("Predicted breakdown events vs EM-DAT disasters")
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude"); ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout(); fig.savefig(outdir / "predicted_vs_actual.png", dpi=110)
    if SHOW_PLOTS: plt.show()
    plt.close(fig)

    # --- precision-recall curve ---
    if r.get("pr_curve"):
        rec, prec = zip(*r["pr_curve"])
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(rec, prec, "-o", ms=3)
        ax.set_xlabel("recall"); ax.set_ylabel("precision")
        ax.set_title("Precision-Recall (predictions added strongest-first)")
        ax.grid(True, lw=0.3)
        fig.tight_layout(); fig.savefig(outdir / "precision_recall.png", dpi=110)
        if SHOW_PLOTS: plt.show()
        plt.close(fig)

    print(f"\n  figures -> {outdir}")


if __name__ == "__main__":
    main()
