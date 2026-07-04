"""Sanity checks before trusting the negative verdict.

Tests the things that, if broken, would make a GOOD model look BAD:
coordinate conventions, the matching logic, a known event (2010 Russian
heatwave), recall counted per-disaster, and the high-latitude artifact.

    python scripts/sanity_check.py
"""
from __future__ import annotations
import os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import warnings; warnings.filterwarnings("ignore")
from climate_capacitor.util import lower_priority; lower_priority()
import matplotlib; matplotlib.use("Agg")
import numpy as np, pandas as pd

from climate_capacitor.config import load_config
from climate_capacitor.pipeline import run_pipeline
from climate_capacitor.data.disasters import load_disasters
from climate_capacitor.analysis import validation
from climate_capacitor.analysis.clustering import _haversine_km

BAR = "=" * 66
def h(t): print(f"\n{BAR}\n {t}\n{BAR}")

cfg = load_config()
cfg["data"]["disasters"]["types"] = "full"      # include heatwaves for the Russia test
res = run_pipeline(cfg, verbose=False, keep_temp=False)
cat = res["catalog"]
dis = load_disasters(cfg)
dis = dis[(dis.date_start >= cfg["time"]["start"]) & (dis.date_start <= cfg["time"]["end"])].reset_index(drop=True)
print(f"predicted events: {len(cat)}   disasters: {len(dis)}")

# ---- 1. Coordinate sanity ----
h("1. COORDINATE SANITY (same system? no lat/lon swap?)")
print(f"  predictions  lat {cat.incept_lat.min():.1f}..{cat.incept_lat.max():.1f}   lon {cat.incept_lon.min():.1f}..{cat.incept_lon.max():.1f}")
print(f"  disasters    lat {dis.lat.min():.1f}..{dis.lat.max():.1f}   lon {dis.lon.min():.1f}..{dis.lon.max():.1f}")
print("  (both should be lat in -90..90, lon in -180..180)")
print("  spot-check a few disasters (country vs coords):")
for _, r in dis.sample(min(5, len(dis)), random_state=1).iterrows():
    print(f"    {r['country'][:20]:20s} lat {r['lat']:7.2f}  lon {r['lon']:7.2f}  [{r['type']}]")

# ---- 2. Matching logic unit test ----
h("2. MATCHING LOGIC (a prediction 55 km from a disaster must be a HIT)")
fake_dis = pd.DataFrame({"lat":[20.0],"lon":[80.0],"date_start":[pd.Timestamp("2015-07-01")],
                         "geo_precision":["exact"],"type":["flood"]})
fake_cat = pd.DataFrame({"incept_lat":[20.5],"incept_lon":[80.0],
                         "date_start":[pd.Timestamp("2015-07-01")],"date_end":[pd.Timestamp("2015-07-01")],
                         "peak_E":[1.0]})
d_km = _haversine_km(20.0,80.0,20.5,80.0)
rr = validation.validate(fake_cat, fake_dis, cfg, radius_km=100)
print(f"  distance = {d_km:.0f} km ; recall at 100 km = {rr['recall']*100:.0f}%  (expect 100%)")
print("  -> matching works" if rr['recall']==1.0 else "  -> BUG: matching failed!")

# ---- 3. Known event: 2010 Russian heatwave (~55.7N, 37.6E, Jun-Aug 2010) ----
h("3. 2010 RUSSIAN HEATWAVE (does the model flag it? is it in the data?)")
mlat, mlon = 55.75, 37.6
d2 = _haversine_km(mlat, mlon, cat.incept_lat.values, cat.incept_lon.values)
summer = (cat.date_start >= "2010-06-01") & (cat.date_start <= "2010-09-15")
near = cat[(d2 <= 500) & summer.values]
print(f"  predicted events within 500 km of Moscow in summer 2010: {len(near)}")
if len(near): print("   ", near[['date_start','incept_lat','incept_lon','peak_E']].head(3).to_string(index=False).replace("\n","\n    "))
dd = _haversine_km(mlat, mlon, dis.lat.values, dis.lon.values)
dis_near = dis[(dd <= 500) & (dis.date_start >= "2010-06-01") & (dis.date_start <= "2010-09-15")]
print(f"  real disasters within 500 km of Moscow in summer 2010: {len(dis_near)}  types: {list(dis_near['type'].unique())}")

# ---- 4. Recall per UNIQUE disaster (not per location) ----
h("4. RECALL BY UNIQUE DISASTER (multi-location disasters counted once)")
cover = validation._coverage(cat, dis, 250.0, 2.0, 2.0)
caught_locs = set()
for idx in cover: caught_locs.update(idx.tolist())
dis = dis.copy(); dis["disno"] = dis["event_id"].astype(str).str.split("_").str[0]
caught_mask = dis.index.isin(caught_locs)
by_loc = caught_mask.mean()
by_dis = dis.loc[caught_mask, "disno"].nunique() / dis["disno"].nunique()
print(f"  @250 km: recall by location = {by_loc*100:.2f}% ;  recall by unique disaster = {by_dis*100:.2f}%")
print(f"  (unique disasters: {dis['disno'].nunique()} from {len(dis)} locations)")

# ---- 5. High-latitude artifact ----
h("5. ARCTIC/POLAR ARTIFACT (where are the predictions?)")
for thr in (45,55,60):
    frac = (cat.incept_lat.abs() > thr).mean()
    print(f"  predictions with |lat| > {thr}: {frac*100:.1f}%")
mid = cat[cat.incept_lat.abs() <= 55]
r_all = validation.validate(cat, dis, cfg, radius_km=250)
r_mid = validation.validate(mid, dis, cfg, radius_km=250)
print(f"  metrics @250 km  all preds:      recall {r_all['recall']*100:.2f}%  precision {r_all['precision']*100:.2f}%")
print(f"  metrics @250 km  |lat|<=55 only: recall {r_mid['recall']*100:.2f}%  precision {r_mid['precision']*100:.2f}%")

# ---- 6. Over-prediction: far more predictions than disasters ----
h("6. OVER-PREDICTION (does making way more predictions than disasters cap precision?)")
n_pred, n_dis = len(cat), len(dis)
print(f"  predictions: {n_pred}   disasters: {n_dis}   ({n_pred/max(1,n_dis):.1f} predictions per disaster)")
pred_hit = np.array([len(idx) > 0 for idx in cover])   # cover computed @250 km in section 4
print(f"  overall precision @250 km (all preds): {pred_hit.mean()*100:.2f}%")
print("  being SELECTIVE — keep only the strongest predictions, then re-check:")
order = cat["peak_E"].values.argsort()[::-1]
for k in (n_dis, max(1, n_dis // 2), max(1, n_dis // 10)):
    sel = order[:k]
    caught = set()
    for i in sel:
        caught.update(cover[i].tolist())
    print(f"    top {k:5d} strongest -> precision {pred_hit[sel].mean()*100:5.2f}% , "
          f"disasters caught {len(caught):4d}/{n_dis}")
print("  Reading it:")
print("   - if precision CLIMBS when selective -> we're just over-predicting; raise")
print("     breakdown.threshold_value (flag fewer cells) to trade recall for precision.")
print("   - if precision STAYS ~0 even for the strongest -> the predictions are in the")
print("     WRONG PLACES, not merely too many -> the analogy genuinely fails.")

print("\n(If matching works, Russia shows up, mid-lat precision is still tiny, AND even the")
print(" strongest predictions have ~0 precision -> the failure is real, not a bug.)")
