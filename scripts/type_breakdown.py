"""Which disaster TYPES does the model predict best? (recall per type)"""
from __future__ import annotations
import sys; from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
import warnings; warnings.filterwarnings("ignore")
from climate_capacitor.util import lower_priority; lower_priority()
import pandas as pd
from climate_capacitor.config import load_config
from climate_capacitor.pipeline import run_pipeline
from climate_capacitor.data.disasters import load_disasters
from climate_capacitor.analysis import validation

cfg = load_config()
cfg["data"]["disasters"]["types"] = "full"     # all weather types
res = run_pipeline(cfg, verbose=False, keep_temp=False)
cat = res["catalog"]
dis = load_disasters(cfg)
dis = dis[(dis.date_start >= cfg["time"]["start"]) & (dis.date_start <= cfg["time"]["end"])].reset_index(drop=True)

RADII = [100, 250, 500]
for radius in RADII:
    cover = validation._coverage(cat, dis, radius, 2.0, 2.0)
    caught = set()
    for idx in cover:
        caught.update(idx.tolist())
    dis[f"hit{radius}"] = dis.index.isin(caught)

tab = dis.groupby("type").agg(
    n_locations=("type", "size"),
    recall_100=("hit100", "mean"),
    recall_250=("hit250", "mean"),
    recall_500=("hit500", "mean"),
).sort_values("recall_250", ascending=False)

print(f"\npredicted events: {len(cat)}   disaster locations: {len(dis)}\n")
print("RECALL BY DISASTER TYPE (fraction of that type caught by a prediction)")
print(f"{'type':22s} {'#locs':>6} {'@100km':>8} {'@250km':>8} {'@500km':>8}")
for t, r in tab.iterrows():
    print(f"{t:22s} {int(r.n_locations):6d} {r.recall_100*100:7.2f}% {r.recall_250*100:7.2f}% {r.recall_500*100:7.2f}%")

print("\nTOP 5 types the model predicts best (by recall @250 km):")
for i, (t, r) in enumerate(tab.head(5).iterrows(), 1):
    print(f"  {i}. {t:20s} recall@250 = {r.recall_250*100:.2f}%  ({int(r.n_locations)} locations)")
print("\n(Higher = the model's breakdown zones line up with that disaster type more often.)")
