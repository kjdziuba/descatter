"""Re-derive the E1 control verdicts under the criteria the mac clarified in
commit 176819f, from the saved runs. No re-sampling.

Clarified criteria (docs/EXPERIMENTS.md, 2026-11-06):
  positive: W < 0.05 in >= 95 % of the 40 draws, in each condition
  negative: KS < 0.1 in >= 90 % of the 40 draws, in each condition,
            with KS computed from >= 2000 equal-weight posterior samples
  sigma_neg: chosen so the noise-free Delta chi^2 (f_beta 0 vs 1) <= 0.1 in
             each condition; take the larger sigma.
"""
import json
import numpy as np

from descatter import infer_e1 as inf
from descatter import physics as ph

from descatter.provenance import REPO_ROOT

P = REPO_ROOT / "results/e1/controls.json"
d = json.loads(P.read_text())
runs = d["runs"]
SIGMA_E0 = d["config"]["sigma_e0_AU"]

TA = ph.Theta(f_beta=0.0, a_um=0.25, n_inf=1.40, phi=0.2)
TB = ph.Theta(f_beta=1.0, a_um=0.25, n_inf=1.40, phi=0.2)
sig_rule = {}
for cond in ("raw", "preprocessed"):
    g = inf.chi2_gap(TA, TB, sigma=SIGMA_E0, condition=cond)
    sig_rule[cond] = {
        "chi2_gap_at_sigma_E0": g,
        "required_multiplier": float(np.sqrt(g / 0.1)),
    }
sigma_neg_mult = max(v["required_multiplier"] for v in sig_rule.values())

out = {
    "source": "re-derived from results/e1/controls.json; no re-sampling",
    "criteria": {
        "positive": "W < 0.05 in >= 95 % of the 40 draws, per condition",
        "negative": "KS < 0.1 in >= 90 % of the 40 draws, per condition, "
                    "KS from >= 2000 equal-weight samples",
    },
    "sigma_neg_rule": {
        "per_condition": sig_rule,
        "sigma_neg_multiplier": sigma_neg_mult,
        "sigma_neg_AU": SIGMA_E0 * sigma_neg_mult,
        "multiplier_actually_run": 100,
        "satisfies_rule": bool(100 >= sigma_neg_mult),
        "chi2_gap_at_x100": {
            c: inf.chi2_gap(TA, TB, sigma=SIGMA_E0 * 100, condition=c)
            for c in ("raw", "preprocessed")
        },
        "note": (
            "the DRAFT says 'sigma x 100 is not enough: a rough estimate leaves "
            "Delta chi^2 ~ 20-190'. Measured, sigma x 100 gives 0.016 (raw) and "
            "0.007 (preprocessed): Delta chi^2 scales as 1/sigma^2, so x100 in "
            "sigma divides the gap by 1e4. The rule's own threshold is met from "
            f"{sigma_neg_mult:.0f}x upwards."
        ),
    },
    "verdicts": {},
}

for control, crit in (("positive", "W"), ("negative", "KS")):
    out["verdicts"][control] = {}
    for cond in ("raw", "preprocessed"):
        sel = [r for r in runs if r["control"] == control and r["condition"] == cond]
        w = np.array([r["wrong_mode_mass_W"] for r in sel], float)
        ks = np.array([r["ks_f_beta_vs_uniform_prior"] for r in sel], float)
        nsamp = np.array([r["n_posterior_samples"] for r in sel], int)
        frac = float((w < 0.05).mean()) if crit == "W" else float((ks < 0.1).mean())
        need = 0.95 if crit == "W" else 0.90
        out["verdicts"][control][cond] = {
            "n_draws": len(sel),
            "W_median": float(np.median(w)),
            "W_max": float(w.max()),
            "frac_W_below_0.05": float((w < 0.05).mean()),
            "ks_median": float(np.median(ks)),
            "ks_max": float(ks.max()),
            "frac_ks_below_0.1": float((ks < 0.1).mean()),
            "min_posterior_samples": int(nsamp.min()),
            "meets_2000_sample_requirement": bool(nsamp.min() >= 2000),
            "criterion": f"frac({crit}) >= {need}",
            "PASS": bool(frac >= need),
        }

d["clarified_2026_11_06"] = out
P.write_text(json.dumps(d, indent=2) + "\n")

print(json.dumps(out["sigma_neg_rule"], indent=2))
print()
for control in ("positive", "negative"):
    print(f"{control.upper()} control under the clarified criteria:")
    for cond, v in out["verdicts"][control].items():
        print(
            f"  {cond:14s} n={v['n_draws']:2d}  W med {v['W_median']:.4f} max {v['W_max']:.4f} "
            f"frac<0.05 {v['frac_W_below_0.05']:.2f} | KS med {v['ks_median']:.4f} "
            f"max {v['ks_max']:.4f} frac<0.1 {v['frac_ks_below_0.1']:.2f} | "
            f"min samples {v['min_posterior_samples']} | {'PASS' if v['PASS'] else 'FAIL'}"
        )
