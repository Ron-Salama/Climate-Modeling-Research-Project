# Climate Capacitor — Build Roadmap

Source of truth for scope and sequencing. The proposal (`Final_Project_A_26-1-R-14..docx`) is the *what/why*; this is the *how/when*.

## Core idea (the analogy)

| Electrical | Climate quantity | Computation |
|---|---|---|
| Charge `Q` | Accumulated thermal anomaly | Sliding-window integral of (T − climatology), with decay |
| Permittivity `ε` | Terrain's resistance to discharge | `f(elevation, slope)`; smooth→high ε, rugged→low ε |
| Breakdown field `E` | Atmospheric "stress" | `‖∇Q‖ / ε` per cell per day |
| Breakdown event | Predicted extreme weather | Cells where `E` exceeds a critical threshold, clustered |

Exploratory by design: a clean **null result is a valid scientific outcome**.

## Feasibility decision (settled)

- **Coarse-global, 1° (~100 km), daily, 2m-temperature, 10 yr** → core cube ≈ **~1 GB**. Runs on a laptop.
- ERA5 via **cloud-streamed ARCO-ERA5** (Zarr on GCS) — no bulk download — or a cached regridded subset.
- EM-DAT: small, **manual one-time export** (login-gated at emdat.be).
- Topography: **ETOPO** (not SRTM — SRTM 30 m is overkill for 1°).
- Resolution/region are config knobs → can refine to 0.25° regionally later with no rewrite.

## Phases

- [x] **Phase 0 — Scaffold:** repo structure, `config/default.yaml`, deps, the pluggable
  `permittivity` abstraction (terrain→ε registry).
- [x] **Phase 1 — Physics core (synthetic data):** `anomaly` → `charge` (window+decay)
  → `breakdown` field. Fully implemented + a synthetic smoke test (`scripts/run_synthetic.py`)
  runnable with **no downloads**. Verified: planted heatwave stands out 30x above median; unit tests pass.
- [x] **Phase 2 — Data layer:** ERA5 cloud loader (WeatherBench2 1.5deg, parallel fetch + cache);
  terrain derived from same store (elevation/slope/roughness/land-mask, no extra download);
  EM-DAT parser → tidy events table with **country-centroid fallback** (`geo_precision` =
  exact|estimated, so heatwaves with no coords are still usable). `scripts/run_real.py` runs the
  full pipeline on the real Earth. Verified: 2010 Russian heatwave appears in the anomaly map.
  - Source switched to WeatherBench2 (public, no CDS account, daily-max from 6-hourly).
  - Data status: full 10-yr (2010-2019) ERA5 cube cached (~840 MB); EM-DAT 4,018 climate events
    (616 exact + 3,402 estimated).
- [x] **Phase 3 — Detection:** per-day DBSCAN blobs → union-find temporal linking → event
  catalog with inception, duration, peak stress, trigger (heat/terrain), precursor ramp.
  (`pipeline.py`, `analysis/clustering.py`, `analysis/events.py`, `scripts/run_detect.py`.)
  First run: 7,053 predicted events over 2010-2019.
- [x] **Phase 4 — Validation:** coverage matching + recall/precision + analytic p-value +
  precision-recall curve, split by exact/estimated. (`analysis/validation.py`,
  `scripts/run_validate.py`.) **First-config result: weak/null** (see below).
- [~] **Phase 5 — Visualization:** field maps, predicted-vs-actual map, PR curve all done.
  Remaining nice-to-haves: time animation, precursor-curve plots, cartopy coastlines.

## RESULTS — first configuration (mean / linear-ε / 97.5pct / 1.5° / 100km-48h)

- Recall **0.1%**, Precision **0%**, p=0.42 → **no skill at the strict 100 km scale**.
- Signal only emerges at coarse radius: significant (p<0.05) at **750-1000 km**, but still
  only ~3-8% recall. So at best a weak, region-scale association.
- **Why (diagnostic map):** predictions concentrate on rugged terrain (Himalaya/Andes) and
  poles because low-ε amplifies the breakdown field there; real flood/storm disasters cluster
  in populated lowlands. Spatial mismatch ⇒ near-zero overlap.
- **Caveats / artifacts to address before concluding:**
  - Polar artifact: spatial gradient is in degrees, distorted near poles (lon lines converge).
    Fix: compute gradient in km (cos-lat weighting) and/or mask |lat|>70.
  - 100 km match radius < one 1.5° cell (~167 km) → metric near-impossible at this resolution.
  - ε dynamic range may be too wide (terrain dominates). Try higher eps_min.
- **This is a legitimate exploratory result** (proposal: null results are valuable), but it's
  ONE point in the experiment space. The knobs below remain to be swept.

## Next scientific steps (the actual experiments)

- Fix polar gradient + retest. Try matching radius ~200-300 km (grid-appropriate).
- Sweep `permittivity.method` (linear/log/slope/combined) and `eps_min/eps_max`.
- Sweep `daily_statistic` (needs max/min cubes — extra pulls) + implement `"extreme"`.
- Sweep `charge.window_days`, `decay_per_day`, breakdown `threshold_value`.
- Validate against **heatwaves specifically** (the model is about heat) rather than all disasters.

## Principles

- **Architect-first, no throwaway:** physics modules are real (pure functions on arrays),
  tested on synthetic data, so real data slots into identical interfaces.
- **One config, reproducible runs:** every knob in `config/default.yaml`; nothing magic in code.
- **Auditability (NFR):** each stage logs enough to trace a breakdown back to raw inputs.

## Experiments to run (decided, not yet built)

- **Daily statistic: `max` vs `mean` vs `min`** — which correlates best with EM-DAT
  disasters? Controlled by `data.era5.daily_statistic` in config. `max` favors hot
  extremes, `min` cold extremes, `mean` is balanced. To be swept automatically in Phase 4.
- **Why both hot AND cold matter:** charge is *signed* (hot = +, cold = −), and the
  breakdown field is the *gradient* of charge (‖∇Q‖/ε), so it peaks where opposite
  charges sit adjacent — like the field between a capacitor's + and − plates. A uniform
  hot region gives a weak field; *contrast* drives breakdown. (So we must never discard
  the sign of the anomaly, regardless of which daily statistic we pick.)
- **Permittivity parameterization sweep:** `linear | log | slope | combined` (already a knob).
