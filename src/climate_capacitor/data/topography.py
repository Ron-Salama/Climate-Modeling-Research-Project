"""Terrain fields (elevation, slope, roughness, land/sea) for permittivity.

Nice surprise: the WeatherBench2 ERA5 store already contains ERA5's *static*
surface fields, on the SAME grid as the temperature. So we derive terrain
straight from there -- no ETOPO download, and guaranteed grid alignment with
the temperature cube (their lat/lon match exactly).

  elevation (m)  = geopotential_at_surface / g           (g = 9.80665 m/s^2)
  slope          = magnitude of the spatial gradient of elevation
  roughness (m)  = standard_deviation_of_orography        (sub-grid ruggedness)
  land_mask      = land_sea_mask                          (1 = land, 0 = ocean)

Returns an xarray.Dataset with those four variables on (lat, lon).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import xarray as xr

from .era5 import _normalize_coords, regrid_to

G = 9.80665  # standard gravity, m/s^2


def _cache_path(cfg: dict) -> Path:
    e, d = cfg["data"]["era5"], cfg["domain"]
    key = f"{e['cloud_uri']}_{d['resolution_deg']}_{d['lat_min']},{d['lat_max']},{d['lon_min']},{d['lon_max']}"
    tag = hashlib.md5(key.encode()).hexdigest()[:8]
    return Path(e["cache_dir"]) / f"topo_{d['resolution_deg']}deg_{tag}.nc"


def load_topography(cfg: dict) -> xr.Dataset:
    """Load elevation/slope/roughness/land-mask aligned to the config grid.

    Cached locally after the first build, so later runs need no network."""
    e = cfg["data"]["era5"]
    d = cfg["domain"]

    cache = _cache_path(cfg)
    if cache.exists():
        print(f"  [terrain cache hit] {cache}")
        return xr.open_dataset(cache)

    print(f"  opening cloud store for terrain (static fields): {e['cloud_uri']}")
    ds = xr.open_zarr(e["cloud_uri"], storage_options={"token": "anon"}, chunks={})
    ds = _normalize_coords(ds)
    ds = ds.sel(lat=slice(d["lat_min"], d["lat_max"]), lon=slice(d["lon_min"], d["lon_max"]))

    # --- elevation from surface geopotential ---
    elevation = (ds["geopotential_at_surface"] / G).load()
    elevation.name = "elevation"
    elevation.attrs["units"] = "m"

    # --- roughness + land mask (static fields, tiny) ---
    roughness = ds["standard_deviation_of_orography"].load()
    roughness.name = "roughness"
    land_mask = ds["land_sea_mask"].load()
    land_mask.name = "land_mask"

    # --- slope = gradient magnitude of elevation across the grid ---
    lat, lon = elevation["lat"].values, elevation["lon"].values
    gy = np.gradient(elevation.values, lat, axis=elevation.get_axis_num("lat"))
    gx = np.gradient(elevation.values, lon, axis=elevation.get_axis_num("lon"))
    slope = elevation.copy(data=np.sqrt(gx**2 + gy**2))
    slope.name = "slope"
    slope.attrs["units"] = "m per degree"

    out = xr.Dataset(
        {"elevation": elevation, "slope": slope, "roughness": roughness, "land_mask": land_mask}
    )
    # Regrid only if the source grid differs from the target (no-op for WB2 1.5deg).
    target_n_lat = len(np.arange(d["lat_min"] + d["resolution_deg"] / 2, d["lat_max"], d["resolution_deg"]))
    if len(out["lat"]) != target_n_lat:
        out = xr.Dataset({v: regrid_to(out[v], d["resolution_deg"], d) for v in out.data_vars})
    out.attrs["source"] = e["cloud_uri"]
    out = out.transpose("lat", "lon")  # standardize dim order to match ERA5
    cache.parent.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(cache)               # cache so later runs skip the cloud
    print(f"  [terrain cached] {cache}")
    return out
