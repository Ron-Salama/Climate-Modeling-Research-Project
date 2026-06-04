"""Experiment engine: sweep permittivity (epsilon) settings and score each.

Computes the expensive part (load -> anomaly -> charge) ONCE, then for each
candidate epsilon recipe recomputes only the cheap downstream
(permittivity -> breakdown -> events -> validation) and prints recall/precision/
p-value. Lets the disaster data pick the best terrain weighting instead of us
guessing a number.

    python scripts/run_experiment.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")

from climate_capacitor.util import lower_priority
lower_priority()   # keep the machine responsive during this heavy run
from climate_capacitor.config import load_config
from climate_capacitor.data.era5 import load_era5
from climate_capacitor.data.topography import load_topography
from climate_capacitor.data.disasters import load_disasters
from climate_capacitor.physics import anomaly, breakdown, charge, permittivity
from climate_capacitor.analysis import clustering, events, validation

# Candidate epsilon recipes to test. "control" = terrain off (epsilon = 1 everywhere).
SWEEP = [
    {"label": "control (no terrain)", "method": "linear", "eps_min": 1.0, "eps_max": 1.0},
    {"label": "eps_min 0.2",          "method": "linear", "eps_min": 0.2, "eps_max": 1.0},
    {"label": "eps_min 0.4",          "method": "linear", "eps_min": 0.4, "eps_max": 1.0},
    {"label": "eps_min 0.5",          "method": "linear", "eps_min": 0.5, "eps_max": 1.0},
    {"label": "eps_min 0.6",          "method": "linear", "eps_min": 0.6, "eps_max": 1.0},
    {"label": "eps_min 0.7",          "method": "linear", "eps_min": 0.7, "eps_max": 1.0},
]
RADII = [150, 250, 500]


def main() -> None:
    cfg = load_config()
    print(f"Loading data + computing charge once ({cfg['domain']['resolution_deg']} deg) ...")
    temp = load_era5(cfg, cfg["time"]["start"], cfg["time"]["end"])
    topo = load_topography(cfg)
    anom = anomaly.compute_anomaly(temp, smooth_days=cfg["charge"]["climatology_smooth_days"])
    Q = charge.accumulate_charge(anom, cfg["charge"]["window_days"], cfg["charge"]["decay_per_day"])
    del temp, anom  # free ~0.8 GB: the sweep only needs the charge from here on

    dis = load_disasters(cfg)
    dis = dis[(dis.date_start >= cfg["time"]["start"]) & (dis.date_start <= cfg["time"]["end"])]
    lat_limit = cfg["domain"].get("analysis_lat_max")

    print(f"\n{'epsilon recipe':22} {'#events':>8} " +
          " ".join(f"r{r}km%/p" for r in RADII))
    print("-" * 70)

    results = []
    for spec in SWEEP:
        pcfg = {"method": spec["method"], "eps_min": spec["eps_min"],
                "eps_max": spec["eps_max"], "params": cfg["permittivity"]["params"]}
        eps = permittivity.compute_permittivity(topo["elevation"], topo["slope"], pcfg)
        E = breakdown.breakdown_field(Q, eps)
        mask, thr = breakdown.flag_zones(E, cfg["breakdown"]["threshold_mode"],
                                         cfg["breakdown"]["threshold_value"], lat_limit=lat_limit)
        blobs = clustering.link_events(clustering.detect_daily_blobs(mask, E, cfg), cfg)
        cat = events.classify_and_summarize(blobs, Q, eps, cfg)

        cells = []
        for radius in RADII:
            r = validation.validate(cat, dis, cfg, radius_km=radius)
            cells.append(f"{r['recall']*100:4.1f}/{r['p_value']:.0e}")
        print(f"{spec['label']:22} {len(cat):8d} " + " ".join(f"{c:>12}" for c in cells))
        results.append((spec["label"], len(cat), cells))

    print("\nReading the table: recall% / p-value at each match radius.")
    print("Look for the recipe with highest recall AND p<0.05 (significant).")


if __name__ == "__main__":
    main()
