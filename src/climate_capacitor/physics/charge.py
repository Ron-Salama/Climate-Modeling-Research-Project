"""Thermal "charge" = decayed sliding-window accumulation of anomalies.

In the capacitor analogy, a cell accumulates thermal charge as warm/cool
anomalies pile up over time, while natural dissipation slowly bleeds it away.
We model this as a causal, exponentially-decayed sum over a sliding window:

    Q(t) = sum_{k=0}^{window-1}  anomaly(t-k) * (1 - decay)^k

so today's anomaly counts fully, yesterday's a bit less, and anything older
than ``window_days`` is dropped. ``decay=0`` => plain running sum over the
window; larger ``decay`` => shorter effective memory.

Implemented as an FIR filter applied along the time axis with
``scipy.signal.lfilter`` — fully vectorized over all grid cells at once
(no Python loop over cells), which is what keeps it fast at global scale.
"""

from __future__ import annotations

import numpy as np
import xarray as xr
from scipy.signal import lfilter


def decay_kernel(window_days: int, decay_per_day: float) -> np.ndarray:
    """Weights (1-decay)^k for k = 0 .. window_days-1."""
    k = np.arange(int(window_days))
    return (1.0 - float(decay_per_day)) ** k


def accumulate_charge(
    anomaly: xr.DataArray, window_days: int = 30, decay_per_day: float = 0.02
) -> xr.DataArray:
    """Accumulate anomalies into thermal charge along the time dimension."""
    kernel = decay_kernel(window_days, decay_per_day)
    axis = anomaly.get_axis_num("time")
    # Causal FIR: y[t] = sum_k kernel[k] * x[t-k]. NaNs are treated as 0 so
    # short gaps don't blow up the accumulation (logged upstream in Phase 2).
    data = np.nan_to_num(anomaly.values, nan=0.0)
    charged = lfilter(kernel, [1.0], data, axis=axis)
    out = anomaly.copy(data=charged)
    out.name = "charge"
    out.attrs["long_name"] = "accumulated thermal charge"
    out.attrs["window_days"] = int(window_days)
    out.attrs["decay_per_day"] = float(decay_per_day)
    return out
