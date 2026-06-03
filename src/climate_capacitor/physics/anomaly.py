"""Temperature anomalies = deviation from the day-of-year climatology.

The "thermal charge" we accumulate later is built from anomalies, not raw
temperature, so this stage removes the seasonal cycle. We compute a
day-of-year climatology (the average temperature for, e.g., every March 3rd
across all years), smooth it slightly so it isn't noisy, then subtract it.

Works on an ``xarray.DataArray`` with dims (time, lat, lon) — the exact shape
real ERA5 arrives in, so the synthetic Phase-1 data and the real Phase-2 data
flow through identical code.
"""

from __future__ import annotations

import numpy as np
import xarray as xr
from scipy.ndimage import uniform_filter1d


def day_of_year_climatology(temp: xr.DataArray, smooth_days: int = 15) -> xr.DataArray:
    """Mean temperature per calendar day-of-year, circularly smoothed.

    Returns a DataArray indexed by ``dayofyear`` (1..366) with dims
    (dayofyear, lat, lon).
    """
    clim = temp.groupby("time.dayofyear").mean("time")
    if smooth_days and smooth_days > 1:
        # Smooth along the day-of-year axis with wrap-around (Dec 31 -> Jan 1).
        axis = clim.get_axis_num("dayofyear")
        smoothed = uniform_filter1d(
            clim.values, size=int(smooth_days), axis=axis, mode="wrap"
        )
        clim = clim.copy(data=smoothed)
    return clim


def compute_anomaly(temp: xr.DataArray, smooth_days: int = 15) -> xr.DataArray:
    """Subtract the day-of-year climatology from temperature.

    Positive anomaly = warmer than seasonal normal ("positive charge"),
    negative = cooler ("negative charge").
    """
    clim = day_of_year_climatology(temp, smooth_days=smooth_days)
    doy = temp["time"].dt.dayofyear
    anom = temp.groupby("time.dayofyear") - clim
    anom = anom.drop_vars("dayofyear", errors="ignore")
    anom.name = "anomaly"
    anom.attrs["long_name"] = "temperature anomaly vs day-of-year climatology"
    anom.attrs["units"] = temp.attrs.get("units", "K")
    return anom
