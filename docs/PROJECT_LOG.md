# Project Log — Climate Capacitor

A running record of decisions, ideas (used & unused), obstacles, and references.
Companion to `ROADMAP.md` (the plan). This file is the "why we did it this way"
and "what we tried" memory. Newest entries appended per phase.

---

## Data sources & references (what we actually use)

| Data | Source | Access | Notes |
|---|---|---|---|
| Temperature (ERA5) | **WeatherBench2** ERA5, 1.5°, 6-hourly | Public GCS Zarr, no account | `gs://weatherbench2/datasets/era5/1959-2022-6h-240x121_equiangular_with_poles_conservative.zarr` |
| Terrain | **Same WeatherBench2 store** (`geopotential_at_surface`, `land_sea_mask`, `standard_deviation_of_orography`) | Public, no extra download | elevation = geopotential / 9.80665 |
| Disasters — dates | **EM-DAT** | Free login at emdat.be, manual export | Has dates + types; precise coords mostly missing |
| Disasters — coords | **GDIS** (geocoded EM-DAT) | Free NASA Earthdata login, manual | Precise lat/lon; joined to EM-DAT dates by disaster number. **PRIMARY truth set.** |
| Country centroids | eesur/country-codes-lat-long (GitHub) | Public JSON | Fallback coords for EM-DAT-only mode; cached `data/reference/country_centroids.csv` |

