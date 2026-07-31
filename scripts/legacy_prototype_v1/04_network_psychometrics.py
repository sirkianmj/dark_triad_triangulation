import os
import pandas as pd
import numpy as np
import networkx as nx
import community as community_louvain
import matplotlib.pyplot as plt

print("="*60)
print("  DT3 PROJECT: PHASE 3 - LAYER 1: NETWORK PSYCHOMETRICS (GGM)  ")
print("="*60)

# Load master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

# Select 12 core DTDD item-level columns
dtdd_cols = [f'DTDD_{i}{t}' for t in ['m', 'p', 'n'] for i in range(1, 5)]
item_df = df[dtdd_cols].dropna()

print(f"\n[1/4] Selected {len(dtdd_cols)} DTDD item-level variables across N = {len(item_df)} respondents.")

# 1. Compute Partial Correlation Matrix (Gaussian Graphical Model)
print("\n[2/4] Estimating Gaussian Graphical Model (Partial Correlation Matrix)...")
corr_matrix = item_df.corr(method='pearson')

# Inverse covariance matrix calculation for partial correlations
inv_corr = np.linalg.pinv(corr_matrix.values)
d = np.diag(inv_corr)
partial_corr = -inv_corr / np.sqrt(np.outer(d, d))
np.fill_diagonal(partial_corr, 0.0)

p_corr_df = pd.DataFrame(partial_corr, index=corr_matrix.index, columns=corr_matrix.columns)

# 2. Build NetworkX Graph
G = nx.Graph()
threshold = 0.05  # Retain edges with absolute partial correlation > 0.05

for i in range(len(p_corr_df.columns)):
    for j in range(i + 1, len(p_corr_df.columns)):
        weight = p_corr_df.iloc[i, j]
        if abs(weight) >= threshold:
            G.add_edge(p_corr_df.columns[i], p_corr_df.columns[j], weight=weight)

print(f" -> GGM Graph built with {G.number_of_nodes()} item nodes and {G.number_of_edges()} partial correlation edges (threshold >= 0.05).")

# 3. Louvain Unsupervised Community Detection
print("\n[3/4] Running Louvain Unsupervised Community Detection...")
partition = community_louvain.best_partition(G, weight='weight', random_state=42)

# Analyze emergent communities for DTDD items
print("\n" + "="*50)
print("  EMERGENT COMMUNITIES FOR DARK TRIAD ITEMS  ")
print("="*50)

community_groups = {}
for node, comm_id in partition.items():
    community_groups.setdefault(comm_id, []).append(node)

for comm_id, items in sorted(community_groups.items()):
    print(f" Community Cluster {comm_id}: {sorted(items)}")

# 4. Save Network Visualization
os.makedirs('results/figures', exist_ok=True)
plt.figure(figsize=(10, 8))
pos = nx.spring_layout(G, seed=42)
cmap = plt.get_cmap('tab10')

colors = [partition[node] for node in G.nodes()]
nx.draw_networkx_nodes(G, pos, node_size=600, node_color=colors, cmap=cmap)
nx.draw_networkx_edges(G, pos, alpha=0.4, width=1.5)
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')

plt.title("Layer 1: Unsupervised Partial Correlation Network (Louvain Communities)", fontsize=12)
plt.axis('off')
figure_path = 'results/figures/layer1_ggm_network.png'
plt.savefig(figure_path, dpi=300, bbox_inches='tight')
plt.close()

print(f"\n[4/4] Network diagram saved to '{figure_path}'")
print("="*60)
