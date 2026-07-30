import os
import pandas as pd
import numpy as np
import semopy

print("="*60)
print("  DT3 PROJECT: PHASE 2 - CORRECTED CFA MODEL FIT COMPARISON ")
print("="*60)

# Load master dataset (Sample 1 Community)
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)
s1_df = df[df['sample_origin'] == 'sample_1_community'].copy()

dtdd_cols = [f'DTDD_{i}{t}' for t in ['m', 'p', 'n'] for i in range(1, 5)]
for col in dtdd_cols:
    s1_df[col] = pd.to_numeric(s1_df[col], errors='coerce')

s1_df = s1_df.dropna(subset=dtdd_cols)

# Define Model Specifications
models = {
    "1-Factor Model": "DarkCore =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m + DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p + DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n",
    "2-Factor Model": "M_P =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m + DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p\nNarcissism =~ DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n",
    "3-Factor Model": "Machiavellianism =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m\nPsychopathy =~ DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p\nNarcissism =~ DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n"
}

cfa_results = []

for name, spec in models.items():
    print(f"\nFitting {name} on Sample 1 (N = {len(s1_df)})...")
    try:
        mod = semopy.Model(spec)
        res = mod.fit(s1_df)
        stats = semopy.calc_stats(mod)

        chi2 = stats.loc['Value', 'chi2'] if 'chi2' in stats.columns else np.nan
        dof = stats.loc['Value', 'DoF'] if 'DoF' in stats.columns else np.nan
        cfi = stats.loc['Value', 'CFI'] if 'CFI' in stats.columns else np.nan
        tli = stats.loc['Value', 'TLI'] if 'TLI' in stats.columns else np.nan
        rmsea = stats.loc['Value', 'RMSEA'] if 'RMSEA' in stats.columns else np.nan

        cfa_results.append({
            'Model': name,
            'Chi2': round(float(chi2), 2),
            'df': int(dof),
            'CFI': round(float(cfi), 3),
            'TLI': round(float(tli), 3),
            'RMSEA': round(float(rmsea), 3)
        })
        print(f" -> {name} Fit Complete! CFI: {cfi:.3f}, RMSEA: {rmsea:.3f}")
    except Exception as e:
        print(f" -> Could not fit {name}: {e}")

if cfa_results:
    cfa_df = pd.DataFrame(cfa_results)
    print("\n" + "="*60)
    print("     CONFIRMATORY FACTOR ANALYSIS FIT COMPARISON (CLEAN S1)     ")
    print("="*60)
    print(cfa_df.to_string(index=False))

    os.makedirs('results', exist_ok=True)
    cfa_df.to_csv('results/baseline_cfa_fit.csv', index=False)
    print("\nSaved CFA model fit indices to 'results/baseline_cfa_fit.csv'")
print("="*60)
