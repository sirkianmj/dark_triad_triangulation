import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error

print("="*60)
print("  DT3 PROJECT: PHASE 4 - LAYER 2: XGBOOST NON-LINEAR CROSS-CHECK ")
print("="*60)

# Set seed
np.random.seed(42)

# Load master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

# Define External Predictors
predictors = ['age']
for prefix in ['BFI_A_', 'BFI_C_', 'BFI_N_', 'TEQ_', 'RSES_']:
    cols = [c for c in df.columns if c.startswith(prefix)]
    if cols:
        df[f'{prefix}sum'] = df[cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
        predictors.append(f'{prefix}sum')

traits = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']

# Clean dataset
data_clean = df[predictors + traits].dropna()
X = data_clean[predictors].values
Y = data_clean[traits].values

X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.2, random_state=42)

xgb_results = []

print("\n[1/2] Training XGBoost Gradient Boosted Trees for each trait...")

for idx, trait in enumerate(traits):
    y_tr = Y_train[:, idx]
    y_te = Y_test[:, idx]
    
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )
    
    model.fit(X_train, y_tr)
    y_pred = model.predict(X_test)
    
    r2 = r2_score(y_te, y_pred)
    mae = mean_absolute_error(y_te, y_pred)
    
    # Feature Importances
    importances = model.feature_importances_
    top_feature_idx = np.argmax(importances)
    top_feature = predictors[top_feature_idx]
    
    xgb_results.append({
        'Trait': trait,
        'XGBoost_R2': round(r2, 3),
        'XGBoost_MAE': round(mae, 3),
        'Top_Predictor': top_feature,
        'Top_Importance': round(importances[top_feature_idx], 3)
    })
    
    print(f"\nTrait: {trait:22s} | Test R²: {r2:.3f} | MAE: {mae:.3f} | Top Feature: {top_feature} ({importances[top_feature_idx]:.3f})")

xgb_df = pd.DataFrame(xgb_results)

os.makedirs('results', exist_ok=True)
xgb_df.to_csv('results/xgboost_performance_summary.csv', index=False)

print("\n[2/2] Saved XGBoost summary to 'results/xgboost_performance_summary.csv'")
print("="*60)
