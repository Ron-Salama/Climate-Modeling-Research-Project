"""Summarize linked blobs into a catalog of predicted events.

For each event (a group of day-to-day-linked blobs) we compute:
  * point of inception  -> first day's peak cell (the "spark"),
  * start/end date + duration,
  * peak stress + max spatial extent,
  * trigger type: heat-driven (charge gradient dominates) vs terrain-driven
    (low permittivity / rugged bottleneck dominates),
  * precursor charge ramp -> how fast charge built up at the inception cell in
    the weeks before (the early-warning signature).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from ..physics.breakdown import gradient_magnitude


def classify_and_summarize(
    blobs: pd.DataFrame, Q: xr.DataArray, eps: xr.DataArray, cfg: dict
) -> pd.DataFrame:
    """Build one row per event_id from the linked blobs."""
    if blobs.empty:
        return pd.DataFrame()

    gradQ = gradient_magnitude(Q)          # |grad charge|, same dims as Q
    window = int(cfg["charge"]["window_days"])

    # Normalizers so "heat" and "terrain" contributions are comparable (0..1-ish).
    grad_ref = float(np.nanpercentile(gradQ.values, 99)) or 1.0
    inv_eps = (1.0 / eps.clip(min=1e-6))
    inv_eps_ref = float(np.nanpercentile(inv_eps.values, 99)) or 1.0

    # Pull raw numpy arrays + coord->index maps so per-event lookups are O(1)
    # array indexing instead of slow xarray .sel() calls (big speedup at scale).
    gradQ_v = gradQ.transpose("time", "lat", "lon").values
    Q_v = Q.transpose("time", "lat", "lon").values
    inv_eps_v = inv_eps.transpose("lat", "lon").values
    lat_idx = {round(float(v), 5): i for i, v in enumerate(Q["lat"].values)}
    lon_idx = {round(float(v), 5): i for i, v in enumerate(Q["lon"].values)}

    out = []
    for eid, g in blobs.groupby("event_id"):
        g = g.sort_values("day_index")
        first = g.iloc[0]                  # inception = earliest blob
        t0 = int(first["day_index"])
        la, lo = float(first["lat"]), float(first["lon"])
        ila, ilo = lat_idx[round(la, 5)], lon_idx[round(lo, 5)]

        # --- trigger classification at the inception cell/time ---
        heat = float(gradQ_v[t0, ila, ilo]) / grad_ref
        terr = float(inv_eps_v[ila, ilo]) / inv_eps_ref
        trigger = "heat-driven" if heat >= terr else "terrain-driven"

        # --- precursor charge ramp at inception cell over the prior window ---
        lo_t = max(0, t0 - window)
        pre = Q_v[lo_t:t0 + 1, ila, ilo]
        ramp = float(pre[-1] - pre[0]) / max(1, len(pre) - 1) if len(pre) > 1 else 0.0

        out.append({
            "event_id": int(eid),
            "date_start": pd.Timestamp(first["time"]).normalize(),
            "date_end": pd.Timestamp(g.iloc[-1]["time"]).normalize(),
            "duration_days": int(g["day_index"].max() - g["day_index"].min() + 1),
            "incept_lat": la,
            "incept_lon": lo,
            "peak_E": float(g["peak_E"].max()),
            "max_cells": int(g["n_cells"].max()),
            "trigger": trigger,
            "heat_score": round(heat, 3),
            "terrain_score": round(terr, 3),
            "precursor_ramp": round(ramp, 4),
        })
    cat = pd.DataFrame(out).sort_values("peak_E", ascending=False).reset_index(drop=True)
    return cat
