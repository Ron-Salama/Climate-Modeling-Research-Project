"""Climate Capacitor — modeling Earth's thermal dynamics as an electrical capacitor.

Package layout:
    data/      ingest ERA5 (cloud-streamed), ETOPO topography, EM-DAT disasters
    physics/   anomaly -> charge -> permittivity -> breakdown field
    analysis/  clustering, event characterization, statistical validation
    viz/       maps and diagnostic plots

See docs/ROADMAP.md for the phased build plan.
"""

__version__ = "0.0.1"
