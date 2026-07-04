# Demonstration Guide — Climate Capacitor

How to show the project live, from Spyder, in one run (≈ 5 minutes).

## Before the demo (do this once, beforehand)
- Open the project in **Spyder** with its interpreter pointed at the project's `.venv`.
- **Run `scripts/run_all.py` once ahead of time** so the climate data is already
  downloaded and cached — then nothing downloads while you present.

## The demo — one run
1. In Spyder, open **`scripts/run_all.py`** and press **F5** (Run).
2. Two things appear:
   - the **console** prints the summary (predicted events + the recall / precision numbers),
   - the **dashboard figure** shows up in the **Plots panel** (all maps + results on one image).
   *(It's also saved to `outputs/report/dashboard.png` as a backup.)*
3. Talk over the dashboard — point at:
   - the maps: **temperature → anomaly → charge → terrain (ε) → breakdown**,
   - the **predicted-vs-actual** map (red = our predicted zones, blue = real disasters),
   - the **numbers**: on the 1.5° laptop grid, recall is a few % (it rises to **~20%** at a
     regional 500 km scale on the finest 0.7° grid), Precision ~1–2% (targets were 30% / 10%),
   - the **daily-statistic comparison** (max is best, still far short).

## What to say
*"We model the Earth as a capacitor — heat builds up as 'charge', terrain acts as a
'dielectric', and a disaster is the 'breakdown' where a steep hot–cold gradient
discharges. Running it on 10 years of real data, we found a real but weak thermal signal:
at the finest grid it recovers up to ~20% of temperature disasters at a regional scale, and
that signal strengthens with resolution. But the precision is ~1–2% and it can't pinpoint
individual disasters — well below our targets. So the analogy captures broad thermal stress
but doesn't work as a precise predictor. That's a clear, valid negative result: it maps both
the promise and the limits of applying this physics to climate — and it held up across every
setting we tested (terrain weighting, resolution, precise coordinates, timing)."*

## Optional extra — prove the pipeline on a test world
If you want to show the method works before the real data: run **`scripts/run_synthetic.py`**
(F5). It runs on a *made-up* world with a **planted heatwave**; the charge and breakdown
maps light up exactly on it — proof the code finds what it should.

## Optional (advanced) — showing edge cases & finer grids

**Switch an edge case** (e.g. use the hottest moment of each day instead of the average):
1. Open `config/default.yaml`, change one line — e.g. `daily_statistic: mean` → `max` — and save.
2. Re-run `run_all.py` (F5) and compare the new numbers.
   Or run a ready-made sweep that tries several at once and prints a table:
   `run_stat_sweep.py` (mean/max/min), `run_experiment.py` (terrain ε), `run_final.py` (radius × lookback).

**Run a finer grid** (more map detail — heavier). In `config/default.yaml` change **two lines**
to a matching pair, then run `run_all.py`:
| Grid | `resolution_deg` | `cloud_uri` | RAM needed |
|---|---|---|---|
| Default | `1.5` | 240x121 store | ~2 GB (any laptop) |
| Finer | `1.0` | 360x181 store | ~3 GB (fine on a good laptop) |
| Fine | `0.703` | 512x256 store | ~5–7 GB (needs ≥ 32 GB) |

Notes:
- The finer grid's **first run re-downloads** (~1 GB for 1.0°, ~2 GB for 0.7°) into a new cache;
  after that it's reused.
- **If the machine slows down (memory pressure), stop the run** (Stop button in Spyder, or Ctrl+C)
  and go back to `1.5`. The 0.7° grid needs ≥ 32 GB RAM — only run it on a large-memory machine.
- To go back, set `resolution_deg: 1.5` and the 240x121 `cloud_uri` again.

## Likely questions (quick answers)
- **What is Recall?** Of the real disasters, how many we caught (within a distance + time
  window). Regionally (500 km) it reached ~20% at the finest grid; at pinpoint scale it's tiny.
- **What is Precision?** Of our alarms, how many were right. Small (~1–2%) → most were false.
- **Why is a negative result okay?** The project brief says a clear negative — mapping the
  limits of a physical analogy — is as valuable as a positive one.
- **How do you test other settings?** Change one value in `config/default.yaml` and re-run
  (see the User Manual). We also have sweep scripts (`run_stat_sweep.py`, `run_experiment.py`).
