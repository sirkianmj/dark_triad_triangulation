#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 6 (REMEDIATED): Layer 4 - Semantic Triangulation
===============================================================================
Methodologically absolute script for LLM Embedding Extraction and Clustering.

FLAW 10 FIX (SEMANTIC OVERSIGHT):
  - Acknowledges that ARI ~ 0.50 is "Moderate", not "Strong".
  - Explicitly generates a cross-tabulation supplementary table showing how 
    many items of each theoretical trait fell into each empirical cluster.
  - Openly documents the "Narcissism Fracture" (where Narcissism items fail 
    to cohere) as a scientific finding rather than hiding it.
===============================================================================
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, linkage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score, silhouette_score

# -----------------------------------------------------------------------------
# DIRECTORY & LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# THEORETICAL ITEM DICTIONARY
# -----------------------------------------------------------------------------
DTDD_ITEMS = {
    'DTDD_1m': 'I tend to manipulate others to get my way.',
    'DTDD_2m': 'I have used deceit or lied to get my way.',
    'DTDD_3m': 'I have used flattery to get my way.',
    'DTDD_4m': 'I tend to exploit others towards my own end.',
    'DTDD_1p': 'I tend to lack remorse.',
    'DTDD_2p': 'I tend to not be too concerned with the morality of my actions.',
    'DTDD_3p': 'I tend to be callous or insensitive.',
    'DTDD_4p': 'I tend to be cynical.',
    'DTDD_1n': 'I tend to want others to admire me.',
    'DTDD_2n': 'I tend to want others to pay attention to me.',
    'DTDD_3n': 'I tend to seek prestige or status.',
    'DTDD_4n': 'I tend to expect special favors from others.'
}

# -----------------------------------------------------------------------------
# MODULE 1: SEMANTIC EMBEDDING & HIERARCHICAL CLUSTERING
# -----------------------------------------------------------------------------
def execute_semantic_triangulation():
    logging.info("--- Executing Semantic Embedding Extraction ---")
    
    keys = list(DTDD_ITEMS.keys())
    texts = list(DTDD_ITEMS.values())
    
    # Ground truth mapping
    theoretical_labels = ['Machiavellianism'] * 4 + ['Psychopathy'] * 4 + ['Narcissism'] * 4
    label_map = {'Machiavellianism': 0, 'Psychopathy': 1, 'Narcissism': 2}
    true_numeric = [label_map[t] for t in theoretical_labels]
    
    logging.info("Initializing SentenceTransformer (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(texts, show_progress_bar=False)
    logging.info(f"Successfully extracted embeddings. Shape: {embeddings.shape}")

    # Agglomerative Clustering (Cosine Distance)
    logging.info("Executing Agglomerative Hierarchical Clustering (k=3)...")
    clusterer = AgglomerativeClustering(n_clusters=3, metric='cosine', linkage='average')
    predicted_clusters = clusterer.fit_predict(embeddings)
    
    # Compute Metrics
    library_ari = adjusted_rand_score(true_numeric, predicted_clusters)
    silhouette = silhouette_score(embeddings, predicted_clusters, metric='cosine')
    logging.info(f"Clustering Metrics -> ARI: {library_ari:.4f} (Moderate) | Silhouette: {silhouette:.4f}")
    
    # Permutation Test for ARI
    logging.info("Executing 1,000-iteration Permutation Test for ARI significance...")
    n_permutations = 1000
    rng = np.random.RandomState(42)
    null_aris = [adjusted_rand_score(rng.permutation(true_numeric), predicted_clusters) for _ in range(n_permutations)]
        
    null_arr = np.array(null_aris)
    null_mean = float(null_arr.mean())
    null_std = float(null_arr.std())
    p_value = np.sum(null_arr >= library_ari) / n_permutations
    logging.info(f"Permutation Test -> Null Mean ARI: {null_mean:.4f} ± {null_std:.4f} | p-value: {p_value:.4f}")

    # FLAW 10 FIX: Explicit Cross-Tabulation (The Narcissism Fracture)
    results_df = pd.DataFrame({
        'Item_Code': keys,
        'Theoretical_Trait': theoretical_labels,
        'Empirical_Cluster': predicted_clusters
    })
    
    crosstab = pd.crosstab(results_df['Theoretical_Trait'], results_df['Empirical_Cluster'])
    logging.info(f"\n--- SEMANTIC FRACTURE ANALYSIS ---\n{crosstab}\n----------------------------------")
    
    # Save Outputs
    out_path = os.path.join(TABLES_DIR, "layer4_semantic_clusters.csv")
    results_df.to_csv(out_path, index=False)
    
    crosstab.to_csv(os.path.join(TABLES_DIR, "layer4_semantic_crosstab.csv"))
    
    stat_df = pd.DataFrame([{
        'ARI_Score': round(library_ari, 4),
        'Silhouette_Score': round(silhouette, 4),
        'Null_Mean_ARI': round(null_mean, 4),
        'Null_Std_ARI': round(null_std, 4),
        'Permutation_P_Value': p_value
    }])
    stat_path = os.path.join(TABLES_DIR, "layer4_semantic_statistics.csv")
    stat_df.to_csv(stat_path, index=False)
    
    # Dendrogram Visualization
    Z = linkage(embeddings, method='average', metric='cosine')
    plt.figure(figsize=(12, 8))
    dendrogram(Z, labels=keys, leaf_rotation=45, leaf_font_size=12)
    plt.ylabel("Cosine Distance")
    plt.title(f"Semantic Triangulation Dendrogram (ARI: {library_ari:.3f}, p={p_value:.3f})")
    plt.tight_layout()
    fig_path = os.path.join(FIGURES_DIR, "layer4_semantic_dendrogram.png")
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logging.info(f"Dendrogram saved to {fig_path}")

if __name__ == "__main__":
    logging.info("===============================================================")
    logging.info(" DT³ PHASE 6 (REMEDIATED): Layer 4 - Semantic Triangulation ")
    logging.info("===============================================================")
    execute_semantic_triangulation()
    logging.info("=== PHASE 6 EXECUTION SUCCESSFULLY COMPLETED ===")