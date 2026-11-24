"""Shared definitions for the E1 grid and its cross-check (request 03).

The cross-check must use the same seed the grid will use for the same cell, so
both import the seed scheme from here rather than each defining its own.
"""

from __future__ import annotations

#: step 4, exactly as pre-registered
GRID_RADII = [0.25, 1.0, 2.0, 3.0, 3.5, 4.0, 5.0, 6.0]
GRID_F_BETAS = [0.0, 1.0]
N_DRAWS = 20
CONDITIONS = ("raw", "preprocessed")
GRID_N_RUNS = len(GRID_RADII) * len(GRID_F_BETAS) * N_DRAWS * len(CONDITIONS)

#: the H1 radii: the 120 draws per condition that the verdict pools
H1_RADII = [3.0, 3.5, 4.0]

#: fresh, never used by an earlier E1 run. Earlier bases: 1000-4999 (controls
#: 2026-11-06), 5000-7999 (controls 2026-11-09), 61000 (sampler diagnostic),
#: 77000 (grid projection), 90000 (calibration), 120000/130000 (gauge
#: diagnostic), 200000 (gauge controls).
SEED_BASE = 300000

#: sampler setting the controls validated (06d0827)
NLIVE = 400
SAMPLE = "rwalk"
BOUND = "multi"
N_WORKERS = 14


def grid_seed(a_um: float, f_beta: float, draw: int) -> int:
    """Seed for one grid cell's draw. Unique across the whole grid."""
    i = GRID_RADII.index(a_um)
    j = GRID_F_BETAS.index(f_beta)
    return SEED_BASE + 1000 * i + 100 * j + draw


#: the three cross-check cases from step 3, each the FIRST noise draw of its
#: grid cell, so the seeds match what the grid will use
CROSSCHECK_CASES = [
    {"a_um": 0.25, "f_beta": 0.0},
    {"a_um": 3.5, "f_beta": 1.0},
    {"a_um": 5.0, "f_beta": 0.0},
]
