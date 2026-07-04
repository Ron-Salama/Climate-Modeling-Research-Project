# Code Guide — how the project is built

For explaining the code (not line-by-line — the important parts). Pairs with
`WALKTHROUGH.md` (what it does scientifically) and `USER_MANUAL.md` (how to run it).

## Project layout

```
config/default.yaml              ← every setting (no values hard-coded in code)
src/climate_capacitor/
  config.py                      ← reads the settings file
  util.py                        ← run at low priority (keeps the PC responsive)
  pipeline.py                    ← the conductor: runs all stages in order
  data/    era5.py  topography.py  disasters.py  synthetic.py
  physics/ anomaly.py  charge.py  permittivity.py  breakdown.py
  analysis/ clustering.py  events.py  validation.py
  viz/     maps.py               ← draws the maps
scripts/                         ← the things you actually run (entry points)
tests/test_physics.py            ← quick correctness checks
```

**Design idea to state up front:** the code is a **modular pipeline driven by one
config file**. Each stage is a small module with one job; `pipeline.py` chains them.
Nothing is hard-coded — every knob lives in `config/default.yaml`, so experiments
are just config changes.

---

## The conductor

**`pipeline.py` → `run_pipeline(cfg)`** — calls each stage in order and returns all
results in a dictionary:
`load_era5 → load_topography → compute_anomaly → accumulate_charge →
compute_permittivity → breakdown_field → flag_zones → detect_daily_blobs →
link_events → classify_and_summarize`.
*Key idea:* one function shows the whole flow; every script calls this.

---

## Data layer (`data/`)

**`era5.py` → `load_era5(cfg, start, end)`** — gets the temperature.
- If a local cache file exists, load it; otherwise open the cloud store **lazily**
  (nothing downloaded yet), cut out our region + dates, collapse each day to one
  value (`.resample("1D").max/min/mean`), then `.compute()` to actually fetch.
- *Key line/idea:* `dask.config.set(scheduler="threads", num_workers=32)` fetches
  the many small cloud chunks **in parallel** (the fix that took a pull from minutes
  to seconds). Result is saved as float32 and cached so later runs are offline.

**`topography.py` → `load_topography(cfg)`** — gets the terrain from the *same* store.
*Key idea:* `elevation = geopotential_at_surface / 9.80665`; slope = gradient of
elevation; roughness = std-of-orography. Cached locally too.

**`disasters.py` → `load_disasters(cfg)`** — the "truth" set.
- `_load_disasters_gdis`: read GDIS (precise coordinates), keep climate types, and
  **join to EM-DAT by disaster number** to attach the dates. Every row is `exact`.
- `_load_disasters_emdat`: EM-DAT only; fills missing coordinates from a country's
  centre point and tags each `exact` or `estimated`.
*Key idea:* GDIS gives *where*, EM-DAT gives *when* — we merge them.

**`synthetic.py` → `make_synthetic(...)`** — builds a fake world (seasonal cycle +
a **planted, growing heatwave** + gaussian "mountains"), so we can test the pipeline
with no download. *Key idea:* a known answer to check the model against.

---

## Physics layer (`physics/`)  — the science

**`anomaly.py` → `compute_anomaly(temp)`** — "how unusual is each day?"
Builds a **day-of-year climatology** (average of every Jan-1, every Jan-2, …) and
subtracts it. *Key idea:* removes the normal seasons so only the *surprise* remains.

**`charge.py` → `accumulate_charge(anomaly)`** — the "capacitor charging".
Adds up the last 30 days of anomalies with a decay (recent days count more).
*Key idea:* done with one filter call (`scipy.signal.lfilter`) over the whole map at
once — **vectorized**, no slow per-cell loop.

**`permittivity.py` → `compute_permittivity(elevation, slope, cfg)`** — terrain → ε.
*Key idea:* a **registry of interchangeable formulas** (`linear/log/slope/combined`,
registered with a `@register` decorator); the config picks one by name. Rugged terrain
→ low ε, smooth → high ε, scaled into `[eps_min, eps_max]`.

