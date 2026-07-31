import os
import pandas as pd
import numpy as np
import xgboost as xgb
from scipy.spatial.distance import cityblock

print("="*60)
print("  DT3 PROJECT: PHASE 5 - LAYER 3: COUNTERFACTUAL EXPLANATIONS  ")
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

# Train XGBoost Models for Each Trait
models = {}
thresholds = {}

for idx, trait in enumerate(traits):
    y = Y[:, idx]
    thresholds[trait] = np.median(y)
    
    model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
    model.fit(X, y)
    models[trait] = model

# Counterfactual Perturbation Generator Function
def compute_counterfactual_perturbation(trait_name, target_idx):
    model = models[trait_name]
    target_low = thresholds[trait_name]
    
    # Identify high scorers (top 15%)
    y_vals = Y[:, target_idx]
    high_idx = np.where(y_vals >= np.percentile(y_vals, 85))[0]
    high_sample = X[high_idx[:100]]  # Evaluate 100 high scorers
    
    feature_perturbations = []
    
    for sample in high_sample:
        base_pred = model.predict(sample.reshape(1, -1))[0]
        best_delta = None
        min_l1 = float('inf')
        
        # Grid search minimal single-feature perturbation to flip score < median
        for f_idx, feat in enumerate(predictors):
            # Test range of feature shifts
            for shift in np.linspace(-3.0, 3.0, 61):
                temp_sample = sample.copy()
                temp_sample[f_idx] += shift * np.std(X[:, f_idx])
                
                new_pred = model.predict(temp_sample.reshape(1, -1))[0]
                if new_pred <= target_low:
                    l1_cost = abs(shift)
                    if l1_cost < min_l1:
                        min_l1 = l1_cost
                        best_delta = (feat, shift)
                        
        if best_delta:
            feature_perturbations.append(best_delta[0])
            
    return pd.Series(feature_perturbations).value_counts(normalize=True)

print("\n[2/3] Computing Counterfactual Feature Perturbations for High Scorers...")
cf_results = {}

for idx, trait in enumerate(traits):
    top_shifts = compute_counterfactual_perturbation(trait, idx)
    cf_results[trait] = top_shifts
    print(f"\n--- Primary Counterfactual Feature Shifts for {trait} ---")
    for feat, prop in top_shifts.items():
        print(f"  -> {feat:12s}: {prop*100:.1f}% of high-scorers flipped to Low")

cf_df = pd.DataFrame(cf_results).fillna(0.0)

os.makedirs('results', exist_ok=True)
cf_df.to_csv('results/counterfactual_perturbation_summary.csv')

print(f"\n[3/3] Counterfactual perturbation summary saved to 'results/counterfactual_perturbation_summary.csv'")
print("="*60)
