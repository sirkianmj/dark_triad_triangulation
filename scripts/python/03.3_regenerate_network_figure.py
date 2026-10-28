#!/usr/bin/env python3
"""Phase 3.3: Regenerate Figure 2 (clean 82-item network at gamma=1.0) as vector PDF."""
import os, warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, networkx as nx
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from sklearn.covariance import graphical_lasso
import community as community_louvain

TABLES, FIGURES = "results/tables", "results/figures"
DTDD = [f"DTDD_{i}{s}" for s in 'mpn' for i in range(1,5)]
BFI = [f"BFI_{d}_{i}" for d,n in [('A',9),('C',9),('N',8),('O',10),('E',8)] for i in range(1,n+1)]
TEQ = [f"TEQ_{i}" for i in range(1,17)]
RSES = [f"RSES_{i}" for i in range(1,11)]
ITEMS = DTDD + BFI + TEQ + RSES

def make_pd(m, tol=1e-8):
    s = (m + m.T)/2; w, v = np.linalg.eigh(s)
    if np.all(w >= tol): return s
    w[w<tol] = tol; r = v @ np.diag(w) @ v.T
    d = np.sqrt(np.diag(r)); return r/np.outer(d,d)

def pairwise_corr(df, mp=10):
    c = df.columns; P = len(c); r = np.eye(P); n = np.zeros((P,P), int)
    for i in range(P):
        for j in range(i+1,P):
            m = df.iloc[:,i].notna() & df.iloc[:,j].notna()
            if m.sum() >= mp:
                xi, xj = df.iloc[:,i][m].astype(float), df.iloc[:,j][m].astype(float)
                if xi.var()>0 and xj.var()>0:
                    rv = np.corrcoef(xi, xj)[0,1]
                    if np.isfinite(rv): r[i,j]=r[j,i]=rv; n[i,j]=n[j,i]=m.sum(); continue
            r[i,j]=r[j,i]=0.0
    return r, n

def harmonic(v):
    v = np.asarray(v); v = v[v>0]
    return len(v)/np.sum(1.0/v) if len(v) else 0.0

def ebic(ld, tr, n, P, e): return -n*(ld-tr) + e*np.log(n) + 4*0.5*e*np.log(P)

df = pd.read_csv("data/processed/dt3_master_dataset.csv", low_memory=False)
comm = df[df.sample_origin == "sample_1_community"].copy()
r, ns = pairwise_corr(comm[ITEMS]); r = make_pd(r)
off = ns[np.triu_indices_from(ns, k=1)]; N_eff = harmonic(off)
best = (np.inf, None, None)
for a in np.logspace(-3, 0, 40):
    try:
        _, prec = graphical_lasso(r, alpha=a, max_iter=1000)
        sg, ld = np.linalg.slogdet(prec)
        if not np.isfinite(ld) or sg <= 0: continue
        tr = np.sum(r * prec); e = np.count_nonzero(prec - np.diag(np.diag(prec)))/2
        ev = ebic(ld, tr, N_eff, len(ITEMS), e)
        if ev < best[0]: best = (ev, a, prec)
    except: continue
_, alpha, prec = best
diag = np.diag(prec); pcorr = -prec * np.outer(1/np.sqrt(diag), 1/np.sqrt(diag))
np.fill_diagonal(pcorr, 1.0)
G = nx.Graph(); G.add_nodes_from(ITEMS)
for i in range(len(ITEMS)):
    for j in range(i+1, len(ITEMS)):
        if abs(pcorr[i,j]) > 0.01: G.add_edge(ITEMS[i], ITEMS[j], weight=abs(pcorr[i,j]))
partition = community_louvain.best_partition(G, weight='weight', resolution=1.0, random_state=42)
n_comm = len(set(partition.values()))
print(f"Clean 82-item: N_eff={N_eff:.0f}, alpha={alpha:.4f}, edges={G.number_of_edges()}, comms={n_comm}")
print(f"DTDD items -> {len(set(partition[i] for i in DTDD))} cluster(s)")

fig, ax = plt.subplots(figsize=(18, 16))
pos = nx.spring_layout(G, k=1.5, seed=42, iterations=200)
cmap = plt.get_cmap('tab20')
node_colors = [cmap(partition[n] % 20) for n in G.nodes()]
node_sizes = [500 if n in DTDD else 150 for n in G.nodes()]
nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors,
                        edgecolors='black', linewidths=0.7, alpha=0.9, ax=ax)
nx.draw_networkx_edges(G, pos, alpha=0.25, width=0.8, edge_color='gray', ax=ax)
nx.draw_networkx_labels(G, pos, font_size=7, ax=ax)
dtdd_comm = partition[DTDD[0]]
dtdd_handle = Patch(facecolor=cmap(dtdd_comm % 20), edgecolor='black',
                    label=f'Community {dtdd_comm} (DTDD, {sum(1 for n in G if partition[n]==dtdd_comm)} items)')
ax.legend(handles=[dtdd_handle], loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=10)
ax.set_title(f"Clean 82-item network (community sample, harmonic N~{N_eff:.0f}, P=82)\n"
             f"All 12 DTDD items in one community (gamma=1.0)", fontsize=13)
ax.axis('off')
plt.tight_layout()
plt.savefig(f"{FIGURES}/layer1_ggm_network_Full_Item_Space_clean.pdf", bbox_inches='tight')
plt.savefig(f"{FIGURES}/layer1_ggm_network_Full_Item_Space_clean.png", dpi=300, bbox_inches='tight')
plt.close()
print(f"Wrote {FIGURES}/layer1_ggm_network_Full_Item_Space_clean.{{pdf,png}}")
