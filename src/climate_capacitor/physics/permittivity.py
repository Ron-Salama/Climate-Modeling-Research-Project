"""Topography -> dielectric permittivity (epsilon) parameterizations.

This is the *keystone abstraction* of the project. In the capacitor analogy the
terrain is the dielectric: smooth regions (oceans, plains) store/redistribute
thermal energy stably (HIGH permittivity), while rugged regions (steep
mountains) act as bottlenecks that trap energy (LOW permittivity).

The validity of the whole analogy hinges on *which* terrain->epsilon mapping we
use, and the proposal calls for testing several. So instead of hard-coding one
formula, every parameterization is a small pure function registered by name.
The config picks one with ``permittivity.method``; calibration/validation can
sweep across all of them without touching pipeline code.

Each parameterization takes terrain fields (elevation, slope) plus a params
dict and returns an epsilon array normalized into [eps_min, eps_max].

All functions are pure and operate elementwise on NumPy arrays or xarray
DataArrays, so they are trivially testable on synthetic data before any real
topography is downloaded.
"""

from __future__ import annotations

from typing import Callable, Dict

import numpy as np
import xarray as xr

# Registry of available parameterizations: name -> function.
_REGISTRY: Dict[str, Callable] = {}


def register(name: str) -> Callable:
    """Decorator to register a permittivity parameterization under ``name``."""

    def _wrap(fn: Callable) -> Callable:
        _REGISTRY[name] = fn
        return fn

    return _wrap


def available() -> list[str]:
    """Return the names of all registered parameterizations."""
    return sorted(_REGISTRY)


def _rescale(raw, eps_min: float, eps_max: float):
    """Map an arbitrary 'ruggedness' signal in [0, 1] to [eps_min, eps_max].

    ``raw`` should be 0 for smooth terrain and 1 for maximally rugged terrain.
    Rugged -> low epsilon, so we invert: eps = eps_max - raw * (eps_max-eps_min).
    """
    raw = np.clip(raw, 0.0, 1.0)
    return eps_max - raw * (eps_max - eps_min)


@register("linear")
def linear(elevation, slope=None, *, eps_min, eps_max, params):
    """Epsilon decreases linearly with elevation up to ``elevation_ref_m``."""
    ref = float(params.get("elevation_ref_m", 4000.0))
    raw = np.clip(np.asarray(elevation, dtype="float64"), 0.0, None) / ref
    return _rescale(raw, eps_min, eps_max)


@register("log")
def log(elevation, slope=None, *, eps_min, eps_max, params):
    """Epsilon decreases with log-elevation: sensitive at low elevations,
    saturating at high ones (a small hill matters more than another 1000 m
    on an already-high plateau)."""
    ref = float(params.get("elevation_ref_m", 4000.0))
    elev = np.clip(np.asarray(elevation, dtype="float64"), 0.0, None)
    raw = np.log1p(elev) / np.log1p(ref)
    return _rescale(raw, eps_min, eps_max)


@register("slope")
def slope_based(elevation, slope=None, *, eps_min, eps_max, params):
    """Epsilon driven by terrain gradient (slope), not absolute height.
    Steep slopes -> low epsilon. ``slope`` is expected in meters-per-cell or
    any consistent gradient magnitude; it is normalized by its own 99th pct."""
    if slope is None:
        raise ValueError("slope parameterization requires a `slope` field")
    s = np.asarray(slope, dtype="float64")
    norm = np.nanpercentile(s, 99) or 1.0
    raw = s / norm
    return _rescale(raw, eps_min, eps_max)


@register("combined")
def combined(elevation, slope=None, *, eps_min, eps_max, params):
    """Weighted blend of elevation (log) and slope ruggedness.
    ``slope_weight`` in [0, 1] sets how much slope contributes vs elevation."""
    w = float(params.get("slope_weight", 0.5))
    ref = float(params.get("elevation_ref_m", 4000.0))
    elev = np.clip(np.asarray(elevation, dtype="float64"), 0.0, None)
    elev_raw = np.log1p(elev) / np.log1p(ref)
    if slope is None:
        slope_raw = np.zeros_like(elev_raw)
    else:
        s = np.asarray(slope, dtype="float64")
        norm = np.nanpercentile(s, 99) or 1.0
        slope_raw = s / norm
    raw = (1.0 - w) * elev_raw + w * slope_raw
    return _rescale(raw, eps_min, eps_max)


def compute_permittivity(elevation, slope, cfg: dict):
    """Dispatch to the configured parameterization.

    Parameters
    ----------
    elevation, slope : array-like
        Terrain fields on the analysis grid (slope may be None for some methods).
    cfg : dict
        The ``permittivity`` block of the config (method, eps_min, eps_max, params).

    Returns
    -------
    epsilon array in [eps_min, eps_max], same shape as ``elevation``.
    """
    method = cfg.get("method", "linear")
    if method not in _REGISTRY:
        raise KeyError(
            f"Unknown permittivity method {method!r}. Available: {available()}"
        )
    eps = _REGISTRY[method](
        elevation,
        slope,
        eps_min=float(cfg.get("eps_min", 0.2)),
        eps_max=float(cfg.get("eps_max", 1.0)),
        params=cfg.get("params", {}),
    )
    # Preserve xarray coords/dims so downstream stages stay label-aware.
    if isinstance(elevation, xr.DataArray):
        eps = elevation.copy(data=np.asarray(eps))
        eps.name = "permittivity"
        eps.attrs = {"long_name": "terrain permittivity (epsilon)", "method": method}
    return eps
