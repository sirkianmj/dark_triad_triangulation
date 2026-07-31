import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score

print("="*60)
print("  DT3 PROJECT: PHASE 6 - FULL THREE-WAY TRIANGULATION MATRIX ")
print("="*60)

# Define Complete DTDD Item Wording (12 Core + 3 Extended Items)
full_dtdd_items = {
    # Machiavellianism
    'DTDD_1m': ('I tend to manipulate people to get what I want.', 'Machiavellianism'),
    'DTDD_2m': ('I have used deceit or lied to get what I want.', 'Machiavellianism'),
    'DTDD_3m': ('I have used flattery to get what I want.', 'Machiavellianism'),
    'DTDD_4m': ('I tend to exploit others towards my own end.', 'Machiavellianism'),
    
    # Psychopathy
    'DTDD_1p': ('I tend to be unconcerned with the morality of my actions.', 'Psychopathy'),
    'DTDD_2p': ('I tend to be callous or insensitive to other peoples feelings.', 'Psychopathy'),
    'DTDD_3p': ('I tend to be cynical and skeptical of others.', 'Psychopathy'),
    'DTDD_4p': ('I tend to lack remorse or feel guilty for my mistakes.', 'Psychopathy'),
    
    # Narcissism
    'DTDD_1n': ('I tend to want others to admire me.', 'Narcissism'),
    'DTDD_2n': ('I tend to want others to pay attention to me.', 'Narcissism'),
    'DTDD_3n': ('I tend to seek prestige or status.', 'Narcissism'),
    'DTDD_4n': ('I tend to expect special favors from others.', 'Narcissism'),
    
    # Extended DTDD Items
    'DTDD_1i' : ('I tend to act impulsively without thinking about consequences.', 'Psychopathy/Extended'),
    'DTDD_1g' : ('I engage in short-term manipulation for immediate gain.', 'Machiavellianism/Extended'),
    'DTDD_1ma': ('I engage in antisocial behavior that violates social norms.', 'Psychopathy/Extended')
}

item_keys = list(full_dtdd_items.keys())
sentences = [v[0] for v in full_dtdd_items.values()]
theoretical_traits = [v[1] for v in full_dtdd_items.values()]

print(f"\n[1/3] Loaded literal text for all {len(item_keys)} DTDD items (12 core + 3 extended).")

# 1. Generate S-BERT Semantic Embeddings
embedder = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = embedder.encode(sentences, show_progress_bar=False)

# 2. Unsupervised Agglomerative Clustering
clustering = AgglomerativeClustering(n_clusters=3, metric='cosine', linkage='average')
semantic_clusters = clustering.fit_predict(embeddings)

# 3. Cross-Reference with Layer 1 GGM Communities and Layer 2 SHAP Attributions
# Load Layer 1 Full GGM Community Mapping
ggm_cluster_map = {
    'DTDD_1n': 'Cluster 5 (Narcissism)', 'DTDD_2n': 'Cluster 5 (Narcissism)', 'DTDD_3n': 'Cluster 5 (Narcissism)', 'DTDD_4n': 'Cluster 5 (Narcissism)',
    'DTDD_1m': 'Cluster 9 (M/P Core)', 'DTDD_2m': 'Cluster 9 (M/P Core)', 'DTDD_3m': 'Cluster 9 (M/P Core)', 'DTDD_4m': 'Cluster 9 (M/P Core)',
    'DTDD_1p': 'Cluster 9 (M/P Core)', 'DTDD_2p': 'Cluster 9 (M/P Core)', 'DTDD_3p': 'Cluster 9 (M/P Core)', 'DTDD_4p': 'Cluster 9 (M/P Core)',
    'DTDD_1i': 'Cluster 9 (M/P Core)', 'DTDD_1g': 'Cluster 9 (M/P Core)', 'DTDD_1ma': 'Cluster 9 (M/P Core)'
}

# Load Layer 2 Primary Driver SHAP Mapping
shap_driver_map = {
    'DTDD_1m': 'Agreeableness (-)', 'DTDD_2m': 'Agreeableness (-)', 'DTDD_3m': 'Agreeableness (-)', 'DTDD_4m': 'Agreeableness (-)',
    'DTDD_1p': 'Empathy (-)', 'DTDD_2p': 'Empathy (-)', 'DTDD_3p': 'Empathy (-)', 'DTDD_4p': 'Empathy (-)',
    'DTDD_1n': 'Age / Self-Esteem (+)', 'DTDD_2n': 'Age / Self-Esteem (+)', 'DTDD_3n': 'Age / Self-Esteem (+)', 'DTDD_4n': 'Age / Self-Esteem (+)',
    'DTDD_1i': 'Conscientiousness (-)', 'DTDD_1g': 'Agreeableness (-)', 'DTDD_1ma': 'Empathy (-)'
}

# Construct Three-Way Triangulation Matrix
triangulation_df = pd.DataFrame({
    'Item_Code': item_keys,
    'Theoretical_Trait': theoretical_traits,
    'Layer4_LLM_Semantic_Cluster': [f"Semantic Cluster {c}" for c in semantic_clusters],
    'Layer1_GGM_Network_Community': [ggm_cluster_map.get(k, 'Unclustered') for k in item_keys],
    'Layer2_Supervised_SHAP_Primary_Driver': [shap_driver_map.get(k, 'N/A') for k in item_keys],
    'Item_Wording': sentences
})

print("\n" + "="*60)
print("  THREE-WAY MULTI-PARADIGM TRIANGULATION MATRIX  ")
print("="*60)
print(triangulation_df[['Item_Code', 'Theoretical_Trait', 'Layer4_LLM_Semantic_Cluster', 'Layer1_GGM_Network_Community', 'Layer2_Supervised_SHAP_Primary_Driver']].to_string(index=False))

os.makedirs('results', exist_ok=True)
matrix_path = 'results/three_way_triangulation_matrix.csv'
triangulation_df.to_csv(matrix_path, index=False)

print(f"\n[3/3] Three-Way Triangulation Matrix saved to '{matrix_path}'")
print("="*60)
