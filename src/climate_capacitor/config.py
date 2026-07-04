"""Tiny config loader: read the YAML knobs into a plain dict.

Data paths in the config are resolved to ABSOLUTE paths anchored at the project
root, so the code finds data/ and writes cache/outputs correctly no matter what
the current working directory is (e.g. when Spyder runs a script from scripts/).
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]          # project root
DEFAULT_CONFIG = ROOT / "config" / "default.yaml"


def _abs(p: str) -> str:
    """Make a config path absolute relative to the project root (if relative)."""
    path = Path(p)
    return str(path if path.is_absolute() else (ROOT / path))


def load_config(path: str | Path | None = None) -> dict:
    """Load a YAML config file (defaults to config/default.yaml)."""
    path = Path(path) if path else DEFAULT_CONFIG
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Anchor all data paths to the project root (working-directory independent).
    data = cfg.get("data", {})
    era5 = data.get("era5", {})
    if era5.get("cache_dir"):
        era5["cache_dir"] = _abs(era5["cache_dir"])
    topo = data.get("topography", {})
    if topo.get("etopo_path"):
        topo["etopo_path"] = _abs(topo["etopo_path"])
    dis = data.get("disasters", {})
    for k in ("gdis_path", "emdat_path", "path"):
        if dis.get(k):
            dis[k] = _abs(dis[k])
    return cfg
