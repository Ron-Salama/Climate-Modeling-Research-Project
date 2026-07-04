"""Why did the model miss the 2010 Russian heatwave? Crowded out, or genuinely low?"""
from __future__ import annotations
import sys; from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
import warnings; warnings.filterwarnings("ignore")
from climate_capacitor.util import lower_priority; lower_priority()
import numpy as np
from climate_capacitor.config import load_config
from climate_capacitor.pipeline import run_pipeline

cfg = load_config()
res = run_pipeline(cfg, verbose=False, keep_temp=True)
Q, E, mask, thr = res["charge"], res["breakdown"], res["mask"], res["threshold"]
temp, anom = res["temp"], res["anomaly"]

mlat, mlon = 55.75, 37.6            # Moscow
def at(da):  # nearest cell, summer-2010 time slice
    return da.sel(lat=mlat, lon=mlon, method="nearest").sel(time=slice("2010-06-01","2010-09-15"))

aM, qM, eM = at(anom), at(Q), at(E)
peak_day = eM["time"].values[int(eM.values.argmax())]

print("=== Moscow (55.75N, 37.6E), summer 2010 ===")
print(f"  peak anomaly : {float(aM.max()):+.1f} K   (hot? should be strongly +)")
print(f"  peak charge  : {float(qM.max()):+.1f}")
print(f"  peak breakdown E : {float(eM.max()):.3f}")
print(f"  flagging threshold : {thr:.3f}   -> Moscow flagged? {float(eM.max()) > thr}")

# where does Moscow's peak-day E rank vs the whole world that day?
Eday = E.sel(time=peak_day).values
eM_peak = float(eM.max())
pct = (Eday < eM_peak).mean() * 100
print(f"\n  on {np.datetime_as_string(peak_day, unit='D')}: Moscow's E is at the "
      f"{pct:.1f}th percentile globally (threshold = ~97.5th)")

# how much of the high-E (flagged) area that day is high-latitude?
Eday2 = E.sel(time=peak_day).transpose("lat", "lon").values   # (lat, lon)
flagged = Eday2 > thr
latgrid = np.broadcast_to(E["lat"].values[:, None], Eday2.shape)
if flagged.sum():
    hi = (np.abs(latgrid[flagged]) > 55).mean() * 100
    print(f"  of all flagged cells that day, {hi:.0f}% are at |lat|>55 (Arctic/sub-Arctic)")
print("\nRead: if Moscow's anomaly is strongly hot but its E is LOW percentile -> a uniform")
print("heatwave has weak GRADIENT, so the gradient-based model can't see it (theory limit).")
print("If Moscow's E is HIGH but below an Arctic-inflated threshold -> it's crowded out (fixable).")
