"""Toy check (mac, 2026-11-25): coverage when the truth sits on a correlated prior boundary.

Not an experiment and not part of E1's verdict. It supports the mac's review
of reply 06 (WORKLOG 2026-11-25 (mac)).

Model: a 2-D Gaussian likelihood in (f, a), unit SDs, likelihood correlation
rho, and a flat prior truncated to f >= 0. The truth (f, a) = (0, 0) sits on
the boundary, as f_beta,true in {0, 1} does in E1's grid. For each simulated
dataset it takes the 90 % marginal interval of a and records:
- coverage of a = 0;
- z = posterior median / (half-width / 1.645);
- the correlation of the truncated posterior samples.

Part 2 matters when comparing with the grid. Watford's corr(f_beta, a) is
measured from posterior samples, and truncation weakens that correlation, so
compare the grid with the toy's posterior correlation, not with its rho.

Pure numpy/scipy on CPU, fixed seeds, runs in about two minutes.

Output on the mac (python 3.12.11, numpy 2.4.2):

Part 1 (seed 1, 4000 datasets)
 rho   cov   mean_z  SD_z
+0.00  0.899  +0.01   1.01
-0.30  0.890  -0.30   0.99
-0.50  0.872  -0.48   0.96
-0.70  0.835  -0.73   0.90
-0.80  0.787  -0.84   0.85
-0.90  0.721  -1.02   0.71
-0.95  0.635  -1.13   0.61

Part 2 (seed 2, 3000 datasets)
 rho_lik  median_post_corr  coverage
-0.40     -0.253           0.886
-0.50     -0.330           0.872
-0.70     -0.510           0.827
-0.80     -0.631           0.787
-0.85     -0.699           0.761
-0.90     -0.780           0.706
-0.95     -0.876           0.624

The E1 grid at the H1 radii, over all 120 draws
(results/e1/grid/posterior_correlation.json, 9d06af6), measures:
- raw: posterior corr -0.319, coverage 0.900. Part 2 predicts 0.874.
- preprocessed: posterior corr -0.726, coverage 0.708. Part 2 predicts 0.743.

Each difference is about 0.9 binomial SD on 120 draws. 707bf06 quoted
-0.332 and -0.773, which came from a 5-draw-per-cell subset.
"""
import numpy as np
from scipy.stats import truncnorm


def draw_posterior(rng, rho, ns):
    """One dataset: data (fh, ah), then ns samples of the truncated posterior."""
    fh = rng.normal()
    ah = rho * fh + np.sqrt(1 - rho**2) * rng.normal()
    f = truncnorm.rvs(-fh, np.inf, loc=fh, scale=1, size=ns, random_state=rng)
    a = ah + rho * (f - fh) + np.sqrt(1 - rho**2) * rng.normal(size=ns)
    return f, a


def part1(nd=4000, ns=4000):
    rng = np.random.default_rng(1)
    print(" rho   cov   mean_z  SD_z   (f on boundary)")
    for rho in (0.0, -0.3, -0.5, -0.7, -0.8, -0.9, -0.95):
        cov, zs = [], []
        for _ in range(nd):
            _, a = draw_posterior(rng, rho, ns)
            lo, med, hi = np.quantile(a, [0.05, 0.5, 0.95])
            cov.append(lo <= 0 <= hi)
            zs.append(med / ((hi - lo) / 2 / 1.645))
        zs = np.array(zs)
        print(f"{rho:+.2f}  {np.mean(cov):.3f}  {zs.mean():+.2f}   {zs.std():.2f}")


def part2(nd=3000, ns=4000):
    rng = np.random.default_rng(2)
    print(" rho_lik  median_post_corr  coverage")
    for rho in (-0.4, -0.5, -0.7, -0.8, -0.85, -0.9, -0.95):
        pc, cov = [], []
        for _ in range(nd):
            f, a = draw_posterior(rng, rho, ns)
            pc.append(np.corrcoef(f, a)[0, 1])
            lo, hi = np.quantile(a, [0.05, 0.95])
            cov.append(lo <= 0 <= hi)
        print(f"{rho:+.2f}     {np.median(pc):+.3f}           {np.mean(cov):.3f}")


if __name__ == "__main__":
    part1()
    part2()
