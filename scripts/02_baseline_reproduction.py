import os
import pandas as pd
import numpy as np

print("="*60)
print("  DT3 PROJECT: PHASE 2 - BASELINE PSYCHOMETRIC REPRODUCTION ")
print("="*60)

# Load validated master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

m_cols = ['DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m']
p_cols = ['DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p']
n_cols = ['DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n']
all_cols = m_cols + p_cols + n_cols

def cronbach_alpha(item_df):
    item_df = item_df.dropna()
    k = item_df.shape[1]
    if k <= 1 or len(item_df) == 0:
        return np.nan
    item_vars = item_df.var(axis=0, ddof=1).sum()
    total_var = item_df.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return np.nan
    return (k / (k - 1)) * (1 - (item_vars / total_var))

print("\n--- 1. CRONBACH'S ALPHA (INTERNAL CONSISTENCY) ---")
results = []
for sample_name, group in df.groupby('sample_origin'):
    alpha_m = cronbach_alpha(group[m_cols])
    alpha_p = cronbach_alpha(group[p_cols])
    alpha_n = cronbach_alpha(group[n_cols])
    alpha_total = cronbach_alpha(group[all_cols])
    
    results.append({
        'Sample': sample_name,
        'N': len(group),
        'Alpha_Machiavellianism': round(alpha_m, 3),
        'Alpha_Psychopathy': round(alpha_p, 3),
        'Alpha_Narcissism': round(alpha_n, 3),
        'Alpha_Full_Scale': round(alpha_total, 3)
    })

alpha_df = pd.DataFrame(results)
print(alpha_df.to_string(index=False))

print("\n--- 2. INTER-TRAIT CORRELATION MATRIX (PEARSON R) ---")
traits = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']

for sample_name, group in df.groupby('sample_origin'):
    print(f"\nSample: {sample_name}")
    corr_mat = group[traits].corr(method='pearson').round(3)
    print(corr_mat)

# Save baseline metrics
os.makedirs('results', exist_ok=True)
alpha_df.to_csv('results/baseline_reliability.csv', index=False)

print("\n" + "="*60)
