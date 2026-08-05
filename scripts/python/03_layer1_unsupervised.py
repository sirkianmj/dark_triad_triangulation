#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 3 (REMEDIATED v4): Layer 1 - Unsupervised Structural Evidence
===============================================================================
Methodologically rigorous script for Network Psychometrics (EBICglasso) and
Topological Data Analysis (Mapper).  Incorporates critical fixes:

FLAW 2 FIX (FULL – v4):
  - Complete‑case analysis for N >= 30; otherwise pairwise‑deletion correlation.
  - `pairwise_correlation` hardened against zero‑variance and NaN contagion.
  - Projection to the nearest positive‑definite correlation matrix before
    GraphicalLasso, preventing `Duality gap: nan` and eigenvalue collapse.
  - EBIC loop now uses `graphical_lasso` (functional API) to correctly
    process a precomputed correlation matrix, avoiding the scikit‑learn
    Object‑Oriented trap that recalculates covariance from the matrix.
  - Removed the zombie ridge penalty (diagonal must remain exactly 1.0).

OUTPUT FILES:
  - results/figures/layer1_ggm_network_DTDD_Only.png
  - results/figures/layer1_ggm_network_Full_Item_Space.png
  - results/figures/layer1_tda_mapper.html
  - results/tables/layer1_ggm_communities_DTDD_Only.csv
  - results/tables/layer1_ggm_communities_Full_Item_Space.csv
