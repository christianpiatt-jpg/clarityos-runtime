#!/usr/bin/env python3
"""
Augmented regression templates for reporting.

Provides functions:
 - fit_canonical_template(df)
 - fit_additive_alternator_template(df, alt_col)
 - fit_slope_switch_template(df, alt_col)
 - fit_continuous_alternator_template(df, alt_cont_col)

Each returns a dict with model objects and a ready-to-print text summary snippet for reporting in methods/results.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

def ensure_E_over_r(df, E_col='E', r_col='r'):
    df = df.copy()
    df['E_over_r'] = df[E_col] / df[r_col]
    return df

def fit_canonical_template(df, outcome='delta', controls=['orientation_score','node_count'], use_HC3=True):
    df = ensure_E_over_r(df)
    controls_part = " + ".join(controls) if controls else ""
    formula = f"{outcome} ~ E_over_r" + ((" + " + controls_part) if controls_part else "")
    model = smf.ols(formula=formula, data=df).fit(cov_type='HC3' if use_HC3 else None)
    coef = model.params.get('E_over_r', np.nan)
    pval = model.pvalues.get('E_over_r', np.nan)
    tpl = f"Canonical model: Δ ~ E/r + controls. β̂_Er = {coef:.4f} (p = {pval:.3f}, HC3)."
    return {'model': model, 'summary_snippet': tpl}

def fit_additive_alternator_template(df, alt_col='alt', outcome='delta', controls=['orientation_score','node_count'], use_HC3=True):
    df = ensure_E_over_r(df)
    controls_part = " + ".join(controls) if controls else ""
    formula = f"{outcome} ~ E_over_r + {alt_col}" + ((" + " + controls_part) if controls_part else "")
    model = smf.ols(formula=formula, data=df).fit(cov_type='HC3' if use_HC3 else None)
    coef_alt = model.params.get(alt_col, np.nan)
    p_alt = model.pvalues.get(alt_col, np.nan)
    tpl = f"Additive alternator model: β̂_alt = {coef_alt:.4f} (p = {p_alt:.3f}, HC3). E/r estimate adjusted: {model.params.get('E_over_r',np.nan):.4f}."
    return {'model': model, 'summary_snippet': tpl}

def fit_slope_switch_template(df, alt_col='alt', outcome='delta', controls=['orientation_score','node_count'], use_HC3=True):
    df = ensure_E_over_r(df)
    # slope-switching: include alt:E_over_r interaction and alt main effect
    controls_part = " + ".join(controls) if controls else ""
    formula = f"{outcome} ~ E_over_r + {alt_col}:E_over_r + {alt_col}" + ((" + " + controls_part) if controls_part else "")
    model = smf.ols(formula=formula, data=df).fit(cov_type='HC3' if use_HC3 else None)
    coef_base = model.params.get('E_over_r', np.nan)
    coef_diff = model.params.get(f'{alt_col}:E_over_r', np.nan)
    p_diff = model.pvalues.get(f'{alt_col}:E_over_r', np.nan)
    tpl = ("Slope-switch model: E/r slope when alt=0 = {b0:.4f}; slope change when alt=1 = {bdiff:.4f} "
           "(interaction p = {p:.3f}, HC3). Effective slope when alt=1 = {b1:.4f}.").format(
                b0=coef_base, bdiff=coef_diff, p=p_diff, b1=(coef_base + coef_diff if (not np.isnan(coef_base) and not np.isnan(coef_diff)) else np.nan)
           )
    return {'model': model, 'summary_snippet': tpl}

def fit_continuous_alternator_template(df, alt_cont_col='alt_cont', outcome='delta', controls=['orientation_score','node_count'], use_HC3=True):
    df = ensure_E_over_r(df)
    controls_part = " + ".join(controls) if controls else ""
    # additive + interaction
    formula = f"{outcome} ~ E_over_r + {alt_cont_col}:E_over_r + {alt_cont_col}" + ((" + " + controls_part) if controls_part else "")
    model = smf.ols(formula=formula, data=df).fit(cov_type='HC3' if use_HC3 else None)
    coef_inter = model.params.get(f'{alt_cont_col}:E_over_r', np.nan)
    p_inter = model.pvalues.get(f'{alt_cont_col}:E_over_r', np.nan)
    tpl = f"Continuous alternator model: interaction coef {coef_inter:.4f} (p = {p_inter:.3f}, HC3). This tests modulation of E/r slope by alt_cont."
    return {'model': model, 'summary_snippet': tpl}

# Quick reporting helper
def report_model_for_paper(fit_dict, label):
    model = fit_dict['model']
    snippet = fit_dict['summary_snippet']
    tab = model.summary().as_text()
    return {'label': label, 'snippet': snippet, 'full_summary': tab}

# Example usage (comment out if importing as module)
if __name__ == "__main__":
    # load a hypothetical CSV
    df = pd.read_csv("regions.csv")
    can = fit_canonical_template(df)
    add = fit_additive_alternator_template(df, alt_col='alt_thresholded')
    sw = fit_slope_switch_template(df, alt_col='alt_thresholded')
    cont = fit_continuous_alternator_template(df, alt_cont_col='alt_cont_sigmoid')
    for label, f in [('canonical', can), ('additive', add), ('slope-switch', sw), ('cont', cont)]:
        out = report_model_for_paper(f, label)
        print("=== MODEL:", label, "===")
        print(out['snippet'])
        print()
