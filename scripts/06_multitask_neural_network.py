import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

print("="*60)
print("  DT3 PROJECT: PHASE 4 - LAYER 2: SHARED-TRUNK MULTI-TASK NEURAL NET ")
print("="*60)

# Set random seeds for reproducibility
torch.manual_seed(42)
np.random.seed(42)

# Load master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

# Define External Predictors (Big Five, Empathy, Self-Esteem, Age)
predictors = ['age']
for prefix in ['BFI_A_', 'BFI_C_', 'BFI_N_', 'TEQ_', 'RSES_']:
    cols = [c for c in df.columns if c.startswith(prefix)]
    if cols:
        df[f'{prefix}sum'] = df[cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
        predictors.append(f'{prefix}sum')

traits = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']

# Clean dataset for PyTorch training
data_clean = df[predictors + traits].dropna()
X = data_clean[predictors].values
Y = data_clean[traits].values

print(f"\n[1/4] Prepared feature matrix X shape: {X.shape} | Targets Y shape: {Y.shape}")

# Standardize inputs & targets
scaler_x = StandardScaler()
scaler_y = StandardScaler()

X_scaled = scaler_x.fit_transform(X)
Y_scaled = scaler_y.fit_transform(Y)

X_train, X_test, Y_train, Y_test = train_test_split(X_scaled, Y_scaled, test_size=0.2, random_state=42)

train_dataset = TensorDataset(torch.tensor(X_train, dtype=torch.float32), torch.tensor(Y_train, dtype=torch.float32))
test_dataset = TensorDataset(torch.tensor(X_test, dtype=torch.float32), torch.tensor(Y_test, dtype=torch.float32))

train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=64, shuffle=False)

# Define Shared-Trunk Multi-Task Architecture
class SharedTrunkMultiTaskNet(nn.Module):
    def __init__(self, input_dim):
        super(SharedTrunkMultiTaskNet, self).__init__()
        # Shared Hidden Trunk
        self.trunk = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU()
        )
        # Separate Output Heads
        self.head_mach = nn.Linear(32, 1)
        self.head_psy  = nn.Linear(32, 1)
        self.head_narc = nn.Linear(32, 1)

    def forward(self, x):
        features = self.trunk(x)
        out_mach = self.head_mach(features)
        out_psy  = self.head_psy(features)
        out_narc = self.head_narc(features)
        return torch.cat([out_mach, out_psy, out_narc], dim=1), features

# Instantiate Model
model = SharedTrunkMultiTaskNet(input_dim=X.shape[1])
criterion = nn.MSELoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# Train Multi-Task Model
print("\n[2/4] Training Shared-Trunk Multi-Task Neural Network (100 Epochs)...")
epochs = 100
for epoch in range(1, epochs + 1):
    model.train()
    total_loss = 0.0
    for batch_x, batch_y in train_loader:
        optimizer.zero_grad()
        outputs, _ = model(batch_x)
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * batch_x.size(0)
    
    if epoch % 20 == 0 or epoch == 1:
        avg_loss = total_loss / len(train_loader.dataset)
        print(f" -> Epoch {epoch:3d}/{epochs} | Training MSE Loss: {avg_loss:.4f}")

# Evaluate Model on Test Set
model.eval()
with torch.no_grad():
    test_preds, _ = model(torch.tensor(X_test, dtype=torch.float32))
    test_loss = criterion(test_preds, torch.tensor(Y_test, dtype=torch.float32)).item()

print(f"\n[3/4] Evaluation Complete | Test Set MSE Loss: {test_loss:.4f}")

# Save PyTorch Model Weights & Data Spec
os.makedirs('results', exist_ok=True)
torch.save(model.state_dict(), 'results/shared_trunk_multitask_net.pt')
np.savez('results/multitask_data_spec.npz', X_test=X_test, Y_test=Y_test, predictors=predictors)

print("\n[4/4] Model weights & data specs saved to 'results/'")
print("="*60)
