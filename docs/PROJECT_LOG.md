# Project Log — Design Decisions, Methodology, and Results

**This is the canonical, self-contained record of the Climate Capacitor study** — the
theory, the method, every experiment, the final numbers, and the verdict. It is written to
stand alone: someone (or something) reading only this file should understand the whole
project well enough to write it up. Companion docs: `ROADMAP.md` (plan/phase history),
`WALKTHROUGH.md` (a plain tour), and `CODE_GUIDE.md` (how the code is organised).

---

## The hypothesis (the analogy)

The project (capstone **26-1-R-14**) tests one idea: **can extreme-weather disasters be
predicted by modelling the Earth's surface as an electrical capacitor?** The Earth is split
into a grid of cells, and each electrical quantity maps to a climate quantity:

| Electrical | Climate quantity | Computation |
|---|---|---|
| Charge `Q` | Accumulated thermal anomaly | sliding-window sum of (temperature − climatology), with decay |
| Permittivity `ε` | Terrain's resistance to discharge | `f(elevation, slope)`; smooth/flat → high ε, rugged → low ε |
| Breakdown field `E` | Atmospheric "stress" | `E = ‖∇Q‖ / ε` per cell per day |
| Breakdown event | Predicted extreme-weather disaster | cells where `E` exceeds a critical threshold, then clustered |

**Why anomalies, not raw temperature.** The "charge" is built from temperature *anomalies*
(each day minus that cell's day-of-year climatology, averaged over the 10 years and smoothed
±15 days), so the model responds to *unusual* build-up rather than the fixed
seasonal/geographic pattern (the tropics being permanently hotter than the poles is not a
disaster signal). The anomaly is **signed** (hot = +, cold = −), and this sign is never
discarded, because the breakdown field is a *gradient*: it peaks where opposite charges sit
adjacent — like the field between a capacitor's + and − plates — so hot–cold *contrast*, not
absolute heat, drives breakdown.

**The central diagnostic tension** (see Key findings #3): a gradient-based breakdown responds
to *contrasts / edges*, but many real disasters — heatwaves especially — occur at the
*centre* of a large, near-uniform extreme, where the gradient is low. This mismatch is the
core reason the analogy underperforms, and it is the single most important thing to carry
forward.

The project brief states explicitly that a **clear negative result is a valid scientific
outcome** — the goal is to map the limits of the analogy, whichever way it falls.

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

> **Reading the numbers honestly:** recall@500 km is a *regional* score (did we flag
> anywhere within 500 km of the disaster) and is the "generous" headline (~20% for
> temperature). recall@250 km and precision are the practical numbers, and they are low.
> Pinpoint recall (100 km) is near zero. So the ~20% is real but coarse-grained.

### Reproducing the headline numbers

The final table above comes from the **finest grid**, poles excluded. In
`config/default.yaml`:

- `domain.resolution_deg: 0.703` **and** `data.era5.cloud_uri:` set to the matching
  512×256 WeatherBench2 store (the commented `cloud_uri_0p7deg` line). These two must
  change together.
- `analysis_lat_max: 55` (excludes poles for both predictions *and* disasters).
- `breakdown.field: gradient`, `breakdown.threshold_value: 97.5`.
- `disasters.types: temperature` (or `thermal` / `full` for the other rows).
- `validation`: match radius 250 km and 500 km give the two recall columns.
- The laptop **default is 1.5°**, which gives weaker absolute numbers (a few %); it is the
  light demo grid, not the headline. Recall rises monotonically with resolution.

> ⚠️ The 0.703° grid needs ≥32 GB RAM (~5–7 GB peak). It was run once to produce these
> numbers; the shared default stays at 1.5° so the repo runs on any laptop.

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
