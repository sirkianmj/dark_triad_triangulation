import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from mapie.regression import CrossConformalRegressor

print("="*60)
print("  DT3 PROJECT: PHASE 7 - RASHOMON SET ROBUSTNESS & CONFORMAL BOUNDS ")
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

X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.2, random_state=42)

print(f"\n[1/3] Prepared dataset shape: {X.shape} | Train N = {len(X_train)} | Test N = {len(X_test)}")

# 1. Rashomon Set Architecture Comparison
rashomon_results = []

architectures = {
    'Elastic-Net': ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42),
    'Random Forest': RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42),
    'XGBoost Trees': xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
}

print("\n[2/3] Evaluating Rashomon Set Multi-Architecture Stability across M, P, N...")

for trait_idx, trait_name in enumerate(traits):
    y_tr = Y_train[:, trait_idx]
    y_te = Y_test[:, trait_idx]
    
    for arch_name, model in architectures.items():
        model.fit(X_train, y_tr)
        preds = model.predict(X_test)
        
        r2 = r2_score(y_te, preds)
        mae = mean_absolute_error(y_te, preds)
        
        rashomon_results.append({
            'Trait': trait_name,
            'Architecture': arch_name,
            'Test_R2': round(r2, 3),
            'Test_MAE': round(mae, 3)
        })

rashomon_df = pd.DataFrame(rashomon_results)

print("\n" + "="*50)
print("  RASHOMON SET MULTI-ARCHITECTURE PERFORMANCE  ")
print("="*50)
print(rashomon_df.to_string(index=False))

# 2. MAPIE v1.4.1 5-Fold Cross-Conformal Prediction Intervals
print("\n[3/3] Wrapping XGBoost in MAPIE 95% Distribution-Free Conformal Prediction Intervals...")
conformal_summary = []

for trait_idx, trait_name in enumerate(traits):
    y_tr = Y_train[:, trait_idx]
    y_te = Y_test[:, trait_idx]
    
    base_model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
    
    mapie = CrossConformalRegressor(estimator=base_model, cv=5, confidence_level=0.95)
    mapie.fit_conformalize(X_train, y_tr)
    
    y_pred, y_pis = mapie.predict_interval(X_test)
    
    low_b = y_pis[:, 0, 0] if y_pis.ndim == 3 else y_pis[:, 0]
    high_b = y_pis[:, 1, 0] if y_pis.ndim == 3 else y_pis[:, 1]
    
    coverage = np.mean((y_te >= low_b) & (y_te <= high_b))
    avg_width = np.mean(high_b - low_b)
    
    conformal_summary.append({
        'Trait': trait_name,
        'Target_Coverage': '95.0%',
        'Empirical_Coverage': f"{coverage*100:.1f}%",
        'Mean_Conformal_Band_Width': round(avg_width, 3)
    })

conformal_df = pd.DataFrame(conformal_summary)

print("\n" + "="*50)
print("  CONFORMAL PREDICTION INTERVALS (MAPIE 95% COVERAGE)  ")
print("="*50)
print(conformal_df.to_string(index=False))

os.makedirs('results', exist_ok=True)
rashomon_df.to_csv('results/rashomon_set_robustness.csv', index=False)
conformal_df.to_csv('results/conformal_prediction_bounds.csv', index=False)

print(f"\nSaved Rashomon set and Conformal Prediction summaries to 'results/'")
print("="*60)
