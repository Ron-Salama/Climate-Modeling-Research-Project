"""Parse the EM-DAT disaster export into a tidy table for validation.

EM-DAT is the "ground truth" we test predictions against in Phase 4. It's a
spreadsheet you export by hand from https://www.emdat.be (free academic login;
this is the one dataset we can't fetch automatically). Drop the file at
`data/raw/emdat.csv` (or .xlsx) and this turns it into a clean DataFrame:

    columns -> [event_id, type, subtype, country, date_start, date_end, lat, lon]

EM-DAT's column names shift a little between exports, so we match them
flexibly and keep only climate-relevant, geolocated events.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Disaster types relevant to the thermal-capacitor hypothesis.
CLIMATE_TYPES = {
    "extreme temperature", "heat wave", "heatwave", "cold wave",
    "storm", "flood", "drought", "wildfire",
}

# ISO3 -> (lat, lon) country center points, used to ESTIMATE a location for
# events EM-DAT only tagged by country (no precise coordinates).
_CENTROIDS_CSV = Path(__file__).resolve().parents[3] / "data" / "reference" / "country_centroids.csv"


def _load_centroids() -> dict:
    """Return {ISO3: (lat, lon)} from the bundled centroid table (or {})."""
    if not _CENTROIDS_CSV.exists():
        return {}
    c = pd.read_csv(_CENTROIDS_CSV)
    return {str(r.iso3): (float(r.lat), float(r.lon)) for r in c.itertuples()
            if pd.notna(r.iso3) and pd.notna(r.lat) and pd.notna(r.lon)}


def _find_col(cols, *candidates):
    """Return the first column whose lowercased name contains a candidate."""
    low = {c.lower(): c for c in cols}
    for cand in candidates:
        for lc, orig in low.items():
            if cand in lc:
                return orig
    return None


def _assemble_date(df, year_col, month_col, day_col):
    """Build a datetime from EM-DAT's separate year/month/day columns,
    defaulting missing month/day to 1 (start-of-period)."""
    y = pd.to_numeric(df[year_col], errors="coerce")
    m = pd.to_numeric(df[month_col], errors="coerce").fillna(1).clip(1, 12) if month_col else 1
    d = pd.to_numeric(df[day_col], errors="coerce").fillna(1).clip(1, 28) if day_col else 1
    return pd.to_datetime(
        dict(year=y, month=m, day=d), errors="coerce"
    )


def load_disasters(cfg: dict, path: str | Path | None = None) -> pd.DataFrame:
    """Dispatch: GDIS (precise coords + EM-DAT dates) or EM-DAT-only.

    Returns [event_id, type, country, date_start, date_end, lat, lon, geo_precision]
    filtered to climate events in the configured domain."""
    if cfg["data"]["disasters"].get("source") == "gdis":
        return _load_disasters_gdis(cfg)
    return _load_disasters_emdat(cfg, path)


def _emdat_dates_by_key(emdat_path: Path) -> pd.DataFrame:
    """From EM-DAT, return a table of [key, date_start, date_end] where key is the
    DisNo. without its country suffix (matches GDIS 'disasterno', e.g. 2010-0232)."""
    df = pd.read_excel(emdat_path)
    cols = df.columns
    c_id = _find_col(cols, "disno", "dis no")
    c_ys, c_ms, c_ds = _find_col(cols, "start year"), _find_col(cols, "start month"), _find_col(cols, "start day")
    c_ye, c_me, c_de = _find_col(cols, "end year"), _find_col(cols, "end month"), _find_col(cols, "end day")
    key = df[c_id].astype(str).str.extract(r"^(\d{4}-\d{4})")[0]   # YYYY-NNNN prefix
    out = pd.DataFrame({
        "key": key,
        "date_start": _assemble_date(df, c_ys, c_ms, c_ds),
        "date_end": _assemble_date(df, c_ye, c_me, c_de) if c_ye else _assemble_date(df, c_ys, c_ms, c_ds),
    }).dropna(subset=["key"]).drop_duplicates("key")
    return out


def _load_disasters_gdis(cfg: dict) -> pd.DataFrame:
    """GDIS precise locations joined to EM-DAT dates on disaster number."""
    dc = cfg["data"]["disasters"]
    gpath = Path(dc["gdis_path"])
    epath = Path(dc.get("emdat_path", dc.get("path")))
    if not gpath.exists():
        raise FileNotFoundError(f"GDIS file not found at {gpath} (see docs/ROADMAP.md).")

    g = pd.read_csv(gpath, encoding="latin-1")
    g["type"] = g["disastertype"].astype(str).str.strip()
    g = g[g["type"].str.lower().apply(lambda t: any(k in t for k in CLIMATE_TYPES))]
    g["key"] = g["disasterno"].astype(str).str.strip()

    dates = _emdat_dates_by_key(epath)
    m = g.merge(dates, on="key", how="left")

    out = pd.DataFrame({
        "event_id": m["disasterno"].astype(str) + "_" + m["geo_id"].astype(str),
        "type": m["type"],
        "country": m["country"].astype(str),
        "date_start": m["date_start"],
        "date_end": m["date_end"],
        "lat": pd.to_numeric(m["latitude"], errors="coerce"),
        "lon": pd.to_numeric(m["longitude"], errors="coerce"),
        "geo_precision": "exact",     # every GDIS location is precisely geocoded
    })
    n0 = len(out)
    out = out.dropna(subset=["lat", "lon", "date_start"])
    d = cfg["domain"]
    out = out[(out.lat >= d["lat_min"]) & (out.lat <= d["lat_max"])
              & (out.lon >= d["lon_min"]) & (out.lon <= d["lon_max"])].reset_index(drop=True)
    print(f"  GDIS: {n0} climate locations -> {len(out)} in domain with dates (all exact coords)")
    return out


def _load_disasters_emdat(cfg: dict, path: str | Path | None = None) -> pd.DataFrame:
    """Load + clean EM-DAT into [event_id, type, subtype, country, date_start,
    date_end, lat, lon], filtered to geolocated climate events in the domain."""
    path = Path(path or cfg["data"]["disasters"]["path"])
    if not path.exists():
        raise FileNotFoundError(
            f"EM-DAT file not found at {path}. Export it from https://www.emdat.be "
            f"(free academic login) and save it there. See docs/ROADMAP.md."
        )

    df = pd.read_excel(path) if path.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(path)
    cols = df.columns

    c_id = _find_col(cols, "disno", "dis no", "event")
    c_type = _find_col(cols, "disaster type", "type")
    c_sub = _find_col(cols, "disaster subtype", "subtype")
    c_country = _find_col(cols, "country")
    c_iso = _find_col(cols, "iso")
    c_lat = _find_col(cols, "latitude", "lat")
    c_lon = _find_col(cols, "longitude", "lon")
    c_ys = _find_col(cols, "start year")
    c_ms = _find_col(cols, "start month")
    c_ds = _find_col(cols, "start day")
    c_ye = _find_col(cols, "end year")
    c_me = _find_col(cols, "end month")
    c_de = _find_col(cols, "end day")

    out = pd.DataFrame({
        "event_id": df[c_id] if c_id else np.arange(len(df)),
        "type": df[c_type].astype(str).str.strip() if c_type else "",
        "subtype": df[c_sub].astype(str).str.strip() if c_sub else "",
        "country": df[c_country].astype(str).str.strip() if c_country else "",
        "iso": df[c_iso].astype(str).str.strip() if c_iso else "",
        "lat": pd.to_numeric(df[c_lat], errors="coerce") if c_lat else np.nan,
        "lon": pd.to_numeric(df[c_lon], errors="coerce") if c_lon else np.nan,
    })
    out["date_start"] = _assemble_date(df, c_ys, c_ms, c_ds) if c_ys else pd.NaT
    out["date_end"] = _assemble_date(df, c_ye, c_me, c_de) if c_ye else out["date_start"]

    # --- tag precision + fill missing coords from country centroid ---------
    # Events with real coordinates are "exact"; those tagged only by country
    # get their country's center point and are flagged "estimated".
    n0 = len(out)
    out["geo_precision"] = np.where(out["lat"].notna() & out["lon"].notna(), "exact", "estimated")
    centroids = _load_centroids()
    need = out["geo_precision"].eq("estimated")
    out.loc[need, "lat"] = out.loc[need, "iso"].map(lambda k: centroids.get(k, (np.nan, np.nan))[0])
    out.loc[need, "lon"] = out.loc[need, "iso"].map(lambda k: centroids.get(k, (np.nan, np.nan))[1])

    # --- filters: need a date + SOME location; climate-relevant types ------
    out = out.dropna(subset=["lat", "lon", "date_start"])
    mask_type = out["type"].str.lower().apply(lambda t: any(k in t for k in CLIMATE_TYPES))
    out = out[mask_type]

    # --- restrict to the configured spatial domain ---
    d = cfg["domain"]
    out = out[(out.lat >= d["lat_min"]) & (out.lat <= d["lat_max"])
              & (out.lon >= d["lon_min"]) & (out.lon <= d["lon_max"])]
    out = out.reset_index(drop=True)

    n_exact = int((out["geo_precision"] == "exact").sum())
    n_est = int((out["geo_precision"] == "estimated").sum())
    print(f"  EM-DAT: {n0} rows -> {len(out)} climate events in domain "
          f"({n_exact} exact, {n_est} estimated from country centroid)")
    return out
