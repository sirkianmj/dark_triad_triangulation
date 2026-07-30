import os
import pandas as pd
import numpy as np
import xgboost as xgb
import shap
from sklearn.metrics import r2_score, mean_absolute_error

print("="*60)
print("  DT3 PROJECT: PHASE 7 - CROSS-SAMPLE REPLICATION & SHAP INTERACTIONS ")
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

# 1. Independent Cross-Sample Replication (Sample 1 vs Sample 2 vs Sample 3)
print("\n[1/3] Executing Independent Cross-Sample Replication across S1, S2, S3...")
replication_results = []

samples = {
    'Sample 1 (Community)': 'sample_1_community',
    'Sample 2 (Student)': 'sample_2_student',
    'Sample 3 (Representative)': 'sample_3_representative'
}

for s_label, s_id in samples.items():
    s_df = df[df['sample_origin'] == s_id][predictors + traits].dropna()
    X_s = s_df[predictors].values
    
    for t_idx, trait_name in enumerate(traits):
        y_s = s_df[trait_name].values
        
        model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        model.fit(X_s, y_s)
        preds = model.predict(X_s)
        
        r2 = r2_score(y_s, preds)
        mae = mean_absolute_error(y_s, preds)
        
        # Top SHAP feature driver
        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(X_s[:500])
        top_feat_idx = np.argmax(np.abs(sv).mean(axis=0))
        top_feat = predictors[top_feat_idx]
        
        replication_results.append({
            'Sample': s_label,
            'N': len(s_df),
            'Trait': trait_name,
            'Replicated_R2': round(r2, 3),
            'Replicated_MAE': round(mae, 3),
            'Top_Feature_Driver': top_feat
        })

repl_df = pd.DataFrame(replication_results)

print("\n" + "="*50)
print("  CROSS-SAMPLE REPLICATION SUMMARY TABLE  ")
print("="*50)
print(repl_df.to_string(index=False))

# 2. Extract SHAP Interaction Values (Pairwise Feature Interactions)
print("\n[2/3] Extracting 2nd-Order SHAP Interaction Values across traits...")
data_clean = df[predictors + traits].dropna()
X_full = data_clean[predictors].values[:500]

interaction_results = []

for t_idx, trait_name in enumerate(traits):
    y_full = data_clean[trait_name].values[:500]
    model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42).fit(X_full, y_full)
    
    explainer = shap.TreeExplainer(model)
    shap_interactions = explainer.shap_interaction_values(X_full)
    
    # Calculate mean absolute interaction matrix
    mean_abs_inter = np.abs(shap_interactions).mean(axis=0)
    
    # Off-diagonal max interaction
    np.fill_diagonal(mean_abs_inter, 0.0)
    max_idx = np.unravel_index(np.argmax(mean_abs_inter), mean_abs_inter.shape)
    feat1, feat2 = predictors[max_idx[0]], predictors[max_idx[1]]
    inter_strength = mean_abs_inter[max_idx[0], max_idx[1]]
    
    interaction_results.append({
        'Trait': trait_name,
        'Top_Interaction_Pair': f"{feat1} x {feat2}",
        'Interaction_Strength': round(inter_strength, 4)
    })

inter_df = pd.DataFrame(interaction_results)

print("\n" + "="*50)
print("  SHAP NON-LINEAR FEATURE INTERACTION PAIRS  ")
print("="*50)
print(inter_df.to_string(index=False))

os.makedirs('results', exist_ok=True)
repl_df.to_csv('results/cross_sample_replication_summary.csv', index=False)
inter_df.to_csv('results/shap_interaction_pairs_summary.csv', index=False)

print(f"\n[3/3] Saved replication and interaction summaries to 'results/'")
print("="*60)
