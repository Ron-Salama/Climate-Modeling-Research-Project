"""Fast unit tests for the pure physics functions (no data downloads)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import xarray as xr

from climate_capacitor.physics import anomaly, breakdown, charge, permittivity


def _toy_cube(nt=120, nlat=6, nlon=8):
    time = pd.date_range("2020-01-01", periods=nt, freq="D")
    lat = np.linspace(-50, 50, nlat)
    lon = np.linspace(-100, 100, nlon)
    rng = np.random.default_rng(0)
    data = 280 + rng.normal(0, 1, (nt, nlat, nlon))
    return xr.DataArray(data, coords={"time": time, "lat": lat, "lon": lon},
                        dims=["time", "lat", "lon"], name="t2m")


def test_permittivity_in_range_and_inverts_elevation():
    lat = np.linspace(-50, 50, 6); lon = np.linspace(-100, 100, 8)
    elev = xr.DataArray(np.linspace(0, 5000, 48).reshape(6, 8),
                        coords={"lat": lat, "lon": lon}, dims=["lat", "lon"])
    cfg = {"method": "linear", "eps_min": 0.2, "eps_max": 1.0,
           "params": {"elevation_ref_m": 4000.0}}
    eps = permittivity.compute_permittivity(elev, None, cfg)
    assert float(eps.min()) >= 0.2 - 1e-9
    assert float(eps.max()) <= 1.0 + 1e-9
    # Higher elevation -> lower permittivity.
    assert float(eps.values.flat[0]) > float(eps.values.flat[-1])


def test_all_permittivity_methods_registered():
    assert set(permittivity.available()) >= {"linear", "log", "slope", "combined"}


def test_charge_decay_shortens_memory():
    cube = _toy_cube()
    anom = anomaly.compute_anomaly(cube, smooth_days=5)
    q_no_decay = charge.accumulate_charge(anom, window_days=30, decay_per_day=0.0)
    q_decay = charge.accumulate_charge(anom, window_days=30, decay_per_day=0.1)
    # Decay reduces the magnitude of accumulated charge on average.
    assert float(np.abs(q_decay.values).mean()) < float(np.abs(q_no_decay.values).mean())


def test_breakdown_positive_and_threshold_flags_minority():
    cube = _toy_cube()
    anom = anomaly.compute_anomaly(cube, smooth_days=5)
    q = charge.accumulate_charge(anom, 30, 0.02)
    lat, lon = cube["lat"].values, cube["lon"].values
    eps = xr.DataArray(np.full((len(lat), len(lon)), 0.5),
                       coords={"lat": lat, "lon": lon}, dims=["lat", "lon"])
    E = breakdown.breakdown_field(q, eps)
    assert float(E.min()) >= 0.0
    mask, thr = breakdown.flag_zones(E, "percentile", 97.5)
    frac = float(mask.mean())
    assert 0 < frac < 0.1  # only a small minority of cells flagged


if __name__ == "__main__":
    test_permittivity_in_range_and_inverts_elevation()
    test_all_permittivity_methods_registered()
    test_charge_decay_shortens_memory()
    test_breakdown_positive_and_threshold_flags_minority()
    print("all physics tests passed [OK]")
