import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import matplotlib.pyplot as plt

print("="*60)
print("  DT3 PROJECT: PHASE 4 - LAYER 2: CKA / RSA REPRESENTATIONAL GEOMETRY ")
print("="*60)

# Set seeds
torch.manual_seed(42)

# Load data specs & master dataset
data_spec = np.load('results/multitask_data_spec.npz')
X_test = data_spec['X_test']
Y_test = data_spec['Y_test']

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
        return torch.cat([out_mach, out_psy, out_narc], dim=1), features

model = SharedTrunkMultiTaskNet(input_dim=X_test.shape[1])
model.load_state_dict(torch.load('results/shared_trunk_multitask_net.pt'))
model.eval()

# Extract Shared Hidden Trunk Activations (32-dim)
with torch.no_grad():
    _, activations = model(torch.tensor(X_test, dtype=torch.float32))
    H = activations.numpy()

print(f"\n[1/3] Extracted 32-dimensional shared trunk activations H shape: {H.shape}")

# Identify High-Scorers (Top 25th percentile for each trait)
high_mach_idx = np.where(Y_test[:, 0] >= np.percentile(Y_test[:, 0], 75))[0]
high_psy_idx  = np.where(Y_test[:, 1] >= np.percentile(Y_test[:, 1], 75))[0]
high_narc_idx = np.where(Y_test[:, 2] >= np.percentile(Y_test[:, 2], 75))[0]

H_mach = H[high_mach_idx]
H_psy  = H[high_psy_idx]
H_narc = H[high_narc_idx]

# Centered Kernel Alignment (Linear CKA) Function
def centering_matrix(n):
    return np.eye(n) - np.ones((n, n)) / n

def linear_hsic(X, Y):
    X_c = np.dot(centering_matrix(X.shape[0]), X)
    Y_c = np.dot(centering_matrix(Y.shape[0]), Y)
    return np.sum(np.dot(X_c, X_c.T) * np.dot(Y_c, Y_c.T))

def linear_cka(X, Y):
    # Equalize sample sizes for comparative HSIC computation
    min_n = min(X.shape[0], Y.shape[0])
    X_sub = X[:min_n]
    Y_sub = Y[:min_n]
    
    hsic_xy = linear_hsic(X_sub, Y_sub)
    hsic_xx = linear_hsic(X_sub, X_sub)
    hsic_yy = linear_hsic(Y_sub, Y_sub)
    
    return hsic_xy / np.sqrt(hsic_xx * hsic_yy)

print("\n[2/3] Computing Linear CKA Representational Similarities...")
cka_m_p = linear_cka(H_mach, H_psy)
cka_m_n = linear_cka(H_mach, H_narc)
cka_p_n = linear_cka(H_psy, H_narc)

cka_matrix = pd.DataFrame([
    [1.0, cka_m_p, cka_m_n],
    [cka_m_p, 1.0, cka_p_n],
    [cka_m_n, cka_p_n, 1.0]
], index=['Machiavellianism', 'Psychopathy', 'Narcissism'], columns=['Machiavellianism', 'Psychopathy', 'Narcissism'])

print("\n" + "="*50)
print("  CENTERED KERNEL ALIGNMENT (CKA) SIMILARITY MATRIX  ")
print("="*50)
print(cka_matrix.round(4))

# Save Results
os.makedirs('results/figures', exist_ok=True)
cka_matrix.to_csv('results/cka_representational_similarity.csv')

# Plot CKA Matrix
plt.figure(figsize=(7, 6))
plt.imshow(cka_matrix.values, cmap='magma', vmin=0, vmax=1)
plt.colorbar(label='Linear CKA Similarity')
plt.xticks(range(3), cka_matrix.columns, rotation=15)
plt.yticks(range(3), cka_matrix.index)

for i in range(3):
    for j in range(3):
        plt.text(j, i, f"{cka_matrix.iloc[i, j]:.3f}", ha='center', va='center', color='white' if cka_matrix.iloc[i, j] < 0.7 else 'black', fontweight='bold')

plt.title("Layer 2: Shared-Trunk CKA Representational Geometry", fontsize=11)
plt.tight_layout()
fig_out = 'results/figures/layer2_cka_similarity.png'
plt.savefig(fig_out, dpi=300)
plt.close()

print(f"\n[3/3] Saved CKA similarity matrix and heatmap to 'results/' and '{fig_out}'")
print("="*60)
