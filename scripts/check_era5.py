"""Phase 2 step 1: pull a 1-YEAR test slice of real ERA5 and verify it.

Confirms the cloud streaming + daily-max aggregation + caching all work, and
renders a real temperature map you can eyeball, before we scale to 10 years.

    python scripts/check_era5.py
"""

from __future__ import annotations

import os
import sys
import time
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
from climate_capacitor.viz.maps import plot_field

# 1-year test window (global, coarse). Scale to the full config period later.
TEST_START, TEST_END = "2015-01-01", "2015-12-31"


def main() -> None:
    cfg = load_config()
    print(f"Pulling ERA5 daily-{cfg['data']['era5']['daily_statistic']} "
          f"for {TEST_START}..{TEST_END} (global, {cfg['domain']['resolution_deg']} deg) ...")

    t0 = time.time()
    da = load_era5(cfg, TEST_START, TEST_END)
    dt = time.time() - t0

    print("\n=== ERA5 test-slice summary ===")
    print(f"  fetched in: {dt:.1f}s")
    print(f"  shape:      {dict(da.sizes)}")
    print(f"  lat range:  {float(da.lat.min()):.1f} .. {float(da.lat.max()):.1f}")
    print(f"  lon range:  {float(da.lon.min()):.1f} .. {float(da.lon.max()):.1f}")
    print(f"  temp range: {float(da.min()):.1f} .. {float(da.max()):.1f} K  "
          f"({float(da.min())-273.15:.1f} .. {float(da.max())-273.15:.1f} C)")
    in_memory_mb = da.nbytes / 1e6
    print(f"  in memory:  {in_memory_mb:.1f} MB")

    # Render a real map: a northern-hemisphere summer day (heat shows up).
    day = "2015-07-15"
    snap = da.sel(time=day)
    out = REPO / cfg["run"]["output_dir"] / "phase2" / "era5_t2m_2015-07-15.png"
    plot_field(snap, f"ERA5 daily-max 2m temperature (K) — {day}", out,
               cmap="inferno", diverging=False, show=SHOW_PLOTS)
    print(f"\nMap written to: {out}")


if __name__ == "__main__":
    main()
