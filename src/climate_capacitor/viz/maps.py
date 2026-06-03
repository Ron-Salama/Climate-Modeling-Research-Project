"""Render a 2-D (lat, lon) field as a global gridded map (like the reference
energy-map image): colored cells over a lat/lon grid, optional flagged-zone
overlay. Uses plain matplotlib so it works everywhere; coastlines are an
optional nicety via cartopy (Phase 5) if installed.
"""

from __future__ import annotations

from pathlib import Path

# NOTE: we do NOT force a backend here. The caller (e.g. run_synthetic.py)
# decides: headless terminal -> save PNGs; Spyder -> inline plots.
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


def plot_field(
    field: xr.DataArray,
    title: str,
    out_path: str | Path,
    *,
    cmap: str = "RdBu_r",
    diverging: bool = True,
    zones: xr.DataArray | None = None,
    show: bool = False,
):
    """Save a PNG map of ``field`` (dims lat, lon).

    diverging=True centers the colormap on 0 (good for anomaly/charge: red=hot,
    blue=cold). Set False for strictly-positive fields (breakdown, permittivity).
    ``zones`` (boolean lat/lon mask) is overlaid as hatched cells if given.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lon = field["lon"].values
    lat = field["lat"].values
    vals = field.values

    fig, ax = plt.subplots(figsize=(11, 6))
    if diverging:
        vmax = float(np.nanpercentile(np.abs(vals), 99)) or 1.0
        vmin = -vmax
    else:
        vmin = float(np.nanpercentile(vals, 1))
        vmax = float(np.nanpercentile(vals, 99))

    mesh = ax.pcolormesh(lon, lat, vals, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
    fig.colorbar(mesh, ax=ax, shrink=0.8, label=field.attrs.get("long_name", field.name))

    if zones is not None:
        z = zones.values.astype(float)
        ax.contourf(
            lon, lat, z, levels=[0.5, 1.5], colors="none",
            hatches=["////"], alpha=0,
        )
        ax.contour(lon, lat, z, levels=[0.5], colors="k", linewidths=0.6)

    ax.set_title(title)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.grid(True, color="0.6", linewidth=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=110)  # always save a PNG too
    if show:
        plt.show()      # render inline (Spyder) / pop up a window
    plt.close(fig)
    return out_path
