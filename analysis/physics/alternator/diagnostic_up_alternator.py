#!/usr/bin/env python3
"""
Diagnostic runner for UP canonical vs alternator-augmented regressions.

Usage:
  - Edit the DATA_FILE, VAR names below to match your CSV.
  - Run: python diagnostic_up_alternator.py
Outputs:
  - diagnostics_summary.json-like printout
  - regressions_out.csv with key estimates per model
  - permutation_test_alt.csv with permutation p-values
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from copy import deepcopy
from tqdm import trange
import json

np.random.seed(12345)

# ---------- User config ----------
DATA_FILE = "regions.csv"   # path to your dataset CSV
# Variable mappings — set to actual column names
VAR_E = "E"
VAR_r = "r"
VAR_ORIENT = "orientation_score"
VAR_NODE = "node_count"
OUT_CSV = "diagnostic_regression_results.csv"
PERM_REPS = 2000
ALPHA = 0.05
USE_HC = True
# ----------------------------------

def prepare_df(df):
    df = df.copy()
    df['E_over_r'] = df[VAR_E] / df[VAR_r]
    # ensure control vars present
    if VAR_ORIENT not in df.columns:
        df[VAR_ORIENT] = 0.0
    if VAR_NODE not in df.columns:
        df[VAR_NODE] = 0
    return df

def fit_canonical(df):
    formula = "delta ~ E_over_r + {} + {}".format(VAR_ORIENT, VAR_NODE)
    return smf.ols(formula=formula, data=df).fit(cov_type='HC3' if USE_HC else None)

def fit_additive_alt(df, alt_col):
    df2 = df.copy()
    formula = "delta ~ E_over_r + {} + {} + {}".format(alt_col, VAR_ORIENT, VAR_NODE)
    return smf.ols(formula=formula, data=df2).fit(cov_type='HC3' if USE_HC else None)

def fit_interaction_alt(df, alt_col):
    df2 = df.copy()
    # interaction alt:E_over_r allows regime-dependent slope
    formula = "delta ~ E_over_r + {}:E_over_r + {} + {} + {}".format(alt_col, alt_col, VAR_ORIENT, VAR_NODE)
    return smf.ols(formula=formula, data=df2).fit(cov_type='HC3' if USE_HC else None)

def fit_continuous_alt_interaction(df, alt_cont):
    df2 = df.copy()
    df2['alt_cont'] = alt_cont
    formula = "delta ~ E_over_r + alt_cont:E_over_r + alt_cont + {} + {}".format(VAR_ORIENT, VAR_NODE)
    return smf.ols(formula=formula, data=df2).fit(cov_type='HC3' if USE_HC else None)

def permutation_test_alt(df, alt_col, test_stat='t_int', reps=1000, seed=12345):
    """Permutation test: shuffle alt assignments and recompute statistic.
    test_stat options: 't_int' (t-stat for interaction), 'r2gain' (R2 improvement aug - base)
    """
    rng = np.random.RandomState(seed)
    obs = []
    # baseline (unshuffled) models
    base = fit_canonical(df)
    aug = fit_interaction_alt(df, alt_col)
    # extract observed stat
    if test_stat == 't_int':
        obs_stat = aug.tvalues.get(f'{alt_col}:E_over_r', np.nan)
    elif test_stat == 'r2gain':
        obs_stat = aug.rsquared - base.rsquared
    else:
        raise ValueError("unknown test_stat")
    # permutations
    perm_stats = []
    for _ in range(reps):
        df_perm = df.copy()
        df_perm[alt_col] = rng.permutation(df_perm[alt_col].values)
        aug_p = fit_interaction_alt(df_perm, alt_col)
        base_p = fit_canonical(df_perm)
        if test_stat == 't_int':
            stat = aug_p.tvalues.get(f'{alt_col}:E_over_r', 0.0)
        else:
            stat = aug_p.rsquared - base_p.rsquared
        perm_stats.append(stat)
    perm_stats = np.array(perm_stats)
    # two-sided empirical p-value for difference from zero (or one-sided if desired)
    if test_stat == 't_int':
        p_emp = (np.abs(perm_stats) >= np.abs(obs_stat)).mean()
    else:
        # for R2 improvement, expect positive under true alt; one-sided p-value
        p_emp = (perm_stats >= obs_stat).mean()
    return {'obs_stat': float(obs_stat), 'perm_mean': float(perm_stats.mean()), 'perm_std': float(perm_stats.std()), 'p_emp': float(p_emp)}

def diagnostics(df, alt_spec='thresholded', alt_name='alt', alt_threshold_quantile=0.5, alt_col_out='alt'):
    """
    alt_spec: 'binary_independent' or 'thresholded' (threshold on E_over_r median by default)
    returns dict with fits, tests, and pattern classification
    """
    df = prepare_df(df)
    N = len(df)
    out = {'N': int(N)}
    # create alt column according to spec
    if alt_spec == 'binary_independent':
        df[alt_col_out] = np.random.RandomState(12345).binomial(1, 0.5, size=N)
    elif alt_spec == 'thresholded':
        q = df['E_over_r'].quantile(alt_threshold_quantile)
        df[alt_col_out] = (df['E_over_r'] > q).astype(int)
    else:
        raise ValueError("alt_spec unknown")

    # Fit models
    base = fit_canonical(df)
    aug_add = fit_additive_alt(df, alt_col_out)
    aug_int = fit_interaction_alt(df, alt_col_out)

    # Extract key stats
    res = {}
    res['base_coef_E'] = float(base.params.get('E_over_r', np.nan))
    res['base_p_E'] = float(base.pvalues.get('E_over_r', np.nan))
    res['aug_add_coef_E'] = float(aug_add.params.get('E_over_r', np.nan))
    res['aug_add_p_E'] = float(aug_add.pvalues.get('E_over_r', np.nan))
    res['aug_add_coef_alt'] = float(aug_add.params.get(alt_col_out, np.nan))
    res['aug_add_p_alt'] = float(aug_add.pvalues.get(alt_col_out, np.nan))
    res['aug_int_coef_E'] = float(aug_int.params.get('E_over_r', np.nan))
    res['aug_int_p_E'] = float(aug_int.pvalues.get('E_over_r', np.nan))
    res['aug_int_coef_int'] = float(aug_int.params.get(f'{alt_col_out}:E_over_r', np.nan))
    res['aug_int_p_int'] = float(aug_int.pvalues.get(f'{alt_col_out}:E_over_r', np.nan))
    res['aug_int_coef_alt'] = float(aug_int.params.get(alt_col_out, np.nan))
    res['r2_base'] = float(base.rsquared)
    res['r2_aug_add'] = float(aug_add.rsquared)
    res['r2_aug_int'] = float(aug_int.rsquared)
    res['r2_gain_add'] = res['r2_aug_add'] - res['r2_base']
    res['r2_gain_int'] = res['r2_aug_int'] - res['r2_base']

    # Permutation tests on interaction (thresholded case particularly important)
    perm_int = permutation_test_alt(df, alt_col_out, test_stat='t_int', reps=PERM_REPS, seed=12345)
    perm_r2 = permutation_test_alt(df, alt_col_out, test_stat='r2gain', reps=PERM_REPS, seed=12345)
    res['perm_t_int_p_emp'] = perm_int['p_emp']
    res['perm_r2gain_p_emp'] = perm_r2['p_emp']

    # Diagnostic pattern rules (1/2/3 from your spec)
    # Pattern 1: beta_Er(canonical) ≈ beta_Er(augmented), beta_alt ≈ 0
    # Pattern 2: beta_Er(canonical) ≈ beta_Er(augmented), beta_alt ≠ 0
    # Pattern 3: beta_Er(canonical) >> beta_Er(augmented), beta_alt ≠ 0
    eps_tol = 1e-6
    # choose comparison tolerance relative to estimated SEs: use absolute difference threshold
    diff = abs(res['base_coef_E'] - res['aug_int_coef_E'])
    # interpret alt as significant if p < ALPHA (aug_add_p_alt or aug_int_p_int)
    alt_sig = (res['aug_add_p_alt'] < ALPHA) or (res['aug_int_p_int'] < ALPHA)
    # approximate rule: "≈" if difference smaller than 2 * se_base_E (use base se); otherwise ">>"
    base_se = base.bse.get('E_over_r', np.nan)
    if np.isnan(base_se):
        base_se = 0.0
    if diff <= 2.0 * base_se:
        if not alt_sig:
            pattern = 1
            interpretation = "Pattern 1: No alternator signal; canonical estimate stable."
        else:
            pattern = 2
            interpretation = "Pattern 2: Alternator exists but independent of E/r; both estimates similar."
    else:
        if alt_sig:
            pattern = 3
            interpretation = "Pattern 3: Evidence alternator correlated with E/r; canonical estimate likely contaminated by OVB. Use augmented estimate."
        else:
            pattern = 0
            interpretation = "Unclear: estimates differ but alternator not significant."
    out.update(res)
    out['pattern'] = int(pattern)
    out['interpretation'] = interpretation
    # Save model summaries compactly
    out['models'] = {
        'base_params': base.params.to_dict(),
        'aug_add_params': aug_add.params.to_dict(),
        'aug_int_params': aug_int.params.to_dict()
    }
    return out, df

def main():
    df = pd.read_csv(DATA_FILE)
    # We assume the outcome is named 'delta' in the file. If different, rename:
    if 'delta' not in df.columns:
        raise RuntimeError("Data must contain 'delta' outcome column.")
    # Run both specs: thresholded alt and binary independent alt
    results = {}
    for alt_spec in ['thresholded', 'binary_independent']:
        res, df_with_alt = diagnostics(df, alt_spec=('binary_independent' if alt_spec=='binary_independent' else 'thresholded'),
                                       alt_col_out=f'alt_{alt_spec}',
                                       alt_threshold_quantile=0.5)
        results[alt_spec] = res
        # create a compact rows for CSV
    # Flatten for CSV
    rows = []
    for spec, d in results.items():
        row = {'alt_spec': spec, 'N': d['N'],
               'base_coef_E': d['base_coef_E'], 'base_p_E': d['base_p_E'],
               'aug_int_coef_int': d['aug_int_coef_int'], 'aug_int_p_int': d['aug_int_p_int'],
               'aug_add_coef_alt': d['aug_add_coef_alt'], 'aug_add_p_alt': d['aug_add_p_alt'],
               'r2_gain_int': d['r2_gain_int'], 'perm_r2gain_p_emp': d['perm_r2gain_p_emp'],
               'pattern': d['pattern'], 'interpretation': d['interpretation']}
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    print("Saved", OUT_CSV)
    print("Diagnostic summary:")
    print(json.dumps(results, indent=2))
    # Also return results dict (if used as module)
    return results

if __name__ == "__main__":
    main()
