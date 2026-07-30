import os
import pandas as pd
import numpy as np
import xgboost as xgb
import shap
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt

print("="*60)
print("  DT3 PROJECT: PHASE 7 - LAYER 5: LOCAL SHAP SUBTYPE CLUSTERING ")
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

traits = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']
data_clean = df[predictors + traits].dropna()

X = data_clean[predictors].values
Y = data_clean[traits].values

print(f"\n[1/3] Dataset prepared: N = {len(X)} across {len(predictors)} features.")

# 1. Compute Local SHAP Explanation Matrices for Each Trait
print("\n[2/3] Extracting Local SHAP Explanation Vectors ($N \times 6$) for each trait...")
subtype_results = []

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for trait_idx, trait_name in enumerate(traits):
    y = Y[:, trait_idx]
    model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
    model.fit(X, y)
    
    explainer = shap.TreeExplainer(model)
    local_shap = explainer.shap_values(X[:2000])  # Local SHAP explanation matrix (2000 x 6)
    
    # K-Means Person-Centered Subtype Discovery (K = 2 Subtypes)
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    subtype_labels = kmeans.fit_predict(local_shap)
    
    # Calculate Mean Feature Profiles per Subtype
    s0_mean = local_shap[subtype_labels == 0].mean(axis=0)
    s1_mean = local_shap[subtype_labels == 1].mean(axis=0)
    
    print(f"\n--- Discovered Subtypes for {trait_name} ---")
    print(f" Subtype 1 (N = {np.sum(subtype_labels == 0)}): Key Driver = {predictors[np.argmax(np.abs(s0_mean))]} ({s0_mean[np.argmax(np.abs(s0_mean))]:.3f})")
    print(f" Subtype 2 (N = {np.sum(subtype_labels == 1)}): Key Driver = {predictors[np.argmax(np.abs(s1_mean))]} ({s1_mean[np.argmax(np.abs(s1_mean))]:.3f})")
    
    for p_idx, pred in enumerate(predictors):
        subtype_results.append({
            'Trait': trait_name,
            'Feature': pred,
            'Subtype1_SHAP': round(s0_mean[p_idx], 3),
            'Subtype2_SHAP': round(s1_mean[p_idx], 3)
        })
        
    # Plot Subtype Differences
    ax = axes[trait_idx]
    x_axis = np.arange(len(predictors))
    ax.bar(x_axis - 0.2, s0_mean, 0.4, label='Subtype 1', color='navy')
    ax.bar(x_axis + 0.2, s1_mean, 0.4, label='Subtype 2', color='crimson')
    ax.set_xticks(x_axis)
    ax.set_xticklabels([p.replace('_sum', '') for p in predictors], rotation=45, fontsize=8)
    ax.set_title(trait_name.replace('score_', ''), fontsize=10)
    ax.legend(fontsize=8)

plt.tight_layout()
os.makedirs('results/figures', exist_ok=True)
fig_path = 'results/figures/layer5_subtype_profiles.png'
plt.savefig(fig_path, dpi=300)
plt.close()

subtype_df = pd.DataFrame(subtype_results)

os.makedirs('results', exist_ok=True)
subtype_df.to_csv('results/person_centered_subtypes_summary.csv', index=False)

print(f"\n[3/3] Saved subtype profiles to 'results/person_centered_subtypes_summary.csv' and '{fig_path}'")
print("="*60)
