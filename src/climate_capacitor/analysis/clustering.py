"""Turn the breakdown field into discrete predicted EVENTS.

Two steps (the proposal's "spatiotemporal clustering"):

  1. Per day, group neighboring flagged cells into spatial blobs (DBSCAN on the
     flagged cells' lat/lon). Each blob = one candidate event on that day.
  2. Link blobs across consecutive days when their centers are close, so a
     multi-day heatwave/storm becomes ONE event with a start, end, and track.

Output: a tidy DataFrame of daily blobs tagged with an `event_id`, plus a
per-event summary is built in events.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr
from scipy import ndimage


def detect_daily_blobs(mask: xr.DataArray, E: xr.DataArray, cfg: dict) -> pd.DataFrame:
    """Group each day's flagged cells into blobs. Dispatches on config:
    "components" (fast connected-components, default) or "dbscan" (original)."""
    if cfg["clustering"].get("algorithm", "components") == "dbscan":
        return _detect_dbscan(mask, E, cfg)
    return _detect_components(mask, E, cfg)


def _detect_dbscan(mask: xr.DataArray, E: xr.DataArray, cfg: dict) -> pd.DataFrame:
    """Original per-day DBSCAN clustering (slower; kept for fidelity/comparison)."""
    from sklearn.cluster import DBSCAN
    c = cfg["clustering"]
    res = float(cfg["domain"]["resolution_deg"])
    eps_deg = c["dbscan_eps_cells"] * res
    min_samples = int(c["dbscan_min_samples"])
    lat, lon, times = mask["lat"].values, mask["lon"].values, mask["time"].values
    mvals, evals = mask.values, E.values
    rows = []
    for t in range(mvals.shape[0]):
        ii, jj = np.where(mvals[t])
        if len(ii) < min_samples:
            continue
        labels = DBSCAN(eps=eps_deg, min_samples=min_samples).fit_predict(
            np.column_stack([lat[ii], lon[jj]]))
        for lab in set(labels):
            if lab == -1:
                continue
            sel = labels == lab
            ci, cj = ii[sel], jj[sel]
            e_here = evals[t, ci, cj]
            peak = int(np.argmax(e_here))
            rows.append({"day_index": t, "time": times[t], "lat": float(lat[ci[peak]]),
                         "lon": float(lon[cj[peak]]), "n_cells": int(sel.sum()),
                         "peak_E": float(e_here[peak])})
    return pd.DataFrame(rows)


def _detect_components(mask: xr.DataArray, E: xr.DataArray, cfg: dict) -> pd.DataFrame:
    """Connected-components clustering via scipy.ndimage.label (C-level, ~100x
    faster than the per-day DBSCAN loop). 8-connectivity groups touching cells;
    to mimic DBSCAN's eps we dilate by (eps_cells-1) first.

    Returns rows: [day_index, time, lat, lon, n_cells, peak_E] (one per blob),
    where (lat, lon) is the blob's peak-stress cell (its "center")."""
    c = cfg["clustering"]
    min_samples = int(c["dbscan_min_samples"])
    merge_iter = max(0, int(round(c["dbscan_eps_cells"])) - 1)
    structure = ndimage.generate_binary_structure(2, 2)   # 8-connectivity

    lat = mask["lat"].values
    lon = mask["lon"].values
    times = mask["time"].values
    mvals = mask.values                            # (time, lat, lon) bool
    evals = E.values
    rows = []

    for t in range(mvals.shape[0]):
        m2 = mvals[t]
        if m2.sum() < min_samples:
            continue
        grp = ndimage.binary_dilation(m2, structure=structure, iterations=merge_iter) \
            if merge_iter > 0 else m2
        labels, n = ndimage.label(grp, structure=structure)
        if n == 0:
            continue
        ii, jj = np.where(m2)                       # original flagged cells only
        labs = labels[ii, jj]                       # their blob label
        evs = evals[t, ii, jj]
        for lab in np.unique(labs):
            if lab == 0:
                continue
            sel = labs == lab
            if sel.sum() < min_samples:
                continue
            sub_e = evs[sel]
            k = int(np.argmax(sub_e))              # center on the strongest cell
            pk = np.where(sel)[0][k]
            rows.append({
                "day_index": t,
                "time": times[t],
                "lat": float(lat[ii[pk]]),
                "lon": float(lon[jj[pk]]),
                "n_cells": int(sel.sum()),
                "peak_E": float(sub_e[k]),
            })
    return pd.DataFrame(rows)


def _haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between scalar/array coordinates."""
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def link_events(blobs: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Link day-to-day blobs into events via union-find on spatial proximity.

    A blob on day t joins an event from day t-1 if its center is within
    `link_radius_km` of one of that event's day-(t-1) blobs. Adds `event_id`.
    """
    if blobs.empty:
        return blobs.assign(event_id=[])
    link_km = float(cfg["clustering"].get("link_radius_km", 300.0))
    blobs = blobs.sort_values("day_index").reset_index(drop=True)

    parent = list(range(len(blobs)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        parent[find(a)] = find(b)

    # Compare each day's blobs only to the previous day's (cheap, tracks motion).
    by_day = {d: g.index.to_numpy() for d, g in blobs.groupby("day_index")}
    days = sorted(by_day)
    for d in days:
        prev = by_day.get(d - 1)
        if prev is None:
            continue
        for i in by_day[d]:
            dist = _haversine_km(blobs.lat[i], blobs.lon[i],
                                 blobs.lat.values[prev], blobs.lon.values[prev])
            near = np.where(dist <= link_km)[0]
            for k in near:
                union(i, int(prev[k]))

    roots = [find(i) for i in range(len(blobs))]
    # Re-number roots to compact 1..N event ids.
    remap = {r: e + 1 for e, r in enumerate(sorted(set(roots)))}
    blobs["event_id"] = [remap[r] for r in roots]
    return blobs
