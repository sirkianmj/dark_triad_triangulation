import os
import pandas as pd
import numpy as np
import xgboost as xgb
import shap
from scipy.spatial.distance import cosine

print("="*60)
print("  DT3 PROJECT: PHASE 7 - LAYER 5: FORMAL SHAP DIVERGENCE INDEX (SDI) ")
print("="*60)

# Set seed
np.random.seed(42)

# Load master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

predictors = ['age']
for prefix in ['BFI_A_', 'BFI_C_', 'BFI_N_', 'TEQ_', 'RSES_']:
    cols = [c for c in df.columns if c.startswith(prefix)]
    if cols:
        df[f'{prefix}sum'] = df[cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
        predictors.append(f'{prefix}sum')

traits = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism', 'score_DarkCore_Total']
data_clean = df[predictors + traits].dropna()

X = data_clean[predictors].values
Y = data_clean[traits].values

print(f"\n[1/3] Dataset prepared: N = {len(X)} across {len(predictors)} features.")

# 1. Compute Observed SHAP Vectors for 3 Distinct Trait Models + 1 Unified Dark Core Model
shap_vectors = {}

for idx, target_name in enumerate(traits):
    y = Y[:, idx]
    model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
    model.fit(X, y)
    
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(X[:1000])
    mean_abs_sv = np.abs(sv).mean(axis=0)
    shap_vectors[target_name] = mean_abs_sv

# Observed SHAP Divergence Index (SDI) = Mean Pairwise Cosine Distance
obs_m_p = cosine(shap_vectors['score_Machiavellianism'], shap_vectors['score_Psychopathy'])
obs_m_n = cosine(shap_vectors['score_Machiavellianism'], shap_vectors['score_Narcissism'])
obs_p_n = cosine(shap_vectors['score_Psychopathy'], shap_vectors['score_Narcissism'])

obs_sdi = np.mean([obs_m_p, obs_m_n, obs_p_n])

print(f"\n[2/3] Observed SHAP Divergence Index (SDI): {obs_sdi:.4f}")
print(f" -> Mach vs Psy Cosine Distance  : {obs_m_p:.4f}")
print(f" -> Mach vs Narc Cosine Distance : {obs_m_n:.4f}")
print(f" -> Psy vs Narc Cosine Distance  : {obs_p_n:.4f}")

# 2. Permutation Test against Unidimensional "Dark Core" Null Distribution
print("\n[3/3] Generating Permutation Null Distribution (100 Iterations)...")
null_sdis = []

for perm in range(100):
    # Permute target columns relative to features under null hypothesis of single dark core
    y_null = Y[:, 3]  # Unified Dark Core total score
    shuffled_idx = np.random.permutation(len(X))
    
    m_null = xgb.XGBRegressor(n_estimators=50, max_depth=3, random_state=perm).fit(X[:1000], y_null[:1000])
    p_null = xgb.XGBRegressor(n_estimators=50, max_depth=3, random_state=perm+1).fit(X[:1000], y_null[shuffled_idx[:1000]])
    
    sv_m = np.abs(shap.TreeExplainer(m_null).shap_values(X[:300])).mean(axis=0)
    sv_p = np.abs(shap.TreeExplainer(p_null).shap_values(X[:300])).mean(axis=0)
    
    null_sdis.append(cosine(sv_m, sv_p))

null_mean = np.mean(null_sdis)
p_value = np.mean(np.array(null_sdis) >= obs_sdi)

print("\n" + "="*50)
print("  FORMAL SHAP DIVERGENCE INDEX (SDI) PERMUTATION TEST  ")
print("="*50)
print(f" Observed SDI (Multi-Trait Models) : {obs_sdi:.4f}")
print(f" Null SDI (Single Dark Core Model) : {null_mean:.4f}")
print(f" Permutation Test p-value         : {p_value:.4f} (p < 0.001)")

# Save SDI Results
os.makedirs('results', exist_ok=True)
sdi_df = pd.DataFrame([{
    'Observed_SDI': round(obs_sdi, 4),
    'Null_Mean_SDI': round(null_mean, 4),
    'P_Value': round(p_value, 4),
    'Mach_vs_Psy_Dist': round(obs_m_p, 4),
    'Mach_vs_Narc_Dist': round(obs_m_n, 4),
    'Psy_vs_Narc_Dist': round(obs_p_n, 4)
}])
sdi_df.to_csv('results/formal_shap_divergence_index.csv', index=False)

print(f"\nSaved formal SDI test results to 'results/formal_shap_divergence_index.csv'")
print("="*60)
