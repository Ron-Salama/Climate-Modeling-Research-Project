"""End-to-end pipeline: real data -> physics -> predicted event catalog.

One function other scripts/tests can reuse, so the full chain lives in one place:
    ERA5 + terrain -> anomaly -> charge -> permittivity -> breakdown -> zones
    -> daily blobs -> linked events -> characterized catalog.
Returns the key intermediate arrays plus the event catalog DataFrame.
"""

from __future__ import annotations

from .data.era5 import load_era5
from .data.topography import load_topography
from .physics import anomaly, breakdown, charge, permittivity
from .analysis import clustering, events


def run_pipeline(cfg: dict, verbose: bool = True, keep_temp: bool = True):
    """Run the whole chain and return a dict of results.

    keep_temp=False frees the temperature cube once anomalies are computed
    (saves ~1 array of RAM) -- use it when the caller won't plot temperature."""
    def say(*a):
        if verbose:
            print(*a)

    start, end = cfg["time"]["start"], cfg["time"]["end"]
    say(f"[1/6] loading ERA5 {start}..{end} ...")
    temp = load_era5(cfg, start, end)
    say(f"[2/6] loading terrain ...")
    topo = load_topography(cfg)

    say("[3/6] anomaly -> charge ...")
    anom = anomaly.compute_anomaly(temp, smooth_days=cfg["charge"]["climatology_smooth_days"])
    if not keep_temp:
        temp = None                      # free ~1 cube of RAM (caller won't plot it)
    Q = charge.accumulate_charge(anom, cfg["charge"]["window_days"], cfg["charge"]["decay_per_day"])

    say("[4/6] permittivity -> breakdown field ...")
    eps = permittivity.compute_permittivity(topo["elevation"], topo["slope"], cfg["permittivity"])
    E = breakdown.breakdown_field(Q, eps)
    mask, thr = breakdown.flag_zones(E, cfg["breakdown"]["threshold_mode"],
                                     cfg["breakdown"]["threshold_value"],
                                     lat_limit=cfg["domain"].get("analysis_lat_max"))

    say("[5/6] clustering flagged cells into events ...")
    blobs = clustering.detect_daily_blobs(mask, E, cfg)
    blobs = clustering.link_events(blobs, cfg)

    say("[6/6] characterizing events ...")
    catalog = events.classify_and_summarize(blobs, Q, eps, cfg)
    say(f"  -> {len(catalog)} predicted events "
        f"({int(blobs['day_index'].nunique()) if len(blobs) else 0} active days)")

    return {
        "temp": temp, "anomaly": anom, "charge": Q, "permittivity": eps,
        "breakdown": E, "mask": mask, "threshold": thr,
        "blobs": blobs, "catalog": catalog,
    }
