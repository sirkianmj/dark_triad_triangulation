import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import shap
import matplotlib.pyplot as plt

print("="*60)
print("  DT3 PROJECT: PHASE 4 - LAYER 2: SHAP MULTI-HEAD ATTRIBUTION ")
print("="*60)

# Set seeds
torch.manual_seed(42)

# Load data specs
data_spec = np.load('results/multitask_data_spec.npz')
X_test = data_spec['X_test']
predictors = list(data_spec['predictors'])

# Define Model Architecture
class SharedTrunkMultiTaskNet(nn.Module):
    def __init__(self, input_dim):
        super(SharedTrunkMultiTaskNet, self).__init__()
        self.trunk = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU()
        )
        self.head_mach = nn.Linear(32, 1)
        self.head_psy  = nn.Linear(32, 1)
        self.head_narc = nn.Linear(32, 1)

    def forward(self, x):
        features = self.trunk(x)
        out_mach = self.head_mach(features)
        out_psy  = self.head_psy(features)
        out_narc = self.head_narc(features)
        return torch.cat([out_mach, out_psy, out_narc], dim=1)

model = SharedTrunkMultiTaskNet(input_dim=len(predictors))
model.load_state_dict(torch.load('results/shared_trunk_multitask_net.pt'))
model.eval()

print(f"\n[1/3] Loaded PyTorch model and test set (N = {len(X_test)}).")

# Compute SHAP Values using GradientExplainer
print("\n[2/3] Computing SHAP values across output heads (Mach, Psy, Narc)...")
background = torch.tensor(X_test[:100], dtype=torch.float32)
test_samples = torch.tensor(X_test[:500], dtype=torch.float32)

explainer = shap.GradientExplainer(model, background)
shap_values = explainer.shap_values(test_samples)

# Print Mean Absolute SHAP Importance per Trait Head
traits = ['Machiavellianism', 'Psychopathy', 'Narcissism']

print("\n" + "="*50)
print("  MEAN ABSOLUTE SHAP IMPORTANCE BY TRAIT HEAD  ")
print("="*50)

shap_summary_dict = {}

for head_idx, trait in enumerate(traits):
    # Extract SHAP array for trait head
    if isinstance(shap_values, list):
        s_val = shap_values[head_idx]
    else:
        s_val = shap_values[:, :, head_idx]
        
    mean_abs_shap = np.abs(s_val).mean(axis=0)
    shap_summary_dict[trait] = mean_abs_shap
    
    print(f"\nTarget Head: {trait}")
    for pred, imp in sorted(zip(predictors, mean_abs_shap), key=lambda x: x[1], reverse=True):
        print(f"  -> {pred:12s}: {imp:.4f}")

# Quantify SHAP Divergence (Cosine Distance between SHAP vectors)
from scipy.spatial.distance import cosine

m_vec = shap_summary_dict['Machiavellianism']
p_vec = shap_summary_dict['Psychopathy']
n_vec = shap_summary_dict['Narcissism']

div_m_p = cosine(m_vec, p_vec)
div_m_n = cosine(m_vec, n_vec)
div_p_n = cosine(p_vec, n_vec)

print("\n" + "="*50)
print("  PAIRWISE SHAP ATTRIBUTION DIVERGENCE (COSINE DISTANCE)  ")
print("="*50)
print(f" Machiavellianism vs Psychopathy : {div_m_p:.4f}")
print(f" Machiavellianism vs Narcissism  : {div_m_n:.4f}")
print(f" Psychopathy vs Narcissism       : {div_p_n:.4f}")

# Save Summary
os.makedirs('results/figures', exist_ok=True)
shap_df = pd.DataFrame(shap_summary_dict, index=predictors)
shap_df.to_csv('results/shap_head_importance.csv')

print(f"\n[3/3] Saved SHAP feature attributions to 'results/shap_head_importance.csv'")
print("="*60)
