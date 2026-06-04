"""Small runtime utilities."""

from __future__ import annotations

import os
import sys


def lower_priority() -> None:
    """Drop this process to below-normal priority so a heavy run keeps the
    machine responsive (the cursor won't freeze even while it grinds).

    No-op on failure; safe to call at the top of any script."""
    try:
        if sys.platform.startswith("win"):
            import ctypes
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetPriorityClass(handle, BELOW_NORMAL_PRIORITY_CLASS)
        else:
            os.nice(10)
    except Exception:
        pass
