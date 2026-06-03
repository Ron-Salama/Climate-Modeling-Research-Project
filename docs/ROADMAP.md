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
- [ ] **Phase 2 — Data layer:** ERA5 cloud loader + regrid + cache; ETOPO loader + regrid;
  EM-DAT parser → tidy events table. Same interfaces the synthetic test already uses.
- [ ] **Phase 3 — Detection:** threshold zones → DBSCAN/KMeans events → origin, precursor
  curve, trigger classification (heat- vs terrain-driven).
- [ ] **Phase 4 — Validation:** match predicted events to EM-DAT (100 km / ±48 h);
  recall / precision / p-value / ROC. Targets: recall>0.30, precision>0.10, p<0.05.
- [ ] **Phase 5 — Visualization:** predicted-vs-actual heatmaps, precursor plots, optional animations.

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
