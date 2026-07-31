import os
import pandas as pd
import numpy as np
import networkx as nx
import community as community_louvain
import matplotlib.pyplot as plt

print("="*60)
print("  DT3 PROJECT: PHASE 3 - FULL LAYER 1 EXPANSION (ALL ITEMS) ")
print("="*60)

# Load master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

# Select ALL item-level columns (DTDD, BFI, RSES, TEQ items)
all_item_cols = [c for c in df.columns if any(c.startswith(p) for p in ['DTDD_', 'BFI_', 'RSES_', 'TEQ_']) 
                 and not c.endswith(('sum', 'Total', 'T1', 'T2', 'origin', 'quality'))]

item_df = df[all_item_cols].apply(pd.to_numeric, errors='coerce')
item_df = item_df.loc[:, item_df.std() > 0.01].dropna(thresh=50)

print(f"\n[1/3] Selected {item_df.shape[1]} active item-level variables across N = {len(item_df)} respondents.")

# 1. Regularized Precision Matrix (Ridge GGM)
print("\n[2/3] Estimating Regularized GGM Network (Ridge Lambda = 0.01)...")
corr_matrix = item_df.corr(method='pearson')

lambda_reg = 0.01
reg_corr = corr_matrix.values + lambda_reg * np.eye(corr_matrix.shape[0])
inv_corr = np.linalg.inv(reg_corr)

d = np.diag(inv_corr)
partial_corr = -inv_corr / np.sqrt(np.outer(d, d))
np.fill_diagonal(partial_corr, 0.0)

p_corr_df = pd.DataFrame(partial_corr, index=corr_matrix.index, columns=corr_matrix.columns)

# Build Network Graph with absolute weights for Louvain
G = nx.Graph()
threshold = 0.08  # Edge threshold

for i in range(len(p_corr_df.columns)):
    for j in range(i + 1, len(p_corr_df.columns)):
        w = p_corr_df.iloc[i, j]
        if abs(w) >= threshold:
            G.add_edge(p_corr_df.columns[i], p_corr_df.columns[j], weight=abs(w), raw_weight=w)

print(f" -> Full GGM Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges (threshold >= 0.08).")

# 2. Louvain Community Detection on Full Item Network
print("\n[3/3] Running Louvain Community Detection on Full Item Space...")
partition = community_louvain.best_partition(G, weight='weight', random_state=42)

dtdd_items = [c for c in item_df.columns if c.startswith('DTDD_') and not c.endswith(('sum', 'Total'))]

print("\n" + "="*50)
print("  EMERGENT COMMUNITIES FOR DTDD ITEMS IN FULL ITEM SPACE  ")
print("="*50)

community_groups = {}
for node, comm_id in partition.items():
    if node in dtdd_items:
        community_groups.setdefault(comm_id, []).append(node)

for comm_id, items in sorted(community_groups.items()):
    print(f" Cluster {comm_id}: {sorted(items)}")

# Save Full Network Diagram
os.makedirs('results/figures', exist_ok=True)
plt.figure(figsize=(12, 10))
pos = nx.spring_layout(G, seed=42)
cmap = plt.get_cmap('tab20')

colors = [partition[node] for node in G.nodes()]
nx.draw_networkx_nodes(G, pos, node_size=300, node_color=colors, cmap=cmap)
nx.draw_networkx_edges(G, pos, alpha=0.25, width=1.0)

dtdd_labels = {node: node for node in G.nodes() if node in dtdd_items}
nx.draw_networkx_labels(G, pos, labels=dtdd_labels, font_size=8, font_weight='bold')

plt.title("Layer 1: Full Item-Space Partial Correlation Network (Louvain Communities)", fontsize=12)
plt.axis('off')
fig_out = 'results/figures/layer1_full_ggm_network.png'
plt.savefig(fig_out, dpi=300, bbox_inches='tight')
plt.close()

print(f"\nSaved full network figure to '{fig_out}'")
print("="*60)
