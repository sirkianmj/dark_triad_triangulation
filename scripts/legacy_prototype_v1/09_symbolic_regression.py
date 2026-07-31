import os
import pandas as pd
import numpy as np
from gplearn.genetic import SymbolicRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

print("="*60)
print("  DT3 PROJECT: PHASE 4 - LAYER 2: SYMBOLIC REGRESSION (GPLEARN) ")
print("="*60)

# Set seeds
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

# Feature names mapping (X0 -> age, X1 -> BFI_A, etc.)
feature_names = predictors
print(f"\n[1/3] Prepared dataset shape: {X.shape} | Predictors: {feature_names}")

# Fit Genetic Symbolic Regressor per trait
discovered_equations = {}

function_set = ['add', 'sub', 'mul', 'div', 'min', 'max']

print("\n[2/3] Running Genetic Programming Symbolic Regression (Population = 1000, Generations = 20)...")

for idx, trait in enumerate(traits):
    print(f"\n--- Discovering Symbolic Equation for {trait} ---")
    y_trait = Y[:, idx]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y_trait, test_size=0.2, random_state=42)
    
    gp = SymbolicRegressor(
        population_size=1000,
        generations=20,
        stopping_criteria=0.01,
        function_set=function_set,
        metric='mean absolute error',
        parsimony_coefficient=0.001,
        random_state=42,
        verbose=1,
        feature_names=feature_names
    )
    
    gp.fit(X_train, y_train)
    
    # Clean expression representation
    expr = str(gp._program)
    discovered_equations[trait] = {
        'Equation': expr,
        'Train_MAE': round(gp._program.raw_fitness_, 4),
        'Length': gp._program.length_,
        'Depth': gp._program.depth_
    }
    
    print(f"\n  -> Discovered Equation for {trait}:")
    print(f"     f(X) = {expr}")

# Summary Table
print("\n" + "="*50)
print("  DISCOVERED GENERATIVE MATHEMATICAL EQUATIONS  ")
print("="*50)

eq_df = pd.DataFrame(discovered_equations).T
print(eq_df.to_string())

os.makedirs('results', exist_ok=True)
eq_df.to_csv('results/symbolic_discovered_equations.csv')

print(f"\n[3/3] Discovered mathematical equations saved to 'results/symbolic_discovered_equations.csv'")
print("="*60)
