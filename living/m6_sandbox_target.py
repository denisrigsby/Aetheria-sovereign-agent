"""Disposable target for M6 thin SafeEdit residual.

Not part of critical launch path. Safe for autonomous patch demos.
Marker must remain a unique single-line string for SafeEdit uniqueness.
"""

# UNIQUE_LINE_FOR_SAFEEDIT — do not duplicate this assignment elsewhere in this file
M6_SANDBOX_VERSION = "1"

def sandbox_status() -> dict:
    return {
        "target": "m6_sandbox_target",
        "version": M6_SANDBOX_VERSION,
        "purpose": "measured_autonomous_code_patch",
    }
