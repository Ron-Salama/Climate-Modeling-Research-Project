"""Breakdown field = spatial stress of the charge, modulated by terrain.

In a capacitor, the electric field is the gradient of potential divided by the
dielectric's permittivity. By analogy, our "breakdown field" is the spatial
gradient (steepness) of accumulated thermal charge divided by the terrain
permittivity epsilon:

    E(x, y, t) = || grad Q(x, y, t) || / epsilon(x, y)

A large E means charge is piling up steeply over terrain that resists
discharge (low epsilon) -> high atmospheric stress -> candidate "breakdown".
Cells whose E exceeds a critical threshold are flagged as potential
catastrophe zones (clustered into events in the analysis stage).
"""

from __future__ import annotations

import numpy as np
import xarray as xr


def gradient_magnitude(charge: xr.DataArray) -> xr.DataArray:
    """Magnitude of the horizontal spatial gradient of the charge field.

    Gradient is taken per grid step in the lat/lon plane for every time slice;
    units are charge-per-degree (a relative stress measure, which is all the
    thresholding needs)."""
    lat = charge["lat"].values
    lon = charge["lon"].values
    # np.gradient handles non-uniform spacing if coords are passed.
    dlat_axis = charge.get_axis_num("lat")
    dlon_axis = charge.get_axis_num("lon")
    gy = np.gradient(charge.values, lat, axis=dlat_axis)
    gx = np.gradient(charge.values, lon, axis=dlon_axis)
    mag = np.sqrt(gx**2 + gy**2)
    out = charge.copy(data=mag)
    out.name = "charge_gradient"
    return out


def breakdown_field(charge: xr.DataArray, epsilon: xr.DataArray) -> xr.DataArray:
    """E = ||grad Q|| / epsilon, broadcasting epsilon(lat,lon) over time."""
    grad = gradient_magnitude(charge)
    eps = epsilon.clip(min=1e-6)  # guard against divide-by-zero
    E = grad / eps
    E.name = "breakdown_field"
    E.attrs["long_name"] = "breakdown field (atmospheric stress)"
    return E


def flag_zones(
    E: xr.DataArray, threshold_mode: str = "percentile", threshold_value: float = 97.5
):
    """Boolean mask of cells exceeding the critical threshold, plus the
    numeric threshold used.

    threshold_mode:
        "percentile" -> threshold = that percentile of all finite E values.
        "absolute"   -> threshold = threshold_value directly.
    """
    if threshold_mode == "percentile":
        thr = float(np.nanpercentile(E.values, threshold_value))
    elif threshold_mode == "absolute":
        thr = float(threshold_value)
    else:
        raise ValueError(f"Unknown threshold_mode {threshold_mode!r}")
    mask = E > thr
    mask.name = "breakdown_zone"
    mask.attrs["threshold"] = thr
    mask.attrs["threshold_mode"] = threshold_mode
    return mask, thr
