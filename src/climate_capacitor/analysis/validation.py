"""Validate predicted events against EM-DAT disasters.

For each predicted event we find the real disasters it "covers" -- within
`spatial_radius_km` of its inception point AND within `temporal_window` of its
active period. From that we compute:

  * Recall    = fraction of real disasters caught by >=1 prediction (hit rate)
  * Precision = fraction of predictions that hit >=1 real disaster (signal/noise)
  * p-value   = is the recall better than random predictions would give?
                (analytic binomial test vs a uniform space-time null)
  * a precision-recall curve, by adding predictions strongest-stress-first.

Results are reported separately for `exact` vs `estimated` (country-centroid)
disasters, so the coarse ones carry their caveat.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from .clustering import _haversine_km

EARTH_AREA_KM2 = 4 * np.pi * 6371.0 ** 2


def _coverage(catalog: pd.DataFrame, dis: pd.DataFrame, radius_km: float,
              lookback_days: float, lookahead_days: float):
    """For each predicted event, which disaster-row indices it covers.

    A prediction covers a disaster at date D if it's within `radius_km` AND its
    active period overlaps [D - lookback, D + lookahead]. `lookback` is the
    early-warning lead time: breakdown flagged up to `lookback` days BEFORE a
    disaster still counts (the capacitor "charges" before it "discharges")."""
    Wb = pd.Timedelta(days=lookback_days)
    Wa = pd.Timedelta(days=lookahead_days)
    p_lat = catalog["incept_lat"].to_numpy()
    p_lon = catalog["incept_lon"].to_numpy()
    p_start = catalog["date_start"].to_numpy()
    p_end = catalog["date_end"].to_numpy()
    d_lat = dis["lat"].to_numpy()
    d_lon = dis["lon"].to_numpy()
    d_date = dis["date_start"].to_numpy()

    cover = []
    for i in range(len(catalog)):
        # prediction [p_start, p_end] overlaps [D - lookback, D + lookahead]
        temporal_ok = (p_start[i] <= d_date + Wa) & (p_end[i] >= d_date - Wb)
        if not temporal_ok.any():
            cover.append(np.empty(0, dtype=int)); continue
        idx = np.where(temporal_ok)[0]
        dist = _haversine_km(p_lat[i], p_lon[i], d_lat[idx], d_lon[idx])
        cover.append(idx[dist <= radius_km])
    return cover


def validate(catalog: pd.DataFrame, dis: pd.DataFrame, cfg: dict, radius_km: float | None = None,
             lookback_days: float | None = None, lookahead_days: float | None = None):
    """Compute recall/precision/p-value (overall + by geo_precision).

    lookback_days: early-warning lead time (breakdown before a disaster still
    counts). lookahead_days: tolerance after. Both default to the config
    temporal window (symmetric)."""
    v = cfg["validation"]
    radius_km = float(radius_km if radius_km is not None else v["spatial_radius_km"])
    base_w = float(v["temporal_window_hours"]) / 24.0
    lookback_days = float(lookback_days if lookback_days is not None else base_w)
    lookahead_days = float(lookahead_days if lookahead_days is not None else base_w)
    window_days = (lookback_days + lookahead_days) / 2.0   # for the null-model span

    if catalog.empty or dis.empty:
        return {"error": "empty catalog or disaster set"}

    cover = _coverage(catalog, dis, radius_km, lookback_days, lookahead_days)

    n_pred = len(catalog)
    n_dis = len(dis)
    hit_dis = np.zeros(n_dis, dtype=bool)        # which disasters got caught
    pred_hits = np.zeros(n_pred, dtype=bool)     # which predictions caught something
    for i, idx in enumerate(cover):
        if len(idx):
            pred_hits[i] = True
            hit_dis[idx] = True

    recall = hit_dis.mean()
    precision = pred_hits.mean()

    # by precision flag
    out = {"radius_km": radius_km, "window_days": window_days,
           "n_predicted": int(n_pred), "n_disasters": int(n_dis),
           "recall": float(recall), "precision": float(precision),
           "disasters_hit": int(hit_dis.sum()),
           "predictions_that_hit": int(pred_hits.sum())}
    if "geo_precision" in dis.columns:
        for tag in ("exact", "estimated"):
            m = (dis["geo_precision"] == tag).to_numpy()
            if m.any():
                out[f"recall_{tag}"] = float(hit_dis[m].mean())
                out[f"n_{tag}"] = int(m.sum())

    # --- analytic p-value vs uniform space-time null ---
    # P(one random prediction covers a given disaster) = spatial * temporal frac.
    f_spatial = (np.pi * radius_km ** 2) / EARTH_AREA_KM2
    total_days = max(1, (dis["date_start"].max() - dis["date_start"].min()).days)
    f_temporal = min(1.0, (2 * window_days) / total_days)
    p_one = f_spatial * f_temporal
    p_dis_null = 1 - (1 - p_one) ** n_pred       # P(a disaster hit by >=1 of N preds)
    k = int(hit_dis.sum())
    bt = binomtest(k, n_dis, min(p_dis_null, 0.999999), alternative="greater")
    out["null_recall"] = float(p_dis_null)
    out["p_value"] = float(bt.pvalue)

    # --- precision-recall curve: add predictions strongest-first ---
    order = catalog["peak_E"].to_numpy().argsort()[::-1]
    caught = np.zeros(n_dis, dtype=bool)
    n_added = n_hit_preds = 0
    pr = []
    for rank, i in enumerate(order, 1):
        n_added += 1
        idx = cover[i]
        if len(idx):
            n_hit_preds += 1
            caught[idx] = True
        if rank % max(1, n_pred // 100) == 0 or rank == n_pred:
            pr.append((caught.mean(), n_hit_preds / n_added))   # (recall, precision)
    out["pr_curve"] = pr
    return out


def print_report(r: dict, cfg: dict):
    s = cfg["validation"]["success"]
    print("\n=== Validation vs EM-DAT ===")
    if "error" in r:
        print("  ", r["error"]); return
    print(f"  match window: {r['radius_km']:.0f} km / +/-{r['window_days']*24:.0f} h")
    print(f"  predicted events: {r['n_predicted']}   disasters: {r['n_disasters']}")
    print(f"  RECALL    {r['recall']*100:5.1f}%  (target >{s['min_recall']*100:.0f}%)  "
          f"-> {r['disasters_hit']} disasters caught")
    if "recall_exact" in r:
        print(f"            exact:     {r['recall_exact']*100:5.1f}%  (n={r['n_exact']})")
    if "recall_estimated" in r:
        print(f"            estimated: {r['recall_estimated']*100:5.1f}%  (n={r['n_estimated']})")
    print(f"  PRECISION {r['precision']*100:5.1f}%  (target >{s['min_precision']*100:.0f}%)  "
          f"-> {r['predictions_that_hit']}/{r['n_predicted']} predictions hit")
    print(f"  null recall (random): {r['null_recall']*100:.3f}%")
    print(f"  p-value: {r['p_value']:.2e}  (target <{s['max_pvalue']})  "
          f"-> {'SIGNIFICANT' if r['p_value'] < s['max_pvalue'] else 'not significant'}")
