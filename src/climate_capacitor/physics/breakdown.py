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


KM_PER_DEG = 111.32  # km per degree of latitude (and of longitude at the equator)


def gradient_magnitude(charge: xr.DataArray) -> xr.DataArray:
    """Magnitude of the horizontal spatial gradient of charge, in charge-per-KM.

    The grid is equal-degree, so a degree of longitude is ~111 km at the equator
    but shrinks toward the poles. We convert to real kilometers with a cos(lat)
    factor on the east-west component, so the gradient is physically consistent
    everywhere (otherwise high-latitude cells get spurious huge gradients)."""
    lat = charge["lat"].values
    lon = charge["lon"].values
    lat_axis = charge.get_axis_num("lat")
    lon_axis = charge.get_axis_num("lon")

    gy_deg = np.gradient(charge.values, lat, axis=lat_axis)   # per degree latitude
    gx_deg = np.gradient(charge.values, lon, axis=lon_axis)   # per degree longitude

    # Convert degrees -> kilometers. cos(lat) shrinks E-W spacing toward poles.
    coslat = np.clip(np.cos(np.radians(lat)), 0.01, None)
    shape = [1] * charge.ndim
    shape[lat_axis] = len(lat)
    coslat_b = coslat.reshape(shape)                          # broadcast along lat

    gy_km = gy_deg / KM_PER_DEG
    gx_km = gx_deg / (KM_PER_DEG * coslat_b)
    mag = np.sqrt(gx_km**2 + gy_km**2)
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
    E: xr.DataArray, threshold_mode: str = "percentile", threshold_value: float = 97.5,
    lat_limit: float | None = None,
):
    """Boolean mask of cells exceeding the critical threshold, plus the
    numeric threshold used.

    threshold_mode:
        "percentile" -> threshold = that percentile of E values (in-region only).
        "absolute"   -> threshold = threshold_value directly.
    lat_limit: if set, cells with |lat| > lat_limit are excluded entirely (the
        poles have ~no disasters and produce noisy gradients); the threshold is
        also computed only over the kept region.
    """
    region = E
    latmask = None
    if lat_limit is not None:
        latmask = np.abs(E["lat"]) <= float(lat_limit)
        region = E.where(latmask)

    if threshold_mode == "percentile":
        thr = float(np.nanpercentile(region.values, threshold_value))
    elif threshold_mode == "absolute":
        thr = float(threshold_value)
    else:
        raise ValueError(f"Unknown threshold_mode {threshold_mode!r}")

    mask = E > thr
    if latmask is not None:
        mask = mask & latmask        # never flag polar cells
    mask.name = "breakdown_zone"
    mask.attrs["threshold"] = thr
    mask.attrs["threshold_mode"] = threshold_mode
    return mask, thr
