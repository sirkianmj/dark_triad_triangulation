import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from causallearn.search.ConstraintBased.PC import pc
from causallearn.utils.cit import fisherz

print("="*60)
print("  DT3 PROJECT: PHASE 5 - LAYER 3: PC CAUSAL DISCOVERY (DAG)  ")
print("="*60)

# Set seed
np.random.seed(42)

# Load master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

# Define variables
predictors = ['age']
for prefix in ['BFI_A_', 'BFI_C_', 'BFI_N_', 'TEQ_', 'RSES_']:
    cols = [c for c in df.columns if c.startswith(prefix)]
    if cols:
        df[f'{prefix}sum'] = df[cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
        predictors.append(f'{prefix}sum')

traits = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']
var_names = predictors + traits

# Clean dataset
data_clean = df[var_names].dropna()
data_matrix = data_clean.values

print(f"\n[1/3] Prepared data matrix for Causal Discovery: N = {len(data_clean)} | Variables = {len(var_names)}")

# 1. Run PC Causal Discovery Algorithm
print("\n[2/3] Running PC Constraint-Based Causal Discovery (Fisher-Z test, alpha = 0.01)...")
cg = pc(data_matrix, alpha=0.01, indep_test=fisherz, verbose=False)

# Extract Causal Direct Antecedents (Parents) for each trait
graph_mat = cg.G.graph

def find_parents(node_idx):
    # In causallearn G.graph matrix, -1 represents tail/incoming edge
    parents = []
    for i in range(len(var_names)):
        if i != node_idx:
            # Check directed edge i -> node_idx
            if graph_mat[i, node_idx] == -1 and graph_mat[node_idx, i] == 1:
                parents.append(var_names[i])
            elif graph_mat[i, node_idx] != 0:
                parents.append(f"{var_names[i]} (undirected/bidirected)")
    return parents

mach_idx = var_names.index('score_Machiavellianism')
psy_idx  = var_names.index('score_Psychopathy')
narc_idx = var_names.index('score_Narcissism')

mach_parents = find_parents(mach_idx)
psy_parents  = find_parents(psy_idx)
narc_parents = find_parents(narc_idx)

print("\n" + "="*50)
print("  INFERRED CAUSAL ANTECEDENTS (DIRECT PARENTS)  ")
print("="*50)
print(f" Machiavellianism Causal Parents : {mach_parents if mach_parents else 'None (Exogenous/Independent)'}")
print(f" Psychopathy Causal Parents      : {psy_parents if psy_parents else 'None (Exogenous/Independent)'}")
print(f" Narcissism Causal Parents       : {narc_parents if narc_parents else 'None (Exogenous/Independent)'}")

# Save Causal Parents Summary
os.makedirs('results', exist_ok=True)
causal_df = pd.DataFrame([
    {'Trait': 'Machiavellianism', 'Causal_Parents': ', '.join(mach_parents) if mach_parents else 'None'},
    {'Trait': 'Psychopathy', 'Causal_Parents': ', '.join(psy_parents) if psy_parents else 'None'},
    {'Trait': 'Narcissism', 'Causal_Parents': ', '.join(narc_parents) if narc_parents else 'None'}
])
causal_df.to_csv('results/causal_parents_summary.csv', index=False)

print(f"\n[3/3] Causal parent relationships saved to 'results/causal_parents_summary.csv'")
print("="*60)
