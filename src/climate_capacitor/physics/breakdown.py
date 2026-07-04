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
    # float32 coords -> np.gradient stays float32 (avoids a float64 memory spike)
    lat = charge["lat"].values.astype(np.float32)
    lon = charge["lon"].values.astype(np.float32)
    lat_axis = charge.get_axis_num("lat")
    lon_axis = charge.get_axis_num("lon")
    vals = np.asarray(charge.values, dtype=np.float32)

    gy = np.gradient(vals, lat, axis=lat_axis)   # per degree latitude  (float32)
    gx = np.gradient(vals, lon, axis=lon_axis)   # per degree longitude (float32)

    # Convert degrees -> km. cos(lat) shrinks E-W spacing toward the poles.
    coslat = np.clip(np.cos(np.radians(lat)), 0.01, None).astype(np.float32)
    shape = [1] * charge.ndim
    shape[lat_axis] = len(lat)
    coslat_b = coslat.reshape(shape)

    # magnitude = sqrt(gx_km^2 + gy_km^2), done in-place to minimise peak memory
    gy /= KM_PER_DEG
    gx /= (KM_PER_DEG * coslat_b)
    gx *= gx
    gy *= gy
    gx += gy
    del gy
    np.sqrt(gx, out=gx)
    out = charge.copy(data=gx)
    out.name = "charge_gradient"
    return out


def breakdown_field(charge: xr.DataArray, epsilon: xr.DataArray, mode: str = "gradient") -> xr.DataArray:
    """E = ||grad Q|| / epsilon, broadcasting epsilon(lat,lon) over time."""
    eps = epsilon.clip(min=1e-6).astype("float32")  # guard div-by-zero + keep float32
    if mode == "charge":
        # accumulated-extreme model: |Q| / eps. Catches uniform hot/cold blobs
        # (e.g. heatwaves) that the gradient misses.
        field = abs(charge)
    elif mode == "combined":
        # blend gradient (contrast) + charge (extreme), each scaled to compare.
        g = gradient_magnitude(charge)
        c = abs(charge)
        gref = float(np.nanpercentile(g.values, 99)) or 1.0
        cref = float(np.nanpercentile(c.values, 99)) or 1.0
        field = (g / gref + c / cref) * 0.5
    else:  # "gradient" (default): the capacitor field, ||grad Q||
        field = gradient_magnitude(charge)
    E = (field / eps).astype("float32")
    E.name = "breakdown_field"
    E.attrs["long_name"] = "breakdown field (atmospheric stress)"
    E.attrs["mode"] = mode
    return E


def flag_zones(
    E: xr.DataArray, threshold_mode: str = "percentile", threshold_value: float = 97.5,
    lat_limit: float | None = None, land_mask: xr.DataArray | None = None,
):
    """Boolean mask of cells exceeding the critical threshold, plus the
    numeric threshold used.

    threshold_mode:
        "percentile" -> threshold = that percentile of E values (in-region only).
        "absolute"   -> threshold = threshold_value directly.
    lat_limit: cells with |lat| > lat_limit are excluded entirely.
    land_mask: if given (a lat/lon boolean), only LAND cells can be flagged, and
        the threshold is computed on land only. Disasters are logged on land, so
        ocean predictions are unmatchable false alarms -> excluding them is fair.
    Both restrictions also shape where the threshold is computed.
    """
    keep = None
    if lat_limit is not None:
        keep = np.abs(E["lat"]) <= float(lat_limit)
    if land_mask is not None:
        keep = land_mask if keep is None else (keep & land_mask)
    region = E.where(keep) if keep is not None else E

    if threshold_mode == "percentile":
        thr = float(np.nanpercentile(region.values, threshold_value))
    elif threshold_mode == "absolute":
        thr = float(threshold_value)
    else:
        raise ValueError(f"Unknown threshold_mode {threshold_mode!r}")

    mask = E > thr
    if keep is not None:
        mask = mask & keep           # never flag excluded (polar/ocean) cells
    mask.name = "breakdown_zone"
    mask.attrs["threshold"] = thr
    mask.attrs["threshold_mode"] = threshold_mode
    return mask, thr
