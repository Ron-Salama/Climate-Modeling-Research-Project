"""Load real ERA5 2m-temperature from a public cloud Zarr store.

Strategy (the whole "no terabytes" trick):
  * open the cloud dataset LAZILY (nothing downloaded yet),
  * subset to our domain + time window,
  * aggregate sub-daily samples to a single daily statistic (default: max),
  * regrid to the target resolution if the source differs,
  * `.load()` -> only now do the (small) requested bytes travel over the wire,
  * cache the result to NetCDF so later runs are instant and offline.

Output is an xarray.DataArray (time, lat, lon) — the SAME shape the synthetic
Phase-1 data uses, so the physics pipeline doesn't care where the data came from.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import dask
import numpy as np
import xarray as xr


def _normalize_coords(ds: xr.Dataset) -> xr.Dataset:
    """Rename lat/lon, convert longitude to [-180, 180], sort ascending."""
    rename = {}
    if "latitude" in ds.coords:
        rename["latitude"] = "lat"
    if "longitude" in ds.coords:
        rename["longitude"] = "lon"
    ds = ds.rename(rename)
    # Convert 0..360 longitudes to -180..180 to match EM-DAT / synthetic data.
    if float(ds["lon"].max()) > 180.0:
        ds = ds.assign_coords(lon=(((ds["lon"] + 180) % 360) - 180))
    return ds.sortby("lon").sortby("lat")


def _cache_path(cfg: dict, start: str, end: str) -> Path:
    """Deterministic cache filename from the request parameters."""
    e = cfg["data"]["era5"]
    d = cfg["domain"]
    key = f"{e['variable']}_{e['daily_statistic']}_{start}_{end}_{d['resolution_deg']}" \
          f"_{d['lat_min']},{d['lat_max']},{d['lon_min']},{d['lon_max']}"
    tag = hashlib.md5(key.encode()).hexdigest()[:8]
    return Path(cfg["data"]["era5"]["cache_dir"]) / f"era5_{e['daily_statistic']}_{start}_{end}_{tag}.nc"


def regrid_to(da: xr.DataArray, resolution_deg: float, domain: dict) -> xr.DataArray:
    """Interpolate onto a regular lat/lon grid at the target resolution.

    Only used when the source grid differs from the target (e.g. ARCO 0.25deg
    -> 1deg). For WeatherBench2 (already 1.5deg) this is effectively a no-op."""
    res = float(resolution_deg)
    new_lat = np.arange(domain["lat_min"] + res / 2, domain["lat_max"], res)
    new_lon = np.arange(domain["lon_min"] + res / 2, domain["lon_max"], res)
    # Skip interpolation if the grid already matches (avoids smoothing the data).
    if (len(da["lat"]) == len(new_lat) and len(da["lon"]) == len(new_lon)
            and np.allclose(da["lat"].values, new_lat, atol=res / 2)):
        return da
    return da.interp(lat=new_lat, lon=new_lon, method="linear")


def load_era5(cfg: dict, start: str, end: str, use_cache: bool = True) -> xr.DataArray:
    """Daily-aggregated ERA5 temperature for the configured domain/time.

    Returns DataArray (time, lat, lon) in Kelvin. Reads from local cache if a
    matching file exists; otherwise streams from the cloud and writes the cache.
    """
    e = cfg["data"]["era5"]
    d = cfg["domain"]
    cache = _cache_path(cfg, start, end)

    if use_cache and cache.exists():
        print(f"  [cache hit] {cache}")
        # float32 halves memory vs the netCDF's float64 (big deal for RAM).
        return xr.open_dataarray(cache).transpose("time", "lat", "lon").astype("float32")

    print(f"  opening cloud store (lazy): {e['cloud_uri']}")
    ds = xr.open_zarr(e["cloud_uri"], storage_options={"token": "anon"}, chunks={})
    ds = _normalize_coords(ds)

    da = ds[e["variable"]]
    if "level" in da.dims:           # surface var shouldn't have levels, but be safe
        da = da.isel(level=0, drop=True)

    # --- subset domain + time (still lazy) ---
    da = da.sel(
        lat=slice(d["lat_min"], d["lat_max"]),
        lon=slice(d["lon_min"], d["lon_max"]),
        time=slice(start, end),
    )

    # --- aggregate sub-daily -> one value per day (this is what we keep) ---
    stat = e["daily_statistic"]
    resampler = da.resample(time="1D")
    daily = getattr(resampler, stat)()      # .max() / .min() / .mean()
    daily.name = "t2m"
    daily.attrs["units"] = "K"
    daily.attrs["daily_statistic"] = stat
    daily.attrs["source"] = e["cloud_uri"]

    daily = regrid_to(daily, d["resolution_deg"], d)

    # The store is chunked in tiny 8-step blocks, so a year is ~180 little reads.
    # Fetch them concurrently with a big thread pool (network I/O, not CPU bound)
    # -> turns minutes of serial round-trips into seconds of parallel ones.
    print("  fetching from cloud in parallel (threaded) ...")
    with dask.config.set(scheduler="threads", num_workers=32):
        daily = daily.compute()      # <-- the only point real data is downloaded
    daily = daily.transpose("time", "lat", "lon").astype("float32")  # std order + half memory

    if use_cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        daily.to_netcdf(cache)
        print(f"  [cached] {cache}  ({cache.stat().st_size/1e6:.1f} MB)")
    return daily
