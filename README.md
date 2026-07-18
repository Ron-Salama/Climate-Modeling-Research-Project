# Climate Capacitor — Modelling Extreme Weather as Electrical Breakdown

A research project (capstone **26-1-R-14**) testing one hypothesis: **can extreme-weather
disasters be predicted by treating the Earth's surface like an electrical capacitor?**

The Earth is split into a grid of cells. Accumulated temperature anomalies act as electric
**charge** (`Q`); terrain acts as a **dielectric / permittivity** (`ε`); and a disaster is
modelled as a dielectric **breakdown** — a cell where the breakdown field `E = ‖∇Q‖ / ε`
(the spatial gradient of accumulated charge over terrain) exceeds a critical threshold.
Predicted breakdown zones are then validated statistically against a real disaster database
(EM-DAT + GDIS).

> **Start here** — **Reviewers:** the [Phase B Project Book](submission/Project_Book_Phase_B_26-1-R-14.docx)
> is the main read (its **Appendix A is the User Guide**, Appendix B the Maintenance Guide).
> **Running it:** [docs/SETUP.md](docs/SETUP.md) to install → [docs/USER_MANUAL.md](docs/USER_MANUAL.md) to run.

## The finding (short version)

The analogy captures a **real but weak thermal signal**. At the finest grid tested (0.703°),
for temperature-type disasters, it recovers **up to ~20% of real events at a regional
(500 km) scale** — and the signal strengthens as resolution increases. However, **precision
stays around 1–2%** and pinpoint (100 km) recall is near zero, both far below the success
targets (recall > 30%, precision > 10%). The model highlights broad regions of thermal
stress, but not the specific location or timing of individual disasters.

**Verdict: a clear, valid negative result** — it maps both the promise and the hard limits
of applying electrostatic physics to climate, which the project brief counts as a genuine
contribution. Full numbers, decisions, and diagnostics are in **[docs/PROJECT_LOG.md](docs/PROJECT_LOG.md)**.

## Submission deliverables

The graded deliverables live in **[`submission/`](submission/)**:

| Deliverable | File |
|---|---|
| Project Book — Phase B | **[submission/Project_Book_Phase_B_26-1-R-14.docx](submission/Project_Book_Phase_B_26-1-R-14.docx)** |
| Project Book — Phase A | **[submission/Project_Book_Phase_A_26-1-R-14.docx](submission/Project_Book_Phase_A_26-1-R-14.docx)** |
| Poster (A0) | **[submission/Poster_Phase_B_26-1-R-14.pptx](submission/Poster_Phase_B_26-1-R-14.pptx)** |
| Presentation deck | **[submission/Presentation_26-1-R-14.pptx](submission/Presentation_26-1-R-14.pptx)** |
| Video (≤2 min) | **[submission/Video_26-1-R-14.mp4](submission/Video_26-1-R-14.mp4)** |

## Documentation

| I want to… | Read |
|---|---|
| Install it and get the data | **[docs/SETUP.md](docs/SETUP.md)** |
| Run it / change settings | **[docs/USER_MANUAL.md](docs/USER_MANUAL.md)** |
| Present it live (≈5 min) | **[docs/DEMO.md](docs/DEMO.md)** |
| Understand what it does, step by step | **[docs/WALKTHROUGH.md](docs/WALKTHROUGH.md)** |
| Understand how the code is built | **[docs/CODE_GUIDE.md](docs/CODE_GUIDE.md)** |
| See the full design decisions + results (canonical record) | **[docs/PROJECT_LOG.md](docs/PROJECT_LOG.md)** |
| See the plan / phase history | **[docs/ROADMAP.md](docs/ROADMAP.md)** |

## Repository layout

```
submission/   the graded deliverables — Phase A & B books, poster, presentation
docs/         all documentation (setup, user manual, demo, design log, code guide)
src/          the Python package (data · physics · analysis · viz)
scripts/      entry points you run (run_all, run_synthetic, sweeps, …)
tests/        quick correctness checks for the physics
config/       default.yaml — every tunable setting ("knob")
data/         disaster inputs (EM-DAT / GDIS) and the cached climate cube
outputs/      generated maps, the event catalogue, and the dashboard
```

## At a glance

- **Data:** 10 years of global ERA5 2 m temperature (2010–2019), cloud-streamed from
  WeatherBench2 (no bulk download); terrain from the same store; disasters from EM-DAT (dates)
  joined with GDIS (precise coordinates).
- **Pipeline:** `temperature → anomaly → charge → permittivity → breakdown field →
  flag high-stress cells → cluster into events → validate vs disasters`.
- **Everything is config-driven** — every knob lives in `config/default.yaml`, so experiments
  are configuration changes, not code edits.
- **Laptop-friendly:** the default 1.5° grid runs on any laptop (~1 GB cached, ~2 GB RAM).
  Finer grids are heavier (0.703° ≈ 5–7 GB, ≥32 GB RAM recommended).
