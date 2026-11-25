"""Toy check (mac, 2026-11-25): coverage when the truth sits on a correlated prior boundary.

Not an experiment and not part of E1's verdict. It supports the mac's review
of reply 06 (WORKLOG 2026-11-25 (mac)).

Model: a 2-D Gaussian likelihood in (f, a), unit SDs, correlation rho, and a
flat prior truncated to f >= 0. The truth (f, a) = (0, 0) sits on the
boundary, as f_beta,true in {0, 1} does in E1's grid. For each simulated
dataset it takes the 90 % marginal interval of a and records:
- coverage of a = 0;
- z = posterior median / (half-width / 1.645).

Pure numpy/scipy on CPU, fixed seed, runs in about a minute.

Output on the mac (python 3.12.11, numpy 2.4.2):
 rho   cov   mean_z  SD_z
+0.00  0.899  +0.01   1.01
-0.30  0.890  -0.30   0.99
-0.50  0.872  -0.48   0.96
-0.70  0.835  -0.73   0.90
-0.80  0.787  -0.84   0.85
-0.90  0.721  -1.02   0.71
-0.95  0.635  -1.13   0.61
"""
import numpy as np
from scipy.stats import truncnorm
rng = np.random.default_rng(1)
ND, NS = 4000, 4000
print(" rho   cov   mean_z  SD_z   (f on boundary)")
for rho in (0.0, -0.3, -0.5, -0.7, -0.8, -0.9, -0.95):
    cov=[]; zs=[]
    for _ in range(ND):
        fh = rng.normal(); ah = rho*fh + np.sqrt(1-rho**2)*rng.normal()
        f = truncnorm.rvs(-fh, np.inf, loc=fh, scale=1, size=NS, random_state=rng)
        a = ah + rho*(f-fh) + np.sqrt(1-rho**2)*rng.normal(size=NS)
        lo, med, hi = np.quantile(a, [0.05, 0.5, 0.95])
        cov.append(lo <= 0 <= hi); zs.append(med/((hi-lo)/2/1.645))
    zs=np.array(zs)
    print(f"{rho:+.2f}  {np.mean(cov):.3f}  {zs.mean():+.2f}   {zs.std():.2f}")
