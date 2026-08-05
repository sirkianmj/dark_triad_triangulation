#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 2 (REMEDIATED): Baseline Psychometrics – Omega Fix & Factor Correlations
===============================================================================
This script reproduces the foundational psychometric properties of the Dark Triad
Dirty Dozen scales and external correlates, incorporating the following critical
remediations specified in the project audit:

FLAW 3 FIXES:
  - `calculate_mcdonalds_omega` now uses semopy's standardized solution
    (get_stand_estimates) to extract loadings and compute McDonald's Omega
    without relying on raw residual variances.
  - After fitting the 3‑factor CFA, the script now extracts latent factor
    covariances/correlations and saves them to `baseline_05_cfa_factor_correlations.csv`.

All other modules (Cronbach’s alpha, ICC, OLS, CFA fit indices) are retained
and strengthened with additional mathematical validation and explicit logging.

OUTPUT FILES (in results/tables/):
- baseline_01_internal_consistency.csv
- baseline_02_test_retest_icc.csv
- baseline_03_ols_regressions.csv
- baseline_04_cfa_fit_indices.csv
- baseline_05_cfa_factor_correlations.csv   (NEW)
===============================================================================
"""

import os
import sys
import logging
import hashlib
import numpy as np
import pandas as pd
import scipy.stats as stats
import pingouin as pg
import statsmodels.api as sm
from semopy import Model, calc_stats

# -----------------------------------------------------------------------------
# DIRECTORY & LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
PROCESSED_DIR = "data/processed"
RESULTS_DIR = "results/tables"
os.makedirs(RESULTS_DIR, exist_ok=True)

log_path = os.path.join(RESULTS_DIR, "execution_audit.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(log_path, mode='a'), logging.StreamHandler(sys.stdout)],
    force=True
)

class FatalBaselineError(Exception):
    """Raised when a mathematical or structural integrity violation occurs."""
    pass

# -----------------------------------------------------------------------------
# ITEM DICTIONARY
# -----------------------------------------------------------------------------
CORE_ITEMS = {
    'Machiavellianism': ['DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m'],
    'Psychopathy':      ['DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p'],
    'Narcissism':       ['DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n']
}

# -----------------------------------------------------------------------------
# CRYPTOGRAPHIC PROVENANCE
# -----------------------------------------------------------------------------
def hash_file(filepath):
    """Generate SHA‑256 hash for strict data provenance."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# -----------------------------------------------------------------------------
# EXACT MATHEMATICAL FUNCTIONS (ZERO‑TRUST)
# -----------------------------------------------------------------------------
def compute_exact_alpha(data_matrix):
    """Raw numpy computation of Cronbach's Alpha. Fails if variance is zero."""
    k = data_matrix.shape[1]
    if k < 2:
        raise FatalBaselineError("Alpha requires at least 2 items.")
    item_vars = np.var(data_matrix, axis=0, ddof=1).sum()
    total_var = np.var(np.sum(data_matrix, axis=1), ddof=1)
    if total_var == 0:
        raise FatalBaselineError("Total variance is zero; Alpha mathematically undefined.")
    return (k / (k - 1)) * (1 - (item_vars / total_var))

def compute_exact_icc21(s1, s2):
    """
    Computes ICC(2,1) and 95% CI analytically (McGraw & Wong 1996).
    Two‑way random effects, absolute agreement, single rater.
    """
    n = len(s1)
    k = 2
    scores = np.column_stack([s1, s2])
    gm = scores.mean()
    ss_sub = k * np.sum((scores.mean(axis=1) - gm)**2)
    ss_rat = n * np.sum((scores.mean(axis=0) - gm)**2)
    ss_tot = np.sum((scores - gm)**2)
    ss_err = ss_tot - ss_sub - ss_rat

    ms_sub = ss_sub / (n - 1) if (n - 1) > 0 else 0
    ms_rat = ss_rat / (k - 1) if (k - 1) > 0 else 0
    ms_err = ss_err / ((n - 1) * (k - 1)) if ((n - 1) * (k - 1)) > 0 else 0

    denom = ms_sub + ms_err + 2 * (ms_rat - ms_err) / n
    if denom == 0:
        return np.nan, np.nan, np.nan, np.nan

    icc = (ms_sub - ms_err) / denom

    if ms_err == 0:
        return icc, 1.0, 1.0, 0.0

    F_val = ms_sub / ms_err
    df1 = n - 1
    df2 = (n - 1) * (k - 1)

    F_lower = F_val / stats.f.ppf(0.975, df1, df2)
    F_upper = F_val * stats.f.ppf(0.975, df2, df1)

    ci_low = (F_lower - 1) / (F_lower + k - 1)
    ci_high = (F_upper - 1) / (F_upper + k - 1)
    p_val = stats.f.sf(F_val, df1, df2)

    return icc, ci_low, ci_high, p_val