**`breakdown.py`** — the core equation and the flagging.
- `gradient_magnitude(charge)`: how sharply charge changes between neighbours,
  computed in **kilometres** (a `cos(latitude)` factor fixes the east-west distance
  near the poles).
- `breakdown_field(charge, eps)`: `E = ‖∇Q‖ / eps`.
- `flag_zones(E, ...)`: mark the top-percentile cells as "risk", and **drop cells
  past ±66°** (poles have no disasters and produced noise).
*Key idea:* this is the whole analogy in one line — steep charge gradient ÷ terrain.

---

## Analysis layer (`analysis/`)  — from a stress map to a scored result

**`clustering.py`**
- `detect_daily_blobs`: group each day's flagged cells into blobs. Default uses
  `scipy.ndimage.label` (**connected components**, C-fast); `dbscan` is available via config.
- `link_events`: join blobs day-to-day (if close in space) into multi-day **events**
  using a union-find. *Key idea:* turns loose pixels into "storm-shaped" objects with a track.

**`events.py` → `classify_and_summarize(...)`** — describe each event: its **inception**
(first cell/day), whether it's **heat-driven** (charge gradient dominates) or
**terrain-driven** (low ε dominates), and its charge build-up ramp.

**`validation.py` → `validate(catalog, disasters, cfg)`** — the scoring.
- `_coverage`: for each prediction, which real disasters it "covers" — within a
  **distance** (haversine ≤ radius) *and* a **time window** (with an optional
  early-warning `lookback`).
- Computes **recall**, **precision**, and a **p-value** (a binomial test vs a
  random-guessing baseline), plus a precision-recall curve.
*Key idea to state:* a big/"significant" p-value here is a **sample-size** effect —
recall/precision are the numbers that matter.

---

## Visualization (`viz/maps.py`)

**`plot_field(field, title, out_path)`** — draws any map with `pcolormesh`
(red↔blue for anomaly/charge, sequential for breakdown), optionally overlaying the
flagged zones. In **Spyder** it shows inline; from a terminal it saves a PNG.

---

## Scripts (`scripts/`) — the entry points you run

| Script | What it runs |
|---|---|
| `run_synthetic.py` | pipeline on the fake world (demo, no data) |
| `run_real.py` | pipeline on real Earth → the 5 maps |
| `run_detect.py` | pipeline → predicted-event catalog (CSV) |
| `run_validate.py` | pipeline + scoring vs disasters + figures |
| `run_all.py` | everything → one dashboard + summary |
| `run_experiment.py` | sweep the terrain weighting (ε) |
| `run_stat_sweep.py` | sweep the daily statistic (mean/max/min) |
| `run_final.py` | sweep match radius × early-warning lookback |
| `check_era5.py` | quick test that the temperature loads |
| `tests/test_physics.py` | unit tests for the physics functions |

*Common pattern in every script:* `load_config()` → `run_pipeline()` (or call stages
directly) → print numbers / save plots. They call `lower_priority()` so a run doesn't
freeze the machine.

---

## The plots and what they mean

(Full list in `WALKTHROUGH.md` Part 2.) In short:
- **`outputs/phase1/*`** — the 5 pipeline stages on the *fake* world; the planted
  heatwave lights up the charge & breakdown maps → proves the code works.
- **`outputs/phase2_real/*`** — the same 5 on the *real* Earth; the 2010 Russian
  heatwave appears in the anomaly map → sanity check on real data.
- **`outputs/phase4/predicted_vs_actual_clean.png`** — red predictions vs blue real
  disasters; they mostly don't overlap → the negative result in one picture.
- **`outputs/phase4/precision_recall.png`** — precision vs recall trade-off.
- **`outputs/report/dashboard.png`** — all of the above on one page.