===============================================================================
"""

import os
import sys
import logging
import hashlib
import numpy as np
import pandas as pd
import networkx as nx
import community as community_louvain
import matplotlib.pyplot as plt
from sklearn.covariance import graphical_lasso  # functional API – critical fix
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import DBSCAN
import kmapper as km

# -----------------------------------------------------------------------------
# DIRECTORY & LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
PROCESSED_DIR = "data/processed"
RESULTS_DIR = "results"
FIGURES_DIR = "results/figures"
TABLES_DIR = "results/tables"

for d in [RESULTS_DIR, FIGURES_DIR, TABLES_DIR]:
    os.makedirs(d, exist_ok=True)

log_path = os.path.join(TABLES_DIR, "execution_audit.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(log_path, mode='a'), logging.StreamHandler(sys.stdout)],
    force=True
)

class FatalScienceError(Exception):
    pass

CORE_DTDD = [
    'DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m',
    'DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p',
    'DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n'
]

# -----------------------------------------------------------------------------
# CRYPTOGRAPHIC PROVENANCE
# -----------------------------------------------------------------------------
def hash_file(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# -----------------------------------------------------------------------------
# ZERO‑TRUST MATHEMATICS
# -----------------------------------------------------------------------------
def compute_ebic(logdet, trace, n_samples, n_features, n_edges, gamma=0.5):
    """
    Extended Bayesian Information Criterion.
    n_samples must be the effective sample size.
    """
    neg_2_ll = -n_samples * (logdet - trace)
    penalty = n_edges * np.log(n_samples) + 4 * gamma * n_edges * np.log(n_features)
    return neg_2_ll + penalty

def precision_to_partial_corr(precision_matrix):
    """Convert precision matrix to partial correlation matrix."""
    diag = np.diag(precision_matrix)
    if np.any(diag <= 0):
        raise FatalScienceError("Non‑positive variance on precision diagonal.")
    inv_sqrt_diag = 1.0 / np.sqrt(diag)
    partial_corr = -precision_matrix * np.outer(inv_sqrt_diag, inv_sqrt_diag)
    np.fill_diagonal(partial_corr, 1.0)
    return partial_corr

def harmonic_mean(values):
    """Compute harmonic mean of an array, ignoring zeros."""
    vals = np.asarray(values)
    vals = vals[vals > 0]
    if len(vals) == 0:
        return 0.0
    return len(vals) / np.sum(1.0 / vals)

# -----------------------------------------------------------------------------
# HARDENED PAIRWISE CORRELATION (prevents NaN contagion)
# -----------------------------------------------------------------------------
def pairwise_correlation(df, min_per_pair=10):
    """
    Compute a pairwise-deletion correlation matrix.
    Includes strict checks for zero-variance subsets to prevent NaN contagion.
    """
    cols = df.columns
    P = len(cols)
    corr = np.eye(P)
    ns = np.zeros((P, P), dtype=int)
    for i in range(P):
        for j in range(i + 1, P):
            mask = df.iloc[:, i].notna() & df.iloc[:, j].notna()
            n = mask.sum()
            ns[i, j] = ns[j, i] = n
            if n >= min_per_pair:
                xi = df.iloc[:, i][mask].astype(float)
                xj = df.iloc[:, j][mask].astype(float)
                # Check for zero variance to prevent np.corrcoef NaN output
                if np.var(xi) > 0 and np.var(xj) > 0:
                    r = np.corrcoef(xi, xj)[0, 1]
                    if not np.isnan(r):
                        corr[i, j] = corr[j, i] = r
                        continue
            # Fallback if low N, zero variance, or NaN
            corr[i, j] = corr[j, i] = 0.0
    return corr, ns

# -----------------------------------------------------------------------------
# MATRIX PROJECTION TO POSITIVE DEFINITE (prevent GraphicalLasso collapse)
# -----------------------------------------------------------------------------
def make_positive_definite(corr_matrix, tol=1e-8):
    """
    Projects a symmetric matrix to the nearest Positive Definite matrix.
    Uses eigenvalue decomposition to clip negative eigenvalues, followed
    by re-normalization to restore the correlation matrix structure (diagonal=1).
    Crucial for GraphicalLasso to prevent 'Duality gap: nan' collapse.
    """
    # 1. Ensure symmetry
    sym_matrix = (corr_matrix + corr_matrix.T) / 2.0

    # 2. Eigendecomposition
    eigvals, eigvecs = np.linalg.eigh(sym_matrix)

    # 3. If already PD, return
    if np.all(eigvals >= tol):
        return sym_matrix

    # 4. Clip negative/zero eigenvalues
    eigvals[eigvals < tol] = tol

    # 5. Reconstruct
    pd_matrix = eigvecs @ np.diag(eigvals) @ eigvecs.T

    # 6. Re-normalize to be a correlation matrix (diagonal = 1)
    d = np.sqrt(np.diag(pd_matrix))
    pd_corr = pd_matrix / np.outer(d, d)

    # Force exact 1.0 on diagonal
    np.fill_diagonal(pd_corr, 1.0)

    return pd_corr

# -----------------------------------------------------------------------------
# MODULE 1: EBICglasso NETWORK (FULLY HARDENED – functional API)
# -----------------------------------------------------------------------------
def run_ebic_glasso_network(df, items, title_suffix="", min_complete=30):
    """
    Estimate a Gaussian Graphical Model using EBICglasso.
    - If complete‑case N >= min_complete, uses complete cases.
    - Otherwise, falls back to pairwise‑deletion correlation matrix
      projected to positive definite.
    """
    logging.info(f"--- Executing EBICglasso Network Analysis ({title_suffix}) ---")

    complete_df = df[items].dropna()
    N_complete = len(complete_df)
    logging.info(f"Complete‑case N = {N_complete} (out of {len(df)} total)")

    # ----- Determine data matrix and effective N -----
    if N_complete >= min_complete:
        # Complete‑case path
        data = complete_df.astype(float).values
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data)
        emp_corr = np.corrcoef(data_scaled, rowvar=False)
        N_eff = N_complete
        P = data.shape[1]
        items_retained = list(complete_df.columns)
        logging.info(f"Using complete‑case correlation (N={N_eff}, P={P}).")
    else:
        # Pairwise‑deletion path
        logging.info(f"Complete‑case N < {min_complete}; switching to pairwise‑deletion correlation.")
        emp_corr, ns_matrix = pairwise_correlation(df[items])

        # FORCE POSITIVE DEFINITE (Prevent GraphicalLasso Collapse)
        emp_corr = make_positive_definite(emp_corr)

        # Effective sample size: harmonic mean of off‑diagonal pairwise Ns
        off_diag_ns = ns_matrix[np.triu_indices_from(ns_matrix, k=1)]
        N_eff = harmonic_mean(off_diag_ns)
        if N_eff < 10:
            raise FatalScienceError("Insufficient pairwise observations (harmonic mean N < 10). Cannot estimate network.")
        P = emp_corr.shape[0]
        items_retained = list(df[items].columns)
        logging.info(f"Using projected pairwise correlation (effective N≈{N_eff:.0f}, P={P}).")

    # ----- EBICglasso alpha search (FUNCTIONAL API) -----
    alphas = np.logspace(-3, 0, 40)
    best_ebic = np.inf
    best_precision = None
    best_alpha = None

    for alpha in alphas:
        try:
            # Use the functional API which exactly accepts a precomputed covariance/correlation matrix
            cov, prec = graphical_lasso(emp_corr, alpha=alpha, max_iter=1000)

            sign, logdet = np.linalg.slogdet(prec)
            if not np.isfinite(logdet) or sign <= 0:
                continue

            trace = np.sum(emp_corr * prec)
            off_diag = prec - np.diag(np.diag(prec))
            n_edges = np.count_nonzero(off_diag) / 2

            ebic = compute_ebic(logdet, trace, N_eff, P, n_edges, gamma=0.5)
            if ebic < best_ebic:
                best_ebic = ebic
                best_precision = prec
                best_alpha = alpha
        except Exception:
            continue

    if best_precision is None:
        raise FatalScienceError("EBICglasso failed to converge on any valid precision matrix.")

    logging.info(f"EBIC Optimization Complete. Min EBIC: {best_ebic:.2f} at Alpha: {best_alpha:.4f}")
    partial_corr = precision_to_partial_corr(best_precision)

    # ----- Build NetworkX graph (threshold 0.01) -----
    G = nx.Graph()
    G.add_nodes_from(items_retained)
    edges_added = 0
    P_actual = partial_corr.shape[0]
    for i in range(P_actual):
        for j in range(i + 1, P_actual):
            weight = partial_corr[i, j]
            if abs(weight) > 0.01:
                G.add_edge(items_retained[i], items_retained[j],
                           weight=abs(weight), sign=np.sign(weight))
                edges_added += 1

    logging.info(f"Network constructed with {edges_added} non‑zero edges.")
    if edges_added == 0:
        logging.warning("0 edges detected. Data may lack reliable conditional dependencies.")
        return None, None

    # Louvain community detection
    partition = community_louvain.best_partition(G, weight='weight', random_state=42)
    n_communities = len(set(partition.values()))
    logging.info(f"Louvain Community Detection identified {n_communities} clusters.")

    # Save community mapping
    comm_df = pd.DataFrame({
        'Node': list(partition.keys()),
        'Community': list(partition.values())
    })
    comm_path = os.path.join(TABLES_DIR, f"layer1_ggm_communities_{title_suffix}.csv")
    comm_df.to_csv(comm_path, index=False)

    # Visualization
    plt.figure(figsize=(14, 12))
    pos = nx.spring_layout(G, k=0.6, seed=42)
    cmap = plt.get_cmap('viridis')
    colors = [cmap(partition[node] / max(1, n_communities - 1)) for node in G.nodes()]
    edge_colors = ['green' if G[u][v]['sign'] > 0 else 'red' for u, v in G.edges()]
    edge_weights = [G[u][v]['weight'] * 10 for u, v in G.edges()]
    nx.draw_networkx_nodes(G, pos, node_size=500, node_color=colors, edgecolors='black', alpha=0.9)
    nx.draw_networkx_edges(G, pos, edge_color=edge_colors, width=edge_weights, alpha=0.5)
    font_size = 10 if P_actual <= 20 else 6
    nx.draw_networkx_labels(G, pos, font_size=font_size, font_family="sans-serif")
    plt.title(f"EBICglasso Network ({title_suffix})\nAlpha={best_alpha:.4f}, Edges={edges_added}, Clusters={n_communities}")
    plt.axis('off')
    fig_path = os.path.join(FIGURES_DIR, f"layer1_ggm_network_{title_suffix}.png")
    plt.savefig(fig_path, dpi=300, bbox_inches='tight')
    plt.close()
    logging.info(f"Network visualization saved to {fig_path}")
    return G, partition

# -----------------------------------------------------------------------------
# MODULE 2: TOPOLOGICAL DATA ANALYSIS (MAPPER)
# -----------------------------------------------------------------------------
def run_tda_mapper(df, items):
    logging.info("--- Executing Topological Data Analysis (Mapper) ---")
    complete_df = df[items].dropna()
    if len(complete_df) < 100:
        raise FatalScienceError("Too few complete cases for Mapper analysis.")
    X = complete_df.astype(float).values
    logging.info(f"Topological Space: {X.shape[0]} observations, {X.shape[1]} dimensions.")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    mapper = km.KeplerMapper(verbose=0)
    pca = PCA(n_components=2, random_state=42)
    projected_data = mapper.fit_transform(X_scaled, projection=pca)

    cover = km.Cover(n_cubes=15, perc_overlap=0.4)
    clusterer = DBSCAN(eps=2.0, min_samples=10)

    try:
        graph = mapper.map(projected_data, X_scaled, cover=cover, clusterer=clusterer)
        html_path = os.path.join(FIGURES_DIR, "layer1_tda_mapper.html")
        mapper.visualize(
            graph,
            path_html=html_path,
            title="DT3 Topological Data Analysis (Mapper)",
            custom_tooltips=np.array([f"Obs: {i}" for i in range(X.shape[0])])
        )
        logging.info(f"TDA Mapper topology saved to {html_path}")
    except Exception as e:
        logging.error(f"Topological mapping failed: {e}")
        raise FatalScienceError("TDA Mapper encountered a singularity or collapse.")

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.info("===============================================================")
    logging.info(" DT³ PHASE 3 (REMEDIATED v4): Layer 1 - Unsupervised Structural")
    logging.info("===============================================================")

    master_path = os.path.join(PROCESSED_DIR, "dt3_master_dataset.csv")
    if not os.path.exists(master_path):
        logging.fatal("Processed CSV file not found. Run Phase 1 first.")
        sys.exit(1)

    logging.info(f"Cryptographic Hash (Master): {hash_file(master_path)}")
    df_master = pd.read_csv(master_path, low_memory=False)

    try:
        # 1. GGM on core DTDD items only
        run_ebic_glasso_network(df_master, CORE_DTDD, title_suffix="DTDD_Only")

        # 2. GGM on full item space (DTDD + BFI + TEQ + RSES items, excluding composites)
        full_items = [c for c in df_master.columns
                      if any(c.startswith(p) for p in ['DTDD_', 'BFI_', 'TEQ_', 'RSES_'])
                      and not c.endswith(('sum', 'Total'))]
        if len(full_items) > len(CORE_DTDD):
            run_ebic_glasso_network(df_master, full_items, title_suffix="Full_Item_Space")

        # 3. Topological Data Analysis
        run_tda_mapper(df_master, CORE_DTDD)

        logging.info("=== PHASE 3 EXECUTION SUCCESSFULLY COMPLETED ===")
    except FatalScienceError as e:
        logging.fatal(f"PIPELINE HALTED: {e}")
        sys.exit(1)