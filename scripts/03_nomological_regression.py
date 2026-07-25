import pandas as pd
import numpy as np
import statsmodels.api as sm

print("="*60)
print("  DT3 PROJECT: PHASE 2 - NOMOLOGICAL NETWORK REGRESSION BASELINE ")
print("="*60)

# Load master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

# Compute Correlate Scales if not already present
bfi_a_cols = [c for c in df.columns if c.startswith('BFI_A_')]
bfi_c_cols = [c for c in df.columns if c.startswith('BFI_C_')]
bfi_n_cols = [c for c in df.columns if c.startswith('BFI_N_')]
teq_cols   = [c for c in df.columns if c.startswith('TEQ_')]
rses_cols  = [c for c in df.columns if c.startswith('RSES_')]

if bfi_a_cols: df['BFI_A_sum'] = df[bfi_a_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
if bfi_c_cols: df['BFI_C_sum'] = df[bfi_c_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
if bfi_n_cols: df['BFI_N_sum'] = df[bfi_n_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
if teq_cols:   df['TEQ_sum']   = df[teq_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
if rses_cols:  df['RSES_sum']  = df[rses_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)

predictors = ['age']
for col in ['BFI_A_sum', 'BFI_C_sum', 'BFI_N_sum', 'TEQ_sum', 'RSES_sum']:
    if col in df.columns and df[col].notna().sum() > 500:
        predictors.append(col)

print(f"\nAvailable External Predictors: {predictors}")

traits = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']

regression_summary = []

for trait in traits:
    print(f"\n" + "="*50)
    print(f" OLS REGRESSION: Predicting {trait}")
    print("="*50)
    
    # Filter dataset for available rows
    reg_df = df[[trait] + predictors].dropna()
    
    X = reg_df[predictors]
    # Standardize predictors for comparable beta weights
    X_std = (X - X.mean()) / X.std()
    X_std = sm.add_constant(X_std)
    
    y = reg_df[trait]
    
    model = sm.OLS(y, X_std).fit()
    print(model.summary().tables[1])
    print(f"Model R-squared: {model.rsquared:.3f} | Adj. R-squared: {model.rsquared_adj:.3f} | N = {len(reg_df)}")
    
    for var in predictors:
        regression_summary.append({
            'Trait': trait,
            'Predictor': var,
            'Beta_Std': round(model.params[var], 3),
            'P_value': round(model.pvalues[var], 4),
            'R2': round(model.rsquared, 3)
        })

summary_df = pd.DataFrame(regression_summary)
summary_df.to_csv('results/baseline_ols_regressions.csv', index=False)

print("\nSaved OLS baseline summary to 'results/baseline_ols_regressions.csv'")
print("="*60)
