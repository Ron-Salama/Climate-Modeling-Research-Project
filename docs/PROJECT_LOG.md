# Project Log — Design Decisions, Methodology, and Results

A record of the design choices, experiments run, and findings for the Climate
Capacitor study. Companion to `ROADMAP.md` (plan), `WALKTHROUGH.md` (what the
project does), and `CODE_GUIDE.md` (how the code is organised).

---

## Data sources

| Data | Source | Notes |
|---|---|---|
| Temperature (ERA5) | WeatherBench2 ERA5 (public Zarr on Google Cloud) | Streamed, then cached; 6-hourly, aggregated to daily |
| Terrain | Same WeatherBench2 store (`geopotential_at_surface`, `land_sea_mask`, orography std) | elevation = geopotential / 9.80665 |
| Disasters — dates | EM-DAT (International Disaster Database) | dates + types; precise coordinates mostly absent |
| Disasters — coordinates | GDIS (geocoded EM-DAT) | precise lat/lon; joined to EM-DAT dates by disaster number. Primary truth set. |
| Country centroids | eesur/country-codes-lat-long | fallback coordinates for EM-DAT-only mode |

Scientific anchors (proposal literature review): IPCC AR6 (2021); Perkins-Kirkpatrick
& Lewis (2020); Woollings et al. (2018); Lin et al. (2001); Brooks (2013); Rycroft
et al. (2000); Bak et al. (1987).

---

## Design decisions

1. **Modular pipeline, config-driven.** Each stage is a small module; `pipeline.py`
   chains them. All parameters live in `config/default.yaml`, so experiments are
   configuration changes rather than code edits (supports maintainability and auditability).
2. **Pluggable permittivity (ε).** `physics/permittivity.py` registers several
   terrain→ε parameterisations (`linear`, `log`, `slope`, `combined`); the config
   selects one by name, enabling systematic comparison.
3. **Anomaly-based charge.** The "charge" is built from temperature *anomalies*
   (deviation from each cell's day-of-year climatology), not raw temperature, so the
   model responds to unusual build-up rather than the fixed seasonal/geographic pattern.
4. **Coarse-global, daily, single variable.** 1.5° + daily + 2 m temperature keeps the
   core dataset near ~1 GB and tractable, avoiding the terabyte volumes of hourly,
   fine-resolution, multi-variable ERA5.
5. **float32 throughout** the physics, and a **standardised (time, lat, lon)** array
   order across loaders and visualisation.

---

## Methodology (pipeline)

```
temperature → anomaly → charge (30-day accumulation, with decay)
            → permittivity (terrain) → breakdown field  E = ‖∇Q‖ / ε
            → flag high-stress cells → cluster into events → validate vs disasters
```

Events are formed by connected-component clustering per day, linked across days into
multi-day events, then characterised (inception point, trigger type, precursor curve).

---

## Validation approach

Predicted events are matched to real disasters within a **spatial radius** and a
**temporal window** (with an optional early-warning *lookback*). Metrics:

- **Recall** — fraction of disasters caught by ≥1 prediction.
- **Precision** — fraction of predictions that hit ≥1 disaster.
- **p-value** — a binomial test versus a uniform space-time null.

Evaluation options (all in config): disaster-type groups (`full` / `thermal` /
`temperature`), a prediction budget (operating point), a latitude cut, and a
per-cell field choice (`gradient` / `charge` / `combined`). Predictions and
disasters are both confined to the analysis latitude band for a fair comparison.

---

## Experiments (parameter sweeps)

| Knob | Values tested | Finding |
|---|---|---|
| Permittivity (ε) range/method | control/0.2–0.7 · linear/log/slope | best 0.4–0.6, but a "no-terrain" control scores similarly → terrain adds little |
| Resolution | 1.5° / 1.0° / 0.703° | recall rises with resolution (strongest lever) |
| Disaster type | full / thermal / temperature | strongest on temperature (heat/cold) — the model's physical domain |
| Daily statistic | mean / max / min | `max` slightly best (heat extremes); choice does not change the verdict |
| Temporal lookback | 2 / 7 / 15 / 30 days | wider window raises raw recall but p → 1 (chance); not real skill |
| Prediction budget | all / match | keeping only the strongest predictions lowers recall (strength ≠ correctness) |
| Field | gradient / charge | gradient misses uniform heatwaves; charge flags them but is crowded by high-latitude charge |
| Latitude cut | 66° / 60° / 55° | excluding poles removes unmatchable predictions and improves precision |

---

## Key findings

1. **Strongest signal on temperature disasters** — the model's physical domain —
   and **recall improves as resolution increases** (a real, scale-dependent signal).
2. **The terrain (dielectric) component contributes little** — a no-terrain control
   performs comparably.
3. **Breakdown as a gradient misses uniform extremes.** A heatwave is a large,
   near-uniform hot region: high accumulated charge but low spatial gradient, so the
   `‖∇Q‖` formulation does not flag it (verified on the 2010 Russian heatwave, where
   charge was very high but the breakdown field stayed below threshold).
4. **The poles are noisy and disaster-free**; excluding high latitudes gives a cleaner,
   fairer evaluation and improves precision.
5. **p-values are significant but sample-size driven**; recall and precision are the
   metrics that reflect practical usefulness.

---

## Results (final, poles excluded, 0.703° — the finest grid tested)

| Disaster type | recall @250 km | recall @500 km | precision @250 km |
|---|---|---|---|
| temperature | 4.5% | **20.3%** | 0.15% |
| thermal | 4.8% | 18.5% | 0.29% |
| full | 4.8% | 15.4% | **1.6%** |

Targets: recall > 30%, precision > 10%, p < 0.05.

---

## Verdict and conclusions

The Climate Capacitor analogy captures a **real, physically-consistent thermal
signal** — strongest for temperature disasters and improving with resolution (up to
~20% regional recall at 0.703°). However, it is **too imprecise to serve as a
predictor**: precision remains around 1% and pinpoint recall (100 km) near zero, both
far below the success targets. It identifies broad regions of thermal stress but not
the specific location or timing of individual disasters.

This is a **valuable negative result**: it maps both the promise and the hard limits
of applying electrostatic physics to climate, as the proposal anticipated.

---

## Limitations and future work

- **Precision is limited by over-prediction** — the model flags far more cells than
  there are disasters, and its confidence (peak stress) does not rank predictions by
  correctness.
- **Gradient-based breakdown misses uniform extremes**; a charge-level formulation, or
  a blend, could capture heatwaves the gradient misses.
- **Anomalies remove permanent climatic gradients** (e.g. the polar front) that also
  drive real weather; combining base-state and anomalous gradients is a natural extension.
- **Additional physical variables** (moisture, atmospheric flow) are likely needed for
  the analogy to become predictive.

---

## Compute notes

The default **1.5° grid runs on a standard laptop** (~1 GB cached, ~2 GB peak RAM).
Finer grids are heavier: **1.0° ≈ 3 GB peak; 0.703° ≈ 5–7 GB peak (≥32 GB RAM
recommended); 0.25° considerably more.** Climate data is downloaded once and cached;
subsequent runs are offline.
