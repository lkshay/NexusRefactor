"""Bootstrapped confidence intervals. IMPLEMENTED as a reference — study it, don't skip it.

Why bootstrap? With a golden set of only 15-25 scenarios you cannot assume normality, so a
textbook mean ± 1.96·SE interval is unjustified. The bootstrap makes almost no distributional
assumption: it estimates the sampling distribution of your statistic by resampling your data
*with replacement* many times and looking at the spread of the statistic across resamples.

Percentile method (what's implemented here):
  1. You have N observed scores.
  2. Draw N samples WITH REPLACEMENT, compute the statistic (e.g. mean). Repeat B times.
  3. The 2.5th and 97.5th percentiles of those B statistics are your 95% CI.

Caveats to say out loud in an interview:
  - For a binary metric (compile success: 0/1), the bootstrap CI on the proportion is fine but
    a Wilson score interval is usually better at small N — mention you know the difference.
  - The CI quantifies sampling variability of YOUR golden set; it does not fix a biased or
    unrepresentative set. Honest N and honest scenario selection matter more than the interval.
  - scipy.stats.bootstrap (BCa method) is the production-grade version; this percentile
    implementation is here so the mechanism is transparent.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np


def bootstrap_ci(
    data: Sequence[float],
    statistic: Callable[[np.ndarray], float] = np.mean,
    *,
    n_resamples: int = 10_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Return (point_estimate, ci_low, ci_high) via the percentile bootstrap.

    Args:
        data: observed scores (e.g. per-scenario compile success 0/1, or minimality in [0,1]).
        statistic: aggregate to bootstrap; default mean.
        n_resamples: number of bootstrap resamples (B). 10k is plenty for a 95% CI.
        confidence: e.g. 0.95.
        seed: fixed for reproducibility — report numbers that others can regenerate.
    """
    arr = np.asarray(data, dtype=float)
    if arr.size == 0:
        raise ValueError("bootstrap_ci: empty data")

    rng = np.random.default_rng(seed)
    n = arr.size

    # Vectorized resampling: an (n_resamples x n) matrix of random indices into `arr`.
    idx = rng.integers(0, n, size=(n_resamples, n))
    resamples = arr[idx]
    stats = np.apply_along_axis(statistic, axis=1, arr=resamples)

    point = float(statistic(arr))
    alpha = (1.0 - confidence) / 2.0
    lo, hi = np.quantile(stats, [alpha, 1.0 - alpha])
    return point, float(lo), float(hi)