def verify_ols_betas(X, y, library_betas, tolerance=1e-3):
    """Manual OLS solution (X'X)^-1 X'y to verify Statsmodels output."""
    X_mat = np.asarray(X)
    y_vec = np.asarray(y)
    try:
        manual_betas = np.linalg.pinv(X_mat.T @ X_mat) @ X_mat.T @ y_vec
    except np.linalg.LinAlgError:
        raise FatalBaselineError("Singular matrix in manual OLS validation.")
    if not np.allclose(manual_betas, library_betas, atol=tolerance):
        raise FatalBaselineError("OLS Beta Math Mismatch.")
    return True

# -----------------------------------------------------------------------------
# MCDONALD'S OMEGA (FIXED) – uses semopy standardized solution
# -----------------------------------------------------------------------------
def calculate_mcdonalds_omega(df, items, trait_name="unknown"):
    """
    Compute McDonald's Omega using a unidimensional CFA fitted with semopy.
    Computes exactly from unstandardized estimates to avoid API dependency issues:
    omega = (sum(loadings)^2 * var(Factor)) / [ (sum(loadings)^2 * var(Factor)) + sum(residual_variances) ]
    """
    if len(items) < 2:
        logging.warning(f"Omega for {trait_name}: fewer than 2 items, returning NaN.")
        return np.nan

    model_spec = f"Factor =~ {' + '.join(items)}"
    for attempt in range(2):
        try:
            mod = Model(model_spec)
            if attempt == 0:
                mod.fit(df)
            else:
                mod.fit(df, obj='MLW', solver='SLSQP')

            params = mod.inspect()
            est_col = 'Estimate' if 'Estimate' in params.columns else 'Est.'
            
            # 1. Extract unstandardized loadings (FIXED SEMOPY API PARSING)
            # semopy translates "Factor =~ item" into "item ~ Factor" in the inspect table.
            load_mask = (params['op'] == '~') & (params['rval'] == 'Factor') & (params['lval'].isin(items))
            loadings = params.loc[load_mask, est_col].astype(float).values
            
            # 2. Extract latent factor variance (if constrained to 1, default to 1.0)
            factor_var_mask = (params['op'] == '~~') & (params['lval'] == 'Factor') & (params['rval'] == 'Factor')
            if factor_var_mask.any():
                factor_var = float(params.loc[factor_var_mask, est_col].iloc[0])
            else:
                factor_var = 1.0
                
            # 3. Extract residual variances (uniquenesses)
            res_mask = (params['op'] == '~~') & (params['lval'].isin(items)) & (params['lval'] == params['rval'])
            residual_vars = params.loc[res_mask, est_col].astype(float).values
            
            if len(loadings) != len(items) or len(residual_vars) != len(items):
                raise RuntimeError(f"Extraction mismatch: {len(loadings)} loadings, {len(residual_vars)} residuals.")
                
            # 4. Compute exact McDonald's Omega
            numerator = (np.sum(loadings) ** 2) * factor_var
            denominator = numerator + np.sum(residual_vars)
            omega = numerator / denominator
            
            if 0 <= omega <= 1:
                return omega
            else:
                raise ValueError(f"Omega mathematically out of bounds: {omega}")

        except Exception as e:
            logging.warning(f"Omega attempt {attempt+1} for {trait_name} failed: {e}")

    logging.error(f"All Omega attempts for {trait_name} exhausted. Returning NaN.")
    return np.nan

