# User Manual — Climate Capacitor

A short, plain guide to using the program.
*(To install it and download the data, see **SETUP.md** first. To run the live
presentation, see **DEMO.md**.)*

---

## What this program does

It tests one idea: can natural disasters (floods, storms, heatwaves) be predicted
by treating the Earth like a **battery/capacitor**? Heat "charges up" in each area
over time, and a disaster is the "spark" when that energy is released — especially
where a hot region sits next to a cold one, over rough terrain.

The program builds these "risk maps" from real climate data and checks them against
a database of real disasters.

---

## How to run it

Open a terminal in the project folder and type one of these:

| Type this | What you get |
|---|---|
| `python scripts/run_synthetic.py` | A quick demo on **made-up** data (no download) — 5 maps in `outputs/phase1/` |
| `python scripts/run_all.py` | The **full run** on real data — a report in `outputs/report/` |
| `python scripts/run_detect.py` | A list of predicted disaster events (a spreadsheet) |
| `python tests/test_physics.py` | Checks the calculations are correct |

> The **first** real run downloads about 0.8 GB of climate data (a few minutes).
> After that it's saved on your computer, so later runs are quick and need no internet.

*(Prefer Spyder? Point it at the project's `.venv`, then press F5 — the maps appear
in the Plots panel.)*

---

## Changing settings & testing scenarios (edge cases)

Everything is in one file: **`config/default.yaml`**. To test a different scenario:

1. Open `config/default.yaml` in any text editor.
2. Change **one value** (see the switches below) and **save**.
3. Re-run a script (e.g. `python scripts/run_all.py`).
4. Compare the new numbers/maps to the previous run.

**The switches you can flip:**

| Setting | Try changing it to… | Tests |
|---|---|---|
| `data.era5.daily_statistic` | `max` or `min` (instead of `mean`) | hottest / coldest moment vs the daily average |
| `permittivity.eps_min` | `0.2` … `0.9` | how much the terrain matters |
| `permittivity.method` | `log`, `slope`, `combined` | a different terrain formula |
| `charge.window_days` / `decay_per_day` | e.g. `15` / `0.05` | a faster/slower heat build-up |
| `breakdown.threshold_value` | e.g. `95` | flag more (or fewer) risk zones |
| `validation.spatial_radius_km` | `250`, `500` | a looser match distance |

> Keep `resolution_deg: 1.5` on a normal laptop — the `0.703` fine grid needs ≥32 GB RAM.

**Ready-made scenario sweeps** (they try several values automatically and print a table):
- `python scripts/run_experiment.py` — sweeps the terrain weighting (ε).
- `python scripts/run_stat_sweep.py` — sweeps the daily statistic (mean vs max vs min).
- `python scripts/run_final.py` — sweeps match radius × early-warning lookback.

---

## Understanding what you see

**The maps:** red = hotter than normal, blue = colder than normal. The final
"breakdown" map highlights the areas the model thinks are at risk.

**The two key numbers** (in the report):
- **Recall** — of all the real disasters, how many did the model catch? (higher = better)
- **Precision** — of all the model's alarms, how many were correct? (higher = better)

---

## If something goes wrong

- **Computer freezes / crashes** → you're on the heavy fine grid. Set `resolution_deg`
  back to `1.5` in the config and close other apps.
- **"file not found" for disasters** → you still need to download the disaster data
  (see **SETUP.md**).
- **First run is slow** → that's the one-time data download; later runs are fast.