Scientific anchors (from the proposal's lit review): IPCC AR6 (2021); Perkins-Kirkpatrick
& Lewis (2020, heatwave clustering >1000 km); Woollings et al. (2018, orographic blocking);
Brooks (2013, CAPE/threshold behavior); Rycroft et al. (2000, Global Atmospheric Electric
Circuit — precedent for circuit analogies); Bak et al. (1987, self-organized criticality).

---

## Key architecture decisions

1. **Modular pipeline, config-driven.** Every knob in `config/default.yaml`; code stays generic.
   Rationale: proposal requires *maintainability* + *auditability*; lets us sweep experiments
   without editing logic.
2. **Pluggable permittivity (ε) registry.** `physics/permittivity.py` holds `linear/log/slope/
   combined` as registered functions; config picks one by name. Rationale: the proposal calls
   for testing multiple terrain→ε formulas — built as an abstraction, not copy-paste.
3. **Synthetic-data first (Phase 1).** Full physics runs on a fabricated world with a planted
   heatwave before any download. Rationale: prove the math end-to-end cheaply; real data later
   flows through identical interfaces (no throwaway).
4. **Coarse-global, daily, single variable.** 1.5° + daily + 2m-temperature → ~1 GB, laptop-
   friendly. Sidesteps the "terabytes / RAM crash" the proposal worried about (that only happens
   at hourly × fine-grid × many variables).
5. **Standardized dim order (time, lat, lon)** across loaders + viz, after a transpose bug (below).

---

## Design discussions / brainstorming

- **daily statistic: max vs mean vs min vs "extreme".**
  - Goal: one number per cell per day for "how unusual". `max` = hot-biased, `min` = cold-biased,
    `mean` = balanced/energy-like, `extreme` = most-anomalous-moment (hot or cold).
  - Realisation (driven by user questioning): `max` can *mislead* — a day warmer-than-normal
    overall can show a negative max-anomaly if only its afternoon peak dipped. So `max` is NOT a
    uniquely "correct" default.
  - **Key concept:** we work in **anomalies** (deviation from each cell's *own* day-of-year normal),
    not raw temperature. Cold nights aren't anomalies (night is normally cold) — only the surprise
    relative to that moment's normal counts. Compare like-for-like (today's min vs *normal* min).
  - **Decision:** default `mean` (robust, never flips sign) for the data layer; `max`/`min` as
    alternatives; `"extreme"` (= biggest signed anomaly of the day) is a Phase-4 experiment because
    it must be computed AFTER climatology, not at load time. → swept against disasters in Phase 4.
- **Why both hot AND cold matter (the capacitor picture).** Charge is *signed* (hot=+, cold=−).
  Breakdown = ‖∇Q‖/ε (gradient of charge), so it peaks where opposite charges sit *adjacent* —
  like the field between a capacitor's + and − plates. Uniform-hot → weak field; *contrast* drives
  breakdown. ⇒ never discard the anomaly's sign.
- **EM-DAT geolocation gap → country-centroid fallback (user's idea).** Only 623/4274 EM-DAT rows
  have real coordinates (mostly floods/storms; ~0 heatwaves). Fix: fill missing coords from the
  event's country centre, tag `geo_precision = exact | estimated`. Recovered 239 heatwave events.
  Phase 4 reports estimated matches with an explicit "approximate / country-level" caveat.

---

## Obstacles & how we solved them

| Obstacle | Resolution |
|---|---|
| "Daily-max needs sub-daily data" → hourly ARCO would transfer ~24× globally | Use WeatherBench2 (already 6-hourly + coarse) → daily-max is max of 4 small samples; ~1 GB total |
| Cloud pull of even 1 year was very slow | Store is chunked in tiny 8-timestep blocks → ~180 serial network reads. Fixed by fetching concurrently: `dask.config.set(scheduler="threads", num_workers=32)`. 1 month: minutes → ~6 s |
| 1-year cube made anomalies ≈ 0 | Day-of-year climatology needs multiple years. Pulled full 10 years (cached ~840 MB) for meaningful anomalies |
| Spyder "kernel" error | Installed `spyder-kernels==2.2.*` (Spyder 5.x needs 2.2.x; we'd first put 3.1.4 for Spyder 6) |
| EM-DAT `.xlsx` unreadable | `pip install openpyxl` |
| `pcolormesh` shape error on real data | ERA5 is `(lon, lat)`, synthetic was `(lat, lon)`. Made viz + loaders transpose to standard `(time, lat, lon)` |
| EM-DAT heatwaves had no coordinates | Country-centroid fallback with `geo_precision` flag (see above) |

---

## Unused / deferred / alternatives considered

- **ARCO-ERA5 (0.25°, hourly)** — kept as a `cloud_uri_hires` config option for future regional
  "zoom in"; not used now (bandwidth-heavy for global daily-max).
- **Copernicus CDS API (`cdsapi`)** — server-side daily aggregation is efficient but needs an
  account + queue; deferred in favor of account-free cloud streaming. Commented in requirements.
- **SRTM 30 m / ETOPO standalone** — overkill at 1.5°; terrain comes from WeatherBench2 instead.
  `rioxarray`/`rasterio` therefore not installed (commented in requirements).
- **"extreme" daily statistic** — designed (most-anomalous-moment-of-day), not yet implemented;
  needs sub-daily anomalies. Slated for the Phase-4 experiment sweep.
- **K-Means clustering** — config option, but DBSCAN/connected-components fits gridded blobs better.

---

## Phase status

- Phase 0 ✅ · Phase 1 ✅ · Phase 2 ✅ · Phase 3 (detection) ✅ · Phase 4 (validation) ✅
- Phase 5 (viz): mostly done (maps, predicted-vs-actual, PR curve). Full software runs end-to-end.

## Phase 3/4 detail (detection + validation)

- **Clustering choice:** per-day DBSCAN on flagged cells' lat/lon (eps = `dbscan_eps_cells` *
  resolution in degrees), then union-find linking of day-to-day blobs within `link_radius_km`
  (300 km) into multi-day events. Chosen over a single 3-D spatiotemporal DBSCAN because the
  latter on ~2.6M flagged cells is intractable; per-day + linking is fast and gives tracks.
- **Trigger classification:** at inception, compare normalized `|∇Q|` (heat) vs normalized
  `1/ε` (terrain); larger wins. **Precursor ramp:** slope of charge at inception cell over the
  prior `window_days`.
- **Validation:** per-prediction "coverage" of disasters (haversine ≤ radius AND within ±window
  of the active period). Recall, precision, analytic binomial p-value vs uniform space-time null,
  and a precision-recall curve (predictions added strongest-stress-first). Split exact/estimated.

### KEY RESULT (first config: mean / linear-ε / 97.5pct / 1.5° / 100km-48h)
- 7,053 predicted events; 2,991 disasters in the 2010-2019 window.
- **Recall 0.1%, Precision 0%, p=0.42** at 100 km → no skill at the strict scale.
- Radius sweep: significant only at 750-1000 km (p=1e-3 .. 7e-18) but ~3-8% recall.
- **Diagnostic:** predictions cluster on Himalaya/Andes/poles (low ε amplifies breakdown);
  disasters cluster in populated lowlands → spatial mismatch (see outputs/phase4 map).

### Obstacles found in Phase 3/4
| Obstacle | Status |
|---|---|
| `sklearn` not installed | `pip install scikit-learn` |
| Polar artifact: degree-based gradient distorts near poles | KNOWN, to fix (km/cos-lat gradient or mask |lat|>70) |
| 100 km match radius < 1 cell (167 km) at 1.5° | Metric near-impossible at this resolution; use ~200-300 km or finer grid |
| Predictions terrain-dominated | Likely ε range too wide; sweep eps_min/eps_max + permittivity method |

### Interpretation
The capacitor analogy, *as first configured*, does not predict disasters better than chance at
strict scales — a legitimate (proposal-sanctioned) exploratory null. But this is ONE point in a
large knob space (ε method/range, daily statistic, window/decay, threshold) and is confounded by
the polar artifact, the resolution-vs-radius mismatch, and validating heat-physics against mostly
flood disasters. Real conclusion requires the experiment sweep (see ROADMAP "Next scientific steps").

## Cleanups + ε sweep (post-first-result tuning)

**Code changes made:**
- `breakdown.py`: gradient now computed in **km** (cos-lat factor on the E-W component), not
  per-degree — fixes the high-latitude distortion.
- `flag_zones(lat_limit=)`: excludes |lat| > `domain.analysis_lat_max` (66°). Disasters max out
  at 62°, so this loses nothing and removes polar false positives.
- Memory: ERA5 + terrain now cast to **float32** (halves RAM); terrain now **cached locally**
  (`topo_*.nc`) so runs after the first need **zero network**.
- `run_experiment.py`: sweeps ε recipes; computes charge ONCE then re-scores each cheaply.
- `run_all.py`: one-shot report (dashboard + console).

**ε sweep result (1.5°, cleaned up), recall% at 150/250/500 km:**
| ε | 150 | 250 | 500 |
|---|---|---|---|
| control (no terrain) | 0.6 | 1.5 | 3.8 |
| eps_min 0.2 (orig) | 0.5 | 1.0 | 4.1 |
| eps_min 0.4 | 0.5 | 1.1 | 4.7 |
| eps_min 0.5 | 0.4 | 1.3 | 4.7 |
| eps_min 0.6 | 0.5 | 1.2 | 4.8 |
| eps_min 0.7 | 0.4 | 1.5 | 4.6 |

**Findings:**
1. **Cleanups ~tripled recall** at 500 km (eps 0.2: 1.4% → 4.1%) by removing polar/edge waste.
2. **Best ε range is 0.4–0.6** (original 0.2 was too terrain-heavy). Locked in **eps_min 0.5**.
3. **Terrain barely contributes** — the "no terrain" control nearly matches the best ε. The
   predictive signal (such as it is) comes from the charge gradient, not the dielectric/ε half.
4. **Still weak overall** (~5% @500 km, ~1.3% @250 km) — far below the 30% target. p-values are
   "significant" only because the random null is ~0.05%; significant ≠ practically useful.

## OBSTACLE: memory crash (user PC, 16 GB)
- Cause: THREE heavy jobs at once — user ran `run_all` while two background jobs (ε sweep +
  0.7° pull) were also building GB-sized arrays. Combined > 16 GB → cap/reset.
- Fixes: float32 everywhere; terrain cached locally; **one heavy job at a time**; never run
  background jobs while the user is running scripts. Corrupt 652-byte partial cache deleted.

## Performance / memory optimizations (after the 0.7° run locked the PC for ~20 min)

Root causes of the heaviness: (a) memory overflow → disk swapping froze the cursor (0.7° cube
~1.9 GB × several copies → 6-8 GB peak); (b) per-day DBSCAN loop over 3,652 days pegged a CPU.

Fixes (verified on 1.5°; physics tests still pass):
- **Low priority** (`util.lower_priority()`, BELOW_NORMAL on Windows) — heavy runs no longer
  freeze the cursor. Called at the top of `run_all.py` / `run_experiment.py`.
- **Fast clustering** — replaced per-day DBSCAN with `scipy.ndimage.label` connected-components
  (`analysis/clustering.py`). Now **config-switchable**: `clustering.algorithm: components` (fast,
  default) | `dbscan` (original, slower, kept for fidelity).
- **Faster event characterization** — `events.py` now uses numpy index lookups instead of per-event
  xarray `.sel()` (29 s → 18 s for clustering+events at 1.5°).
- **Memory** — float32 everywhere; terrain cached locally; `run_pipeline(keep_temp=False)` frees the
  temperature cube for `run_all` (~1 array of RAM saved).
- **Process rule:** warn the user (expected time + RAM) and get an explicit OK before any heavy run;
  never run background jobs while the user is running scripts (3 concurrent jobs caused the crash).

**Trade-off noted:** connected-components vs DBSCAN changes the grouping — at 1.5°/eps_min 0.5,
7,421 events vs DBSCAN's 10,309, recall@250km 0.8% vs 1.3% (both weak; conclusion unchanged).
Switchable via config so nothing is lost.

## GDIS (precise disaster coords) — could NOT auto-fetch
- All sources require auth: SEDAC/NASA Earthdata login, GEE `ee` auth; DataLumos 403; data.nasa.gov
  direct file 404. User must download the CSV manually (free Earthdata login) from
  https://sedac.ciesin.columbia.edu/data/set/pend-gdis-1960-2018/data-download .
- Plan when available: join GDIS (coords) to existing EM-DAT (dates) on `disasterno`/`DisNo.`.

## GDIS validation result (1.5°, eps_min 0.5, precise coordinates)

7,421 predicted events vs 13,292 precisely-located GDIS disaster-locations (2010-2019):
| radius | recall | precision | p-value |
|---|---|---|---|
| 100 km | 0.19% | 0.15% | 2.8e-07 |
| 250 km | 0.89% | 0.42% | 5.4e-19 |
| 500 km | 3.46% | 1.58% | 3.9e-67 |

- Precise coords did NOT change the verdict (vs country-centroid: ~same ~1% @250km). So the weak
  result is NOT a geolocation artifact — it's real.
- **The tiny p-values are a sample-size artifact**, not practical skill: 7.4k preds × 13.3k disasters
  means even a hair above the uniform-random null is "significant." Recall/precision are the honest
  metrics, and they're ~1-3.5% — far below targets (30% / 10%).
- **Consistent conclusion across all levers (cleanups, ε tuning, precise data): weak/null.** The
  capacitor breakdown zones and real disasters mostly occupy different places. A legitimate negative
  result per the proposal. Remaining lever: 0.7° resolution (unlikely to reach targets).

## Temporal lookback (precursor) sweep — FINAL result (1.5°, GDIS)

Idea: a disaster counts as predicted if breakdown was flagged up to `lookback` days BEFORE it
(the capacitor "charges" then "discharges"). Swept radius x lookback (7,421 preds, 13,292 GDIS locs):

RECALL %:           2d    7d   15d   30d        | best 8.12% @ 500km/30d, but p=1.0
  100km           0.19  0.25  0.29  0.39
  250km           0.89  1.10  1.43  2.17
  500km           3.46  4.23  5.94  8.12

- Recall rises with lookback, BUT the p-value collapses to ~1.0 at wide windows -> the gain is
  MECHANICAL (more days = more chance overlap), NOT skill. The null accounts for window width.
- At tight matching (lookback 2d) results ARE significant (p=4e-67 @500km) but recall is tiny
  (~3.5%). So: a statistically real but practically negligible signal.
- **Precursor timing does NOT rescue the theory.**

## Verdict (summary)
Across ALL levers (km-gradient + pole-mask cleanups, eps sweep, precise GDIS coords, finer 0.7°
grid attempt, temporal-lookback/precursor sweep): the "Climate Capacitor" analogy shows a
**statistically detectable but practically negligible** association with disaster locations
(~1-3% recall at meaningful scales; far below the 30% target). Terrain (the dielectric half) adds
almost nothing. (Full conclusions at the bottom of this file.)

## Hardware note
0.7° (~78 km) caused a BSOD on the 16 GB laptop even at low priority (memory swapping is the limit,
not CPU). Default config locked to 1.5° (laptop-safe). 0.7°/0.25° require >=32 GB RAM — left as a
config switch (resolution_deg + cloud_uri) for a bigger machine / the project partner.

## Current config (default = laptop-safe 1.5°)
- Resolution **1.5° (~150 km)**, WeatherBench2 240x121 store; daily statistic **mean**;
  permittivity linear **eps_min 0.5**; pole mask 66°; charge 30 d / decay 0.02; threshold 97.5 pct;
  clustering **components**; disasters **GDIS**.
- Finer grids (0.7° / 0.25°) are a config switch (`resolution_deg` + `cloud_uri`) — need >=32 GB RAM.

## Real-world sanity checks observed

- 2010-08-05 anomaly map shows a strong hot blob over western Russia = the **2010 Russian
  heatwave**, recovered from real data without prompting. Elevation/land-fraction sane
  (land ≈ 0.34, Himalaya cell ≈ 3117 m).

---

## Ideas we tried/considered and dropped (short)

- **Validate against heatwaves only** — considered (the model is heat-physics), but dropped: the
  theory isn't about heat *blobs*, it's about steep hot↔cold gradients discharging into *any*
  disaster. So we validate against **all climate disaster types**; the disaster *type* is bonus
  info, not the target. (We flag a breakdown, then ask "did any disaster hit there, around then?")
- **Predict from raw charge level instead of the gradient** — proposed, rejected: departs from the
  pure analogy (discharge = gradient between extremes). Kept `‖∇Q‖/ε`.
- **Local (time) normalization of stress before flagging** — considered, dropped: would hide places
  that always have steep gradients, which is exactly what the theory says should break down. Kept
  the raw spatial gradient.
- **Event duration matching** (terrain controls how long a discharge lasts) — nice in theory, but
  EM-DAT durations are coarse/missing and we work in daily steps (a 5-hour tornado is invisible).
  Left as a bonus, not pursued.
- **Subdividing our coarse cells ourselves** — rejected: upsampling adds no real detail (just a
  blurrier-looking finer grid) and can fake a better score. Only real finer source data helps.

## Failed / low-impact tweaks (what did NOT move the needle)

- ε (terrain) tuning: best (eps_min 0.4–0.6) only marginally beat the worst; **no-terrain control
  scored about the same** → the dielectric idea adds ~nothing.
- Precise GDIS coords vs country centroids: **no real change** → weak result isn't a data artifact.
- Precursor lookback (2→30 d): raised raw recall but **p→1.0** → the gain is chance, not skill.
- Finer 0.7° grid: **crashed the laptop (BSOD)**; lookback-2d column matched 1.5° anyway, so it
  would not change the verdict.

---

## FINAL VERDICT & CONCLUSIONS

**The question:** does the "Climate Capacitor" analogy — heat builds up like electric charge,
terrain acts like a dielectric, and steep hot↔cold gradients "break down" into disasters —
actually predict where and when real disasters happen?

**The answer: No, not in any useful way.**

1. **Best honest skill ≈ 1–3%** of disasters caught within a meaningful distance + time window —
   far below the project's 30% target. Precision similarly tiny.
2. **The signal is statistically real but practically negligible.** Big "significant" p-values
   (e.g. 1e-67) are a *sample-size* effect (thousands of predictions × thousands of disasters),
   not real predictive skill. Recall/precision are the honest metrics, and they're near zero.
3. **The terrain ("dielectric") half adds almost nothing** — turning terrain off scored about the
   same. Whatever faint signal exists comes from the heat-gradient, not the capacitor-specific idea.
4. **The precursor-timing idea didn't rescue it** — wider lookback raised raw recall but not skill.
5. **Robust across everything we tried:** cleanups, ε sweep, precise GDIS coordinates, finer grid,
   precursor timing — same weak/null conclusion.

**Most likely why:** the model's high-stress zones and real disasters mostly sit in *different
places*. Real disasters depend on moisture, weather systems, population and infrastructure that a
temperature+terrain analogy ignores.

**This is a valid, valuable result.** The proposal explicitly states that a clear negative result —
mapping the limits of physical analogies in climate modeling — is as scientifically useful as a
positive one. We tested the analogy fairly and thoroughly; it does not hold up as a predictor.

**If the partner wants to push further (needs >=32 GB RAM):**
- Run the 0.7° / 0.25° grids (config switch) to confirm at finer resolution.
- Sweep charge `window_days` / `decay` (different accumulation timescales).
- Implement the `"extreme"` daily statistic (most-anomalous-moment).
- Low odds of changing the verdict, but they make the negative result airtight.
