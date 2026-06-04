"""ONE-SHOT REPORT: run the entire project end-to-end and produce a clean summary.

    python scripts/run_all.py

Does everything: loads real data -> physics -> events -> validation, then prints
a tidy console report and saves a single dashboard image (all stages on one
figure) plus a text summary and the event catalog, into outputs/report/.

Nothing here is new science -- it just orchestrates the existing pipeline and
presents the results readably. Safe to re-run (uses the cached data).
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
import pandas as pd

from climate_capacitor.config import load_config
from climate_capacitor.pipeline import run_pipeline
from climate_capacitor.data.disasters import load_disasters
from climate_capacitor.analysis import validation
from climate_capacitor.util import lower_priority

lower_priority()   # keep the machine responsive during this heavy run
BAR = "=" * 70


def banner(title: str) -> None:
    print(f"\n{BAR}\n  {title}\n{BAR}")


def _panel(ax, field, title, cmap, diverging):
    """Draw one (lat, lon) field into a dashboard subplot."""
    f = field.transpose("lat", "lon")
    vals = f.values
    if diverging:
        vmax = float(np.nanpercentile(np.abs(vals), 99)) or 1.0
        vmin = -vmax
    else:
        vmin = float(np.nanpercentile(vals, 1)); vmax = float(np.nanpercentile(vals, 99))
    m = ax.pcolormesh(f["lon"], f["lat"], vals, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
    ax.set_title(title, fontsize=9)
    ax.tick_params(labelsize=6)
    plt.colorbar(m, ax=ax, shrink=0.7)


def main() -> None:
    cfg = load_config()
    outdir = REPO / cfg["run"]["output_dir"] / "report"
    outdir.mkdir(parents=True, exist_ok=True)
    date = "2010-08-05"   # Russian-heatwave day, used for the snapshot panels

    banner("CLIMATE CAPACITOR — FULL RUN")
    print(f"  period      : {cfg['time']['start']} .. {cfg['time']['end']}")
    print(f"  resolution  : {cfg['domain']['resolution_deg']} deg (global)")
    print(f"  daily stat  : {cfg['data']['era5']['daily_statistic']}   "
          f"permittivity: {cfg['permittivity']['method']}   "
          f"charge window: {cfg['charge']['window_days']}d decay {cfg['charge']['decay_per_day']}")

    res = run_pipeline(cfg, verbose=True, keep_temp=False)  # run_all doesn't plot temperature
    cat = res["catalog"]

    dis = load_disasters(cfg)
    dis = dis[(dis.date_start >= cfg["time"]["start"]) & (dis.date_start <= cfg["time"]["end"])]

    # ---- event catalog summary ----
    banner("PREDICTED EVENTS")
    print(f"  total predicted events : {len(cat)}")
    print(f"  heat-driven / terrain  : {(cat.trigger=='heat-driven').sum()}"
          f" / {(cat.trigger=='terrain-driven').sum()}")
    print("\n  strongest 10 (by peak stress):")
    cols = ["event_id", "date_start", "duration_days", "incept_lat", "incept_lon", "peak_E", "trigger"]
    with pd.option_context("display.width", 200):
        print("    " + cat[cols].head(10).to_string(index=False).replace("\n", "\n    "))

    # ---- validation at several radii ----
    banner("VALIDATION vs EM-DAT")
    print(f"  disasters in window: {len(dis)}  "
          f"(exact {int((dis.geo_precision=='exact').sum())}, "
          f"estimated {int((dis.geo_precision=='estimated').sum())})")
    print(f"\n  {'radius_km':>9} {'recall%':>8} {'prec%':>7} {'hits':>5} {'p-value':>10} {'verdict':>16}")
    target_p = cfg["validation"]["success"]["max_pvalue"]
    rows = {}
    for radius in [cfg["validation"]["spatial_radius_km"], 250, 500, 1000]:
        r = validation.validate(cat, dis, cfg, radius_km=radius)
        rows[radius] = r
        verdict = "significant" if r["p_value"] < target_p else "~ random"
        print(f"  {radius:9.0f} {r['recall']*100:8.2f} {r['precision']*100:7.2f} "
              f"{r['disasters_hit']:5d} {r['p_value']:10.2e} {verdict:>16}")
    s = cfg["validation"]["success"]
    print(f"\n  success targets: recall>{s['min_recall']*100:.0f}%  "
          f"precision>{s['min_precision']*100:.0f}%  p<{s['max_pvalue']}")

    # ---- dashboard figure ----
    fig = plt.figure(figsize=(16, 9))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.25)
    _panel(fig.add_subplot(gs[0, 0]), res["anomaly"].sel(time=date), f"Anomaly {date}", "RdBu_r", True)
    _panel(fig.add_subplot(gs[0, 1]), res["charge"].sel(time=date), f"Charge {date}", "RdBu_r", True)
    _panel(fig.add_subplot(gs[0, 2]), res["permittivity"], "Permittivity (terrain)", "viridis", False)
    _panel(fig.add_subplot(gs[1, 0]), res["breakdown"].sel(time=date), f"Breakdown {date}", "magma", False)

    # predicted vs actual
    axm = fig.add_subplot(gs[1, 1:])
    axm.scatter(cat.incept_lon, cat.incept_lat, s=5, c="red", alpha=0.2, label="predicted")
    ex = dis[dis.geo_precision == "exact"]
    axm.scatter(ex.lon, ex.lat, s=14, c="blue", marker="x", label="disasters (exact)")
    axm.set_xlim(-180, 180); axm.set_ylim(-90, 90); axm.grid(True, lw=0.3)
    axm.set_title("Predicted events (red) vs real disasters (blue)", fontsize=9)
    axm.legend(loc="lower left", fontsize=7); axm.tick_params(labelsize=6)

    # PR curve
    axp = fig.add_subplot(gs[2, 0])
    pr = rows[cfg["validation"]["spatial_radius_km"]].get("pr_curve") or rows[1000]["pr_curve"]
    if pr:
        rec, prec = zip(*pr)
        axp.plot(rec, prec, "-o", ms=2)
    axp.set_xlabel("recall", fontsize=8); axp.set_ylabel("precision", fontsize=8)
    axp.set_title("Precision-Recall", fontsize=9); axp.grid(True, lw=0.3); axp.tick_params(labelsize=6)

    # text summary panel
    axt = fig.add_subplot(gs[2, 1:]); axt.axis("off")
    r100 = rows[cfg["validation"]["spatial_radius_km"]]
    summary = (
        f"CONFIG: {cfg['data']['era5']['daily_statistic']} / "
        f"{cfg['permittivity']['method']} / {cfg['domain']['resolution_deg']}deg\n\n"
        f"Predicted events : {len(cat)}\n"
        f"Disasters (window): {len(dis)}\n\n"
        f"At {r100['radius_km']:.0f} km:  recall {r100['recall']*100:.2f}%   "
        f"precision {r100['precision']*100:.2f}%   p={r100['p_value']:.1e}\n"
        f"At 1000 km:  recall {rows[1000]['recall']*100:.2f}%   p={rows[1000]['p_value']:.1e}\n\n"
        f"Targets: recall>{s['min_recall']*100:.0f}%  precision>{s['min_precision']*100:.0f}%  "
        f"p<{s['max_pvalue']}"
    )
    axt.text(0.0, 1.0, summary, va="top", ha="left", fontsize=10, family="monospace")

    fig.suptitle("Climate Capacitor — run dashboard", fontsize=13)
    dash = outdir / "dashboard.png"
    fig.savefig(dash, dpi=110)
    if SHOW_PLOTS:
        plt.show()
    plt.close(fig)

    # ---- save text summary + catalog ----
    (outdir / "summary.txt").write_text(summary, encoding="utf-8")
    cat.to_csv(outdir / "predicted_events.csv", index=False)

    banner("DONE")
    print(f"  dashboard : {dash}")
    print(f"  summary   : {outdir / 'summary.txt'}")
    print(f"  catalog   : {outdir / 'predicted_events.csv'}")


if __name__ == "__main__":
    main()
