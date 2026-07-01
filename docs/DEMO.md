# Demonstration Guide — Climate Capacitor

A simple script for showing the project live (≈ 5 minutes).

## Before the demo
- Make sure it's installed and the data is downloaded (**SETUP.md**).
- **Run it once beforehand** so the climate data is already cached — then nothing
  downloads while you present.
- **Easiest way to present: run from Spyder** (point it at the project's `.venv`).
  When you press **F5**, the graphs appear **automatically in the Plots panel** —
  no need to open any files. (Every figure is *also* saved to `outputs/` as a backup;
  if you run from a plain terminal instead, open those PNGs since nothing pops up.)

---

## Step 1 — Show the calculations are correct  (~10 sec)
Run:
```
python tests/test_physics.py
```
Say: *"These automatic tests confirm the core math behaves correctly."*

## Step 2 — Show the idea working on a test world  (~1 min)
Run `scripts/run_synthetic.py` (F5 in Spyder).
The maps appear in the Plots panel (also saved to `outputs/phase1/`).
Show the **charge** and **breakdown** maps.
Say: *"We plant a fake heatwave in a made-up world. Without being told where it is,
the model lights up exactly that spot — so the pipeline works end to end."*

## Step 3 — Show the real result  (~2 min)
Run `scripts/run_all.py` (F5 in Spyder).
The dashboard appears in the Plots panel (also saved to `outputs/report/dashboard.png`).
Point at:
- the maps (temperature → charge → breakdown),
- the **predicted-vs-actual** map (red = our predictions, blue = real disasters),
- the numbers (Recall, Precision).
Say: *"On real data, the predicted zones and real disasters mostly don't overlap.
We caught only about 1–3% of disasters, far below our 30% target."*

## Step 4 — The conclusion  (~30 sec)
Say: *"So the capacitor analogy does not predict disasters well. That's a clear
negative result — and a valuable one: it shows the limits of applying this kind of
physics to climate. Even our best tuning and precise disaster data didn't change it."*

---

## Likely questions (quick answers)
- **What is Recall?** Of the real disasters, how many we caught. Ours was tiny → we missed almost all.
- **What is Precision?** Of our alarms, how many were right. Also tiny → most alarms were false.
- **Why is a negative result okay?** The project brief says a clear negative — mapping the
  limits of a physical analogy — is as valuable as a positive one.
- **Could it still work?** A few settings remain untested (daily statistic, timescale) and a
  finer map needs a bigger computer — but everything we tried points the same way.
