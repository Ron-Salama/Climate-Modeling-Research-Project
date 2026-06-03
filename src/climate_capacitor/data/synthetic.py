"""Synthetic temperature + terrain, so the whole pipeline runs with no downloads.

The point of Phase 1 is to prove the physics end-to-end before touching real
ERA5. We fabricate a small global cube that has the structure the model expects:

  * a seasonal cycle (so the anomaly stage has something to remove),
  * latitude-dependent baseline temperature,
  * spatial + temporal noise,
  * a deliberately *planted* growing hot anomaly ("a heatwave") at a known
    place and time, sitting next to a mountain (low permittivity) -- this is
    the event the breakdown field should light up on.

Returns ``xarray`` DataArrays shaped exactly like the real data
(time, lat, lon), so Phase 2 can drop real data into the same interfaces.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr


def _grid(domain: dict):
    res = float(domain["resolution_deg"])
    lats = np.arange(domain["lat_min"] + res / 2, domain["lat_max"], res)
    lons = np.arange(domain["lon_min"] + res / 2, domain["lon_max"], res)
    return lats, lons


def make_terrain(lats: np.ndarray, lons: np.ndarray, seed: int = 42):
    """A couple of Gaussian 'mountain ranges' -> elevation (m) and slope."""
    rng = np.random.default_rng(seed)
    LON, LAT = np.meshgrid(lons, lats)
    elevation = np.zeros_like(LAT, dtype="float64")
    # (center_lat, center_lon, height_m, width_deg)
    mountains = [(35, 80, 5000, 12), (45, -110, 3500, 14), (-20, -65, 4500, 10)]
    for clat, clon, h, w in mountains:
        elevation += h * np.exp(-(((LAT - clat) ** 2 + (LON - clon) ** 2) / (2 * w**2)))
    elevation += rng.normal(0, 50, elevation.shape).clip(-200, 200)
    elevation = elevation.clip(0, None)
    # Slope = magnitude of spatial gradient of elevation.
    gy = np.gradient(elevation, lats, axis=0)
    gx = np.gradient(elevation, lons, axis=1)
    slope = np.sqrt(gx**2 + gy**2)
    coords = {"lat": lats, "lon": lons}
    elev_da = xr.DataArray(elevation, coords=coords, dims=["lat", "lon"], name="elevation")
    slope_da = xr.DataArray(slope, coords=coords, dims=["lat", "lon"], name="slope")
    return elev_da, slope_da


def make_temperature(domain: dict, start: str, end: str, seed: int = 42):
    """Synthetic daily temperature cube (K) with a planted heatwave event."""
    rng = np.random.default_rng(seed)
    lats, lons = _grid(domain)
    time = pd.date_range(start, end, freq="D")
    nt, nlat, nlon = len(time), len(lats), len(lons)

    LON, LAT = np.meshgrid(lons, lats)
    doy = time.dayofyear.values.astype("float64")

    # Baseline: warmer at equator, seasonal swing stronger at high latitudes.
    base = 288.0 - 0.45 * np.abs(LAT)                       # (lat, lon)
    seasonal_amp = 2.0 + 0.25 * np.abs(LAT)                 # (lat, lon)
    season = np.sin(2 * np.pi * (doy - 80) / 365.25)        # (time,)
    hemis = np.sign(LAT)                                    # flip phase by hemisphere

    temp = (
        base[None, :, :]
        + (seasonal_amp[None, :, :] * season[:, None, None] * hemis[None, :, :])
        + rng.normal(0, 1.2, (nt, nlat, nlon))
    )

    # --- Planted event: a growing hot blob near the (35N, 80E) mountain ---
    event = {"lat": 33.0, "lon": 78.0, "peak_doy_index": nt // 3, "ramp": 25}
    dist2 = (LAT - event["lat"]) ** 2 + (LON - event["lon"]) ** 2
    blob = np.exp(-dist2 / (2 * 6.0**2))                    # (lat, lon)
    t_idx = np.arange(nt)
    # Linear ramp up to the peak over `ramp` days, then quick decay.
    ramp = np.clip(1 - np.abs(t_idx - event["peak_doy_index"]) / event["ramp"], 0, 1)
    temp += 14.0 * ramp[:, None, None] * blob[None, :, :]

    da = xr.DataArray(
        temp,
        coords={"time": time, "lat": lats, "lon": lons},
        dims=["time", "lat", "lon"],
        name="t2m",
    )
    da.attrs["units"] = "K"
    da.attrs["planted_event"] = str(event)
    return da, event


def make_synthetic(domain: dict, start: str, end: str, seed: int = 42):
    """Convenience: temperature cube + terrain + the planted-event metadata."""
    temp, event = make_temperature(domain, start, end, seed=seed)
    elev, slope = make_terrain(temp["lat"].values, temp["lon"].values, seed=seed)
    return temp, elev, slope, event