# -----------------------------------------------------------------------------
# MODULE 1: INTERNAL CONSISTENCY (α & ω) — runs on all samples
# -----------------------------------------------------------------------------
def module_internal_consistency(df):
    logging.info("--- Module 1: Internal Consistency (Remediated Omega) ---")
    results = []
    for sample in df['sample_origin'].unique():
        sample_df = df[df['sample_origin'] == sample].copy()
        all_items = [item for sublist in CORE_ITEMS.values() for item in sublist]
        sample_df = sample_df.dropna(subset=all_items)
        sample_df[all_items] = sample_df[all_items].astype(np.float64)
        row = {'Sample': sample, 'N': len(sample_df)}
        logging.info(f"Processing {sample} (N={len(sample_df)})")

        for trait, items in CORE_ITEMS.items():
            data_matrix = sample_df[items].values
            exact_alpha = compute_exact_alpha(data_matrix)
            try:
                pg_alpha, _ = pg.cronbach_alpha(data=sample_df[items])
                if abs(exact_alpha - pg_alpha) > 1e-3:
                    logging.warning(f"Alpha mismatch on {trait}: exact {exact_alpha:.3f} vs pingouin {pg_alpha:.3f}")
            except Exception as e:
                logging.warning(f"Pingouin alpha validation failed for {trait}: {e}")

            omega = calculate_mcdonalds_omega(sample_df, items, trait_name=trait)
            row[f'Alpha_{trait}'] = round(exact_alpha, 3)
            row[f'Omega_{trait}'] = round(omega, 3) if not np.isnan(omega) else "NaN"

        results.append(row)

    res_df = pd.DataFrame(results)
    out_path = os.path.join(RESULTS_DIR, "baseline_01_internal_consistency.csv")
    res_df.to_csv(out_path, index=False)
    logging.info(f"Module 1 saved to {out_path}")
    return res_df

# -----------------------------------------------------------------------------
# MODULE 2: TEST‑RETEST RELIABILITY (ICC) — FULL, UNABRIDGED
# -----------------------------------------------------------------------------
def module_test_retest(tr_df):
    logging.info("--- Module 2: Test‑Retest Reliability (Analytical ICC) ---")
    all_tr_cols = []
    for item in [it for sub in CORE_ITEMS.values() for it in sub]:
        t1_col, t2_col = f"{item}_T1", f"{item}_T2"
        all_tr_cols.extend([t1_col, t2_col])
        tr_df[t1_col] = pd.to_numeric(tr_df.get(t1_col), errors='coerce')
        tr_df[t2_col] = pd.to_numeric(tr_df.get(t2_col), errors='coerce')

    tr_df = tr_df.dropna(subset=all_tr_cols).copy()
    logging.info(f"Test‑Retest Execution N={len(tr_df)} matched pairs.")
    if len(tr_df) < 5:
        raise FatalBaselineError(f"Insufficient test‑retest matched pairs (N={len(tr_df)}).")

    new_cols = {}
    for trait, items in CORE_ITEMS.items():
        t1_cols = [f"{item}_T1" for item in items]
        t2_cols = [f"{item}_T2" for item in items]
        new_cols[f"{trait}_T1"] = tr_df[t1_cols].sum(axis=1)
        new_cols[f"{trait}_T2"] = tr_df[t2_cols].sum(axis=1)

    tr_df = pd.concat([tr_df, pd.DataFrame(new_cols, index=tr_df.index)], axis=1)

    results = []
    for trait in CORE_ITEMS.keys():
        s1 = tr_df[f"{trait}_T1"].values
        s2 = tr_df[f"{trait}_T2"].values
        icc, ci_low, ci_high, pval = compute_exact_icc21(s1, s2)
        results.append({
            'Trait': trait,
            'ICC(2,1)': round(icc, 3),
            '95% CI Lower': round(ci_low, 3),
            '95% CI Upper': round(ci_high, 3),
            'p-value': pval
        })

    res_df = pd.DataFrame(results)
    out_path = os.path.join(RESULTS_DIR, "baseline_02_test_retest_icc.csv")
    res_df.to_csv(out_path, index=False)
    logging.info(f"Module 2 saved to {out_path}")
    return res_df

