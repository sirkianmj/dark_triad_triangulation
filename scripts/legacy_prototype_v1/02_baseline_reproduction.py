import os
import pandas as pd
import numpy as np

print("="*60)
print("  DT3 PROJECT: PHASE 2 - RELIABILITY & PSYCHOMETRIC REPRODUCTION ")
print("="*60)

# Load master dataset and test-retest dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)
df_tr = pd.read_csv('data/processed/dt3_test_retest_dataset.csv', low_memory=False)

m_cols = ['DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m']
p_cols = ['DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p']
n_cols = ['DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n']
all_cols = m_cols + p_cols + n_cols

def cronbach_alpha(item_df):
    item_df = item_df.dropna()
    k = item_df.shape[1]
    if k <= 1 or len(item_df) == 0: return np.nan
    item_vars = item_df.var(axis=0, ddof=1).sum()
    total_var = item_df.sum(axis=1).var(ddof=1)
    if total_var == 0: return np.nan
    return (k / (k - 1)) * (1 - (item_vars / total_var))

def mcdonald_omega(item_df):
    item_df = item_df.dropna()
    k = item_df.shape[1]
    if k <= 1 or len(item_df) < 50: return np.nan
    cov_mat = item_df.cov().values
    eigvals, eigvecs = np.linalg.eigh(cov_mat)
    idx = np.argsort(eigvals)[::-1]
    eigval1 = eigvals[idx[0]]
    eigvec1 = eigvecs[:, idx[0]]
    if eigval1 <= 0: return np.nan
    loadings = np.abs(eigvec1 * np.sqrt(eigval1))
    sum_loadings = np.sum(loadings)
    diag_vars = np.diag(cov_mat)
    uniqueness = np.maximum(0, diag_vars - (loadings**2))
    denom = (sum_loadings ** 2) + np.sum(uniqueness)
    if denom == 0: return np.nan
    return min(1.0, (sum_loadings ** 2) / denom)

print("\n--- 1. INTERNAL CONSISTENCY (CRONBACH'S ALPHA & MCDONALD'S OMEGA) ---")
results = []
for sample_name, group in df.groupby('sample_origin'):
    alpha_m = cronbach_alpha(group[m_cols])
    alpha_p = cronbach_alpha(group[p_cols])
    alpha_n = cronbach_alpha(group[n_cols])
    alpha_tot = cronbach_alpha(group[all_cols])
    
    omega_m = mcdonald_omega(group[m_cols])
    omega_p = mcdonald_omega(group[p_cols])
    omega_n = mcdonald_omega(group[n_cols])
    omega_tot = mcdonald_omega(group[all_cols])
    
    results.append({
        'Sample': sample_name,
        'N': len(group),
        'Alpha_Mach': round(alpha_m, 3), 'Omega_Mach': round(omega_m, 3),
        'Alpha_Psy': round(alpha_p, 3), 'Omega_Psy': round(omega_p, 3),
        'Alpha_Narc': round(alpha_n, 3), 'Omega_Narc': round(omega_n, 3),
        'Alpha_Total': round(alpha_tot, 3), 'Omega_Total': round(omega_tot, 3)
    })

rel_df = pd.DataFrame(results)
print(rel_df.to_string(index=False))

# 2. Sample 4 Test-Retest Reliability
print("\n--- 2. SAMPLE 4 TEST-RETEST RELIABILITY (N = 61 PAIRS) ---")
t1_cols = [c for c in df_tr.columns if c.endswith('_T1') and any(m in c for m in ['1m', '2m', '3m', '4m', '1p', '2p', '3p', '4p', '1n', '2n', '3n', '4n'])]
t2_cols = [c for c in df_tr.columns if c.endswith('_T2') and any(m in c for m in ['1m', '2m', '3m', '4m', '1p', '2p', '3p', '4p', '1n', '2n', '3n', '4n'])]

if len(t1_cols) > 0 and len(t2_cols) > 0:
    t1_sum = df_tr[t1_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
    t2_sum = df_tr[t2_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
    r_tr = t1_sum.corr(t2_sum)
    print(f" -> Overall DTDD Scale Test-Retest Pearson r = {r_tr:.3f}")

os.makedirs('results', exist_ok=True)
rel_df.to_csv('results/baseline_reliability.csv', index=False)
print("\nSaved full reliability metrics to 'results/baseline_reliability.csv'")
print("="*60)
