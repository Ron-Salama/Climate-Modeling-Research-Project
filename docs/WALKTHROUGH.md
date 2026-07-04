# Walkthrough — What the project actually does

A plain, linear tour of the whole project: the major steps, what each plot shows,
and every experiment ("edge case") we ran. For decisions/obstacles see
`PROJECT_LOG.md`; for the plan see `ROADMAP.md`.

---

## Part 1 — The major steps (the pipeline, in order)

The program runs one chain of steps. Each step feeds the next.

1. **Get the data.**
   - *Temperature:* 10 years of global ERA5 (2010–2019), streamed from a public
     cloud store (WeatherBench2) — no bulk download; only the slice we use is pulled, then cached.
   - *Terrain:* elevation/slope/roughness comes from the **same** store (no extra download).
   - *Disasters:* EM-DAT (gives the dates) joined with GDIS (gives precise coordinates).

2. **Anomaly** — for every cell, every day: temperature minus that cell's *normal* for
   that day of the year. Positive = hotter than usual, negative = colder. (Removes seasons.)

3. **Charge** — add up each cell's anomalies over a sliding **30-day window** (with a slow
   decay). This is the "capacitor charging": persistent heat builds up as positive charge,
   persistent cold as negative.

4. **Permittivity (ε)** — turn terrain into a "dielectric" number per cell: smooth/flat = high ε
   (energy escapes easily), rugged mountains = low ε (energy gets trapped).

5. **Breakdown field** — `E = ‖∇Q‖ / ε`: the *spatial gradient* of charge (how sharply it
   changes between neighbouring cells) divided by the terrain ε. It's largest where a hot
   region sits next to a cold region over rugged terrain. We then **flag** the top-stress
   cells (and exclude the poles, which have no disasters).

6. **Cluster into events** — group neighbouring flagged cells into blobs, and link them
   day-to-day into multi-day "events" (each a predicted storm/heatwave-shaped object).

7. **Characterize each event** — where/when it started (the "spark"), whether it's
   heat-driven or terrain-driven, and its charge build-up curve.

8. **Validate** — compare each predicted event to real disasters (within a distance + time
   window) and score it: **recall**, **precision**, **p-value**.

---

## Part 2 — Every plot (what it shows, where it lives)

**Synthetic test world** — `outputs/phase1/` (from `run_synthetic.py`):
proves the pipeline works before using real data. We plant a fake heatwave; the model finds it.
| File | Shows |
|---|---|
| `1_temperature.png` | The made-up temperature |
| `2_anomaly.png` | Hotter/colder than normal (red/blue) |
| `3_charge.png` | Accumulated charge — the planted heatwave is the red blob |
| `4_permittivity.png` | The terrain (ε) map |
| `5_breakdown.png` | Stress map + flagged risk zones — lights up on the planted heatwave |

**Real Earth** — `outputs/phase2_real/` (from `run_real.py`): the same five maps on real
data. In `2_anomaly.png` the **2010 Russian heatwave** shows up as a big red blob over
western Russia — a good reality check.

**Validation** — `outputs/phase4/` (from `run_validate.py`):
| File | Shows |
|---|---|
| `predicted_vs_actual.png` | Red = predicted zones, blue = real disasters — they mostly *don't* overlap (the negative result). |
| `predicted_vs_actual_clean.png` | Same, tidied (poles excluded) — used on the poster |
| `precision_recall.png` | Precision vs recall as we include more predictions |

**One-page summary** — `outputs/report/dashboard.png` (from `run_all.py`): all the key maps,
the predicted-vs-actual map, and the metrics on a single image.

---

## Part 3 — Every experiment / edge case we ran

We didn't rely on one setting — we swept the important knobs and scored each against disasters.

| What we varied | Values tested | Result |
|---|---|---|
| **Terrain weighting** (ε) | none / 0.2 / 0.4 / 0.5 / 0.6 / 0.7 | 0.4–0.6 best, but the "no-terrain" control scored about the same → **terrain adds almost nothing** |
| **Match radius** | 100 / 250 / 500 / 1000 km | recall rises with a looser radius (0.2% → 8%) but stays far below target |
| **Early-warning lookback** | 2 / 7 / 15 / 30 days | recall rises, **but p-value → 1.0** → the gain is just chance, not skill |
| **Daily statistic** | mean / max / min | **max is best** (4.8% vs 3.5% recall @500 km — heat extremes matter most), still far below target |
| **Resolution** | 1.5° (tested) ; 0.7° (attempted) | 0.7° crashed the laptop (needs ≥32 GB RAM); wouldn't change the verdict |
| **Disaster coordinates** | country-centroid vs precise GDIS | precise coords gave the same weak result → not a data-quality artifact |
| **Clustering method** | DBSCAN vs connected-components | components ~100× faster, same conclusion |

Two fixes along the way that mattered: computing the gradient in **kilometres** (not degrees)
and **excluding the poles** — together these roughly *tripled* the apparent skill (by removing
false predictions at the edges), which is why a clean pipeline was needed before trusting any result.

---

## Part 4 — The bottom line

Best honest skill: **~1–3% recall** (of real disasters caught) and **<2% precision** (of alarms
that were right) — far below the targets of 30% and 10%. The big "significant" p-values are a
sample-size effect, not real skill.

**Verdict: the Climate Capacitor analogy does not usefully predict real disasters.** Its
high-stress zones and real disasters mostly sit in different places, terrain adds little, and no
setting we tried rescued it. This is a **clear, valid negative result** — it maps the limits of
applying electrical-capacitor physics to climate, which the project brief counts as a real contribution.
