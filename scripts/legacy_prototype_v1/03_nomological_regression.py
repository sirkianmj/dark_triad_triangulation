import os
import pandas as pd
import numpy as np
import statsmodels.api as sm
from utils_features import build_feature_set

print("="*60)
print("  DT3 PROJECT: EXACT PUBLISHED HYPOTHESIS REPRODUCTION (H1-H9) ")
print("="*60)

# Load master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)
df, predictors = build_feature_set(df)

# Published Hypotheses Specifications (Matching DTDD_validation.Rmd lines 3460-3535)
EXACT_HYPOTHESES = [
    ('score_Psychopathy', 'BFI_N_sum', '+', 'H2a', 'sample_3_representative'),
    ('score_Machiavellianism', 'BFI_N_sum', None, 'H2b (n.s.)', 'sample_3_representative'),
    ('score_Narcissism', 'BFI_N_sum', '+', 'H4a', 'sample_3_representative'),
    ('score_Narcissism', 'BFI_C_sum', '-', 'H4b', 'sample_3_representative'),
    ('score_Narcissism', 'BFI_A_sum', '-', 'H7a', 'sample_3_representative'),
    ('score_Machiavellianism', 'BFI_A_sum', '-', 'H7b', 'sample_3_representative'),
    ('score_Psychopathy', 'BFI_A_sum', '-', 'H7c', 'sample_3_representative'),
    ('score_Machiavellianism', 'BFI_C_sum', '-', 'H8a', 'sample_3_representative'),
    ('score_Psychopathy', 'BFI_C_sum', '-', 'H8b', 'sample_3_representative'),
    ('score_Narcissism', 'TEQ_sum', None, 'H9a (n.s.)', 'sample_3_representative'),
    ('score_Machiavellianism', 'TEQ_sum', '-', 'H9b', 'sample_3_representative'),
    ('score_Psychopathy', 'TEQ_sum', '-', 'H9c', 'sample_3_representative'),
    ('score_Narcissism', 'RSES_sum', '+', 'H1', 'sample_2_student')
]

regression_summary = []
all_betas = {}

print("\n[1/2] Fitting Exact Single-Predictor Hypothesis Models (Controlled for Age, Gender, Education)...")

covariates = [c for c in predictors if c.startswith(('age', 'gender', 'edu'))]

for target, single_pred, expected_sign, hyp_id, sample_id in EXACT_HYPOTHESES:
    sub_df = df[df['sample_origin'] == sample_id].copy()
    model_preds = [single_pred] + covariates
    
    reg_df = sub_df[[target] + model_preds].dropna()
    X = reg_df[model_preds].values.astype(float)
    y = reg_df[target].values.astype(float)

    # Filter out zero-variance columns in this sample subset
    std_vec = X.std(axis=0)
    active_idx = np.where(std_vec > 0)[0]
    X = X[:, active_idx]
    model_preds = [model_preds[i] for i in active_idx]

    # Standardize X and Y
    X_std = (X - X.mean(axis=0)) / X.std(axis=0)
    y_std = (y - y.mean()) / y.std()
    X_std_const = sm.add_constant(X_std)

    model = sm.OLS(y_std, X_std_const).fit()
    betas = dict(zip(['const'] + model_preds, model.params))
    pvals = dict(zip(['const'] + model_preds, model.pvalues))
    
    beta_pred = betas[single_pred]
    pval_pred = pvals[single_pred]
    all_betas[hyp_id] = (beta_pred, pval_pred, len(reg_df))
    
    regression_summary.append({
        'Hypothesis': hyp_id,
        'Sample': sample_id,
        'Target': target,
        'Predictor': single_pred,
        'Beta_Std': round(beta_pred, 4),
        'P_value': round(pval_pred, 4),
        'R2': round(model.rsquared, 3),
        'N': len(reg_df)
    })

# --- AUTOMATED VERIFICATION GATE ---
print("\n" + "="*60)
print("  AUTOMATED SIGN VERIFICATION AGAINST PUBLISHED HYPOTHESES  ")
print("="*60)

pass_count, fail_count, na_count = 0, 0, 0

for target, single_pred, expected_sign, hyp_id, sample_id in EXACT_HYPOTHESES:
    beta_val, pval_val, n_val = all_betas[hyp_id]

    if expected_sign is None:
        status = "INFO (n.s. expected)"
        na_count += 1
    elif (expected_sign == '+' and beta_val > 0) or (expected_sign == '-' and beta_val < 0):
        status = "PASS"
        pass_count += 1
    else:
        status = "FAIL <<< SIGN MISMATCH -- INVESTIGATE"
        fail_count += 1

    print(f"  [{hyp_id:20s}] {target:22s} <- {single_pred:12s}: beta={beta_val:+.4f} (p={pval_val:.4f}, N={n_val}) expected={expected_sign} -> {status}")

print(f"\n  TOTAL: {pass_count} PASS | {fail_count} FAIL | {na_count} INFO/SKIP")

if fail_count > 0:
    print("\n  *** INVESTIGATE FAILS BEFORE PROCEEDING ***")
else:
    print("\n  *** ALL DIRECTIONAL CHECKS PASSED (100% REPRODUCTION). Safe to proceed. ***")

os.makedirs('results', exist_ok=True)
summary_df = pd.DataFrame(regression_summary)
summary_df.to_csv('results/baseline_ols_regressions.csv', index=False)
print(f"\nSaved exact hypothesis regression summary to 'results/baseline_ols_regressions.csv'")
print("="*60)
