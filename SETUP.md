# Setup — Climate Capacitor

How to go from a fresh clone to running the analysis. (See `docs/ROADMAP.md` for the
plan and `docs/PROJECT_LOG.md` for what we tried + the final verdict.)

## 1. Get the code
```bash
git clone https://github.com/Ron-Salama/Climate-Modeling-Research-Project.git
cd Climate-Modeling-Research-Project
```

## 2. Python environment (Python 3.11+, we used 3.13)
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
```
(For Spyder: point its interpreter at this `.venv` and `pip install spyder-kernels`.)

## 3. Disaster data — two manual downloads (free logins)
Climate data (temperature + terrain) downloads automatically from the cloud on first
run — no account. Only the disaster data is manual:

- **EM-DAT (dates)** — https://public.emdat.be → free account → export **Natural** disasters,
  **2009–2021**, World → save the `.xlsx` into `data/raw/`.
- **GDIS (precise coordinates)** — https://sedac.ciesin.columbia.edu/data/set/pend-gdis-1960-2018/data-download
  → free NASA Earthdata login → download the **CSV** (`pend-gdis-1960-2018-disasterlocations.csv`)
  into `data/raw/`.
- Then set the filenames in `config/default.yaml` under `data.disasters`
  (`emdat_path`, `gdis_path`).

## 4. Run
```bash
python scripts/run_all.py         # full report: maps + numbers -> outputs/report/
python scripts/run_final.py       # radius x lookback validation grid
python scripts/run_experiment.py  # epsilon (terrain weighting) sweep
python tests/test_physics.py      # quick sanity tests (no data needed)
```
First run downloads ~0.8 GB of ERA5 (cached afterward; later runs are offline + fast).

## 5. Tuning — everything lives in `config/default.yaml`
- `data.era5.daily_statistic`: `mean | max | min`
- `permittivity.method` + `eps_min`/`eps_max` (terrain weighting)
- `charge.window_days` / `decay_per_day` (accumulation timescale)
- `breakdown.threshold_value` (how many cells get flagged)
- `clustering.algorithm`: `components` (fast) | `dbscan` (original)
- `validation` radius / temporal window

## 6. Finer resolution — needs a big machine (>= 32 GB RAM)
Default is **1.5° (~150 km)**, which is laptop-safe. To run the **0.7° (~78 km)** grid,
in `config/default.yaml` set:
- `domain.resolution_deg: 0.703`
- `data.era5.cloud_uri:` the 512x256 store (the commented `cloud_uri_0p7deg` line)

> ⚠️ 0.7° peaks at ~5–7 GB RAM and caused a **blue-screen on a 16 GB laptop**. Only run it
> on a machine with plenty of RAM. Even finer (0.25°) needs much more.