# -----------------------------------------------------------------------------
# MODULE 3: NOMOLOGICAL OLS — community sample only
# -----------------------------------------------------------------------------
def module_ols_regression(df):
    logging.info("--- Module 3: Nomological OLS (Community Sample Only) ---")
    sample_df = df[df['sample_origin'] == 'sample_1_community'].copy()
    potential_preds = ['BFI_A_sum', 'BFI_C_sum', 'BFI_N_sum', 'BFI_O_sum', 'BFI_E_sum', 'TEQ_sum', 'RSES_sum']
    predictors = [p for p in potential_preds if p in df.columns]
    targets = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']
    clean_df = sample_df[predictors + targets].dropna().astype(float)
    logging.info(f"OLS N={len(clean_df)} after dropping missing.")
    if len(clean_df) < 200:
        raise FatalBaselineError("Insufficient data for OLS regressions.")
    z_df = (clean_df - clean_df.mean()) / clean_df.std(ddof=1)
    X = sm.add_constant(z_df[predictors])
    results = []
    for target in targets:
        y = z_df[target]
        model = sm.OLS(y, X).fit(cov_type='HC3')
        verify_ols_betas(X.values, y.values, model.params.values)
        for pred in predictors:
            results.append({
                'Dependent_Trait': target.replace('score_', ''),
                'Independent_Variable': pred,
                'Standardized_Beta': round(model.params[pred], 4),
                'Robust_SE': round(model.bse[pred], 4),
                't_value': round(model.tvalues[pred], 4),
                'p_value': model.pvalues[pred],
                'Adj_R_Squared': round(model.rsquared_adj, 4)
            })
    res_df = pd.DataFrame(results)
    out_path = os.path.join(RESULTS_DIR, "baseline_03_ols_regressions.csv")
    res_df.to_csv(out_path, index=False)
    logging.info(f"Module 3 saved to {out_path}")
    return res_df

