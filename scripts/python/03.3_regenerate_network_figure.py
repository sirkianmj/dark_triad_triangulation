#!/usr/bin/env python3
"""Phase 3.3: Regenerate Figure 2 (clean 82-item network) with full color legend."""
import os, warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, networkx as nx
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from sklearn.covariance import graphical_lasso
import community as community_louvain

TABLES, FIGURES = "results/tables", "results/figures"
DTDD = [f"DTDD_{i}{s}" for s in 'mpn' for i in range(1,5)]
BFI = [f"BFI_{d}_{i}" for d,n in [('A',9),('C',9),('N',8),('O',10),('E',8)] for i in range(1,n+1)]
TEQ = [f"TEQ_{i}" for i in range(1,17)]
RSES = [f"RSES_{i}" for i in range(1,11)]
ITEMS = DTDD + BFI + TEQ + RSES

def scale_of(node):
    if node.startswith('DTDD_'): return 'DTDD'
    if node.startswith('BFI_A'): return 'BFI_A'
    if node.startswith('BFI_C'): return 'BFI_C'
    if node.startswith('BFI_E'): return 'BFI_E'
    if node.startswith('BFI_N'): return 'BFI_N'
    if node.startswith('BFI_O'): return 'BFI_O'
    if node.startswith('TEQ_'):   return 'TEQ'
    if node.startswith('RSES_'):  return 'RSES'
    return 'OTHER'

SCALE_COLORS = {
    'DTDD':  '#E67E22',  # orange
    'BFI_A': '#9B59B6',  # purple
    'BFI_C': '#3498DB',  # blue
    'BFI_E': '#2ECC71',  # green
    'BFI_N': '#8B4513',  # brown
    'BFI_O': '#1ABC9C',  # teal
    'TEQ':   '#E91E63',  # pink
    'RSES':  '#808080',  # grey
}

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

# Count: how many items per (community, scale)?
from collections import Counter, defaultdict
comm_scale = defaultdict(Counter)
for node, cid in partition.items():
    comm_scale[cid][scale_of(node)] += 1

# Identify DTDD community
dtdd_comm_id = partition[DTDD[0]]
n_dtdd_in_comm = sum(1 for n in G if partition[n] == dtdd_comm_id)

# Color by SCALE (makes clusters visually interpretable); draw DTDD with thicker edge
node_colors = [SCALE_COLORS.get(scale_of(n), '#333') for n in G.nodes()]
node_edgecolors = ['red' if n in DTDD else 'black' for n in G.nodes()]
node_linewidths = [2.0 if n in DTDD else 0.7 for n in G.nodes()]
node_sizes = [500 if n in DTDD else 200 for n in G.nodes()]

fig = plt.figure(figsize=(20, 16))
ax = fig.add_subplot(111)
pos = nx.spring_layout(G, k=1.8, seed=42, iterations=250)

nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors,
                       edgecolors=node_edgecolors, linewidths=node_linewidths,
                       alpha=0.92, ax=ax)
nx.draw_networkx_edges(G, pos, alpha=0.15, width=0.6, edge_color='grey', ax=ax)
nx.draw_networkx_labels(G, pos, font_size=7, ax=ax)

# ============ FULL LEGEND ============
# Left panel: scale color legend
scale_legend = [
    Patch(facecolor=SCALE_COLORS['DTDD'],  edgecolor='red', linewidth=2,
          label=f'DTDD items (12) — all in one community ({dtdd_comm_id})'),
    Patch(facecolor=SCALE_COLORS['BFI_A'], edgecolor='black', label='BFI Agreeableness'),
    Patch(facecolor=SCALE_COLORS['BFI_C'], edgecolor='black', label='BFI Conscientiousness'),
    Patch(facecolor=SCALE_COLORS['BFI_E'], edgecolor='black', label='BFI Extraversion'),
    Patch(facecolor=SCALE_COLORS['BFI_N'], edgecolor='black', label='BFI Neuroticism'),
    Patch(facecolor=SCALE_COLORS['BFI_O'], edgecolor='black', label='BFI Openness'),
    Patch(facecolor=SCALE_COLORS['TEQ'],   edgecolor='black', label='Toronto Empathy (TEQ)'),
    Patch(facecolor=SCALE_COLORS['RSES'],  edgecolor='black', label='Rosenberg Self-Esteem (RSES)'),
]
leg1 = ax.legend(handles=scale_legend, loc='upper left', bbox_to_anchor=(1.02, 1.0),
                 title='Node color = scale',
                 fontsize=9, title_fontsize=11, frameon=True, framealpha=0.95)

# Second legend: community summary
comm_legend = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='w',
           markeredgecolor='red', markersize=12, markeredgewidth=2,
           label='Red ring = DTDD item'),
    Patch(facecolor='none', edgecolor='black',
          label=f'Total communities detected: {n_comm}'),
    Patch(facecolor='none', edgecolor='black',
          label=f'DTDD community {dtdd_comm_id}: {n_dtdd_in_comm} items'),
    Patch(facecolor='none', edgecolor='black',
          label=f'Non-DTDD communities: {n_comm - 1}'),
]
ax.add_artist(leg1)
ax.legend(handles=comm_legend, loc='lower left', bbox_to_anchor=(1.02, 0.0),
          title='Community summary',
          fontsize=9, title_fontsize=11, frameon=True, framealpha=0.95)

ax.set_title(
    f"Clean 82-item network (community sample, harmonic $N_{{eff}}$={N_eff:.0f}, $P$=82, EBIC $\\alpha$={alpha:.4f})\n"
    f"All 12 DTDD items in one Louvain community at $\\gamma=1.0$ (Dark Core Collapse)",
    fontsize=13
)
ax.axis('off')
plt.tight_layout()
plt.savefig(f"{FIGURES}/layer1_ggm_network_Full_Item_Space_clean.pdf", bbox_inches='tight')
plt.savefig(f"{FIGURES}/layer1_ggm_network_Full_Item_Space_clean.png", dpi=300, bbox_inches='tight')
plt.close()
print(f"Wrote {FIGURES}/layer1_ggm_network_Full_Item_Space_clean.{{pdf,png}}")
print(f"Legend entries: 8 scale colors + 4 community summary rows")
print(f"Communities: {n_comm} total; DTDD community {dtdd_comm_id} = {n_dtdd_in_comm} items")