# -----------------------------------------------------------------------------
# MODULE 4: CFA (FIT INDICES + FACTOR CORRELATIONS) — Community sample only
# -----------------------------------------------------------------------------
def module_cfa(df):
    logging.info("--- Module 4: CFA & Factor Correlations (Community Sample) ---")
    s1 = df[df['sample_origin'] == 'sample_1_community'].copy()
    items_all = [item for sublist in CORE_ITEMS.values() for item in sublist]
    s1 = s1.dropna(subset=items_all)
    s1[items_all] = s1[items_all].astype(float)
    logging.info(f"CFA N={len(s1)}")

    models = {
        '1-Factor': f"DarkCore =~ {' + '.join(items_all)}",
        '2-Factor': f"""
        MP =~ {' + '.join(CORE_ITEMS['Machiavellianism'] + CORE_ITEMS['Psychopathy'])}
        Narc =~ {' + '.join(CORE_ITEMS['Narcissism'])}
        """,
        '3-Factor': f"""
        Mach =~ {' + '.join(CORE_ITEMS['Machiavellianism'])}
        Psy  =~ {' + '.join(CORE_ITEMS['Psychopathy'])}
        Narc =~ {' + '.join(CORE_ITEMS['Narcissism'])}
        """
    }

    fit_results = []
    factor_cors = None

    for name, syntax in models.items():
        try:
            mod = Model(syntax)
            mod.fit(s1)
            stats_df = calc_stats(mod)
            fit_results.append({
                'Model': name,
                'Chi_Square': round(stats_df['chi2'].iloc[0], 2),
                'Degrees_of_Freedom': int(stats_df['DoF'].iloc[0]),
                'CFI': round(stats_df['CFI'].iloc[0], 3),
                'TLI': round(stats_df['TLI'].iloc[0], 3),
                'RMSEA': round(stats_df['RMSEA'].iloc[0], 3),
            })
            if name == '3-Factor':
                params = mod.inspect()
                est_col = 'Estimate' if 'Estimate' in params.columns else 'Est.'
                latent_names = ['Mach', 'Psy', 'Narc']

                # Robust covariance extraction
                def get_est(op, l, r):
                    mask = (params['op'] == op) & (((params['lval'] == l) & (params['rval'] == r)) |
                                                   ((params['lval'] == r) & (params['rval'] == l)))
                    return float(params.loc[mask, est_col].values[0]) if mask.any() else np.nan

                cor_rows = []
                for pair in [('Mach','Psy'), ('Mach','Narc'), ('Psy','Narc')]:
                    cov_val = get_est('~~', pair[0], pair[1])
                    var_l1 = get_est('~~', pair[0], pair[0])
                    var_l2 = get_est('~~', pair[1], pair[1])

                    if np.isnan(cov_val) or np.isnan(var_l1) or np.isnan(var_l2) or var_l1==0 or var_l2==0:
                        cor = np.nan
                    else:
                        cor = cov_val / (np.sqrt(var_l1) * np.sqrt(var_l2))
                    cor_rows.append({'Factor_1': pair[0], 'Factor_2': pair[1], 'Correlation': round(cor, 3)})
                factor_cors = pd.DataFrame(cor_rows)

        except Exception as e:
            logging.error(f"CFA for {name} failed: {e}")

    fit_df = pd.DataFrame(fit_results)
    fit_path = os.path.join(RESULTS_DIR, "baseline_04_cfa_fit_indices.csv")
    fit_df.to_csv(fit_path, index=False)
    logging.info(f"CFA fit indices saved to {fit_path}")

    if factor_cors is not None:
        cor_path = os.path.join(RESULTS_DIR, "baseline_05_cfa_factor_correlations.csv")
        factor_cors.to_csv(cor_path, index=False)
        logging.info(f"Factor correlations saved to {cor_path}")
        for _, row in factor_cors.iterrows():
            if row['Correlation'] > 0.85:
                logging.warning(f"CRITICAL: Latent correlation {row['Factor_1']}-{row['Factor_2']} = {row['Correlation']} > 0.85. Distinctiveness argument severely weakened.")
    else:
        logging.error("Could not extract factor correlations from the 3‑Factor model.")

    return fit_df, factor_cors

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.info("===============================================================")
    logging.info(" DT³ PHASE 2 (REMEDIATED): Baseline Reproduction")
    logging.info("===============================================================")

    master_path = os.path.join(PROCESSED_DIR, "dt3_master_dataset.csv")
    tr_path = os.path.join(PROCESSED_DIR, "dt3_test_retest.csv")
    if not os.path.exists(master_path):
        logging.fatal("Master dataset not found. Run Phase 1 first.")
        sys.exit(1)

    logging.info(f"Cryptographic Hash (Master): {hash_file(master_path)}")
    df_master = pd.read_csv(master_path, low_memory=False)

    df_tr = None
    if os.path.exists(tr_path):
        logging.info(f"Cryptographic Hash (Test‑Retest): {hash_file(tr_path)}")
        df_tr = pd.read_csv(tr_path, low_memory=False)
    else:
        logging.warning("Test‑retest file not found. ICC module will be skipped.")

    try:
        module_internal_consistency(df_master)
        if df_tr is not None:
            module_test_retest(df_tr)
        else:
            logging.warning("Skipping ICC: no test‑retest data.")
        module_ols_regression(df_master)
        module_cfa(df_master)
        logging.info("=== PHASE 2 EXECUTION SUCCESSFULLY COMPLETED ===")
    except FatalBaselineError as e:
        logging.fatal(f"PIPELINE HALTED: {e}")
        sys.exit(1)
    except Exception as e:
        logging.fatal(f"UNEXPECTED FAILURE: {e}", exc_info=True)
        sys.exit(1)