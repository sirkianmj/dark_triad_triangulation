import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score, silhouette_score
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import dendrogram, linkage

print("="*60)
print("  DT3 PROJECT: PHASE 6 - LAYER 4: LLM SEMANTIC TRIANGULATION  ")
print("="*60)

# Define Scale Item Literal Wording (12 DTDD items + Anchor Correlates)
item_dictionary = {
    # Machiavellianism Items (Target Cluster: Machiavellianism)
    'DTDD_1m': ('I tend to manipulate people to get what I want.', 'Machiavellianism'),
    'DTDD_2m': ('I have used deceit or lied to get what I want.', 'Machiavellianism'),
    'DTDD_3m': ('I have used flattery to get what I want.', 'Machiavellianism'),
    'DTDD_4m': ('I tend to exploit others towards my own end.', 'Machiavellianism'),
    
    # Psychopathy Items (Target Cluster: Psychopathy)
    'DTDD_1p': ('I tend to be unconcerned with the morality of my actions.', 'Psychopathy'),
    'DTDD_2p': ('I tend to be callous or insensitive to other peoples feelings.', 'Psychopathy'),
    'DTDD_3p': ('I tend to be cynical and skeptical of others.', 'Psychopathy'),
    'DTDD_4p': ('I tend to lack remorse or feel guilty for my mistakes.', 'Psychopathy'),
    
    # Narcissism Items (Target Cluster: Narcissism)
    'DTDD_1n': ('I tend to want others to admire me.', 'Narcissism'),
    'DTDD_2n': ('I tend to want others to pay attention to me.', 'Narcissism'),
    'DTDD_3n': ('I tend to seek prestige or status.', 'Narcissism'),
    'DTDD_4n': ('I tend to expect special favors from others.', 'Narcissism'),
    
    # Correlate Anchors
    'BFI_A_1': ('I see myself as someone who is helpful and unselfish with others.', 'Agreeableness'),
    'BFI_A_2': ('I see myself as someone who finds fault with others.', 'Agreeableness'),
    'BFI_C_1': ('I see myself as someone who does a thorough job.', 'Conscientiousness'),
    'BFI_N_1': ('I see myself as someone who depresses easily.', 'Neuroticism'),
    'TEQ_1'  : ('I feel compassionate toward people who are less fortunate than me.', 'Empathy'),
    'RSES_1' : ('I feel that I am a person of worth at least on an equal plane with others.', 'Self-Esteem')
}

item_keys = list(item_dictionary.keys())
sentences = [v[0] for v in item_dictionary.values()]
true_labels = [v[1] for v in item_dictionary.values()]

print(f"\n[1/3] Loaded literal text for {len(item_keys)} scale items.")

# 1. Generate Semantic Embeddings via Local LLM (all-MiniLM-L6-v2)
print("\n[2/3] Generating 384-dimensional semantic vector embeddings using all-MiniLM-L6-v2...")
embedder = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = embedder.encode(sentences, show_progress_bar=False)

print(f" -> Generated embeddings matrix shape: {embeddings.shape}")

# 2. Unsupervised Agglomerative Semantic Clustering on 12 DTDD items
dtdd_indices = [i for i, k in enumerate(item_keys) if k.startswith('DTDD_')]
dtdd_embeddings = embeddings[dtdd_indices]
dtdd_keys = [item_keys[i] for i in dtdd_indices]
dtdd_true_labels = [true_labels[i] for i in dtdd_indices]

print("\n[3/3] Performing Unsupervised Semantic Clustering on 12 DTDD Item Embeddings (K = 3)...")
clustering = AgglomerativeClustering(n_clusters=3, metric='cosine', linkage='average')
pred_clusters = clustering.fit_predict(dtdd_embeddings)

# Quantify Agreement with Theory using Adjusted Rand Index (ARI)
# Map true labels to numeric integers
label_map = {'Machiavellianism': 0, 'Psychopathy': 1, 'Narcissism': 2}
true_numeric = [label_map[l] for l in dtdd_true_labels]

ari_score = adjusted_rand_score(true_numeric, pred_clusters)
sil_score = silhouette_score(dtdd_embeddings, pred_clusters, metric='cosine')

print("\n" + "="*50)
print("  EMERGENT LLM SEMANTIC CLUSTERS (ZERO HUMAN RESPONSE DATA)  ")
print("="*50)

semantic_df = pd.DataFrame({
    'Item_Code': dtdd_keys,
    'True_Trait': dtdd_true_labels,
    'LLM_Semantic_Cluster': pred_clusters,
    'Literal_Text': [sentences[i] for i in dtdd_indices]
})

for c_id in sorted(set(pred_clusters)):
    cluster_items = semantic_df[semantic_df['LLM_Semantic_Cluster'] == c_id]
    item_list = cluster_items['Item_Code'].tolist()
    traits_contained = cluster_items['True_Trait'].tolist()
    print(f" LLM Cluster {c_id}: {item_list} -> Traits: {set(traits_contained)}")

print(f"\nAdjusted Rand Index (ARI) with Theoretical Traits: {ari_score:.4f}")
print(f"Semantic Silhouette Separation Score: {sil_score:.4f}")

# Save Results & Semantic Dendrogram Figure
os.makedirs('results/figures', exist_ok=True)
semantic_df.to_csv('results/semantic_item_embeddings_clusters.csv', index=False)

plt.figure(figsize=(10, 6))
Z = linkage(dtdd_embeddings, method='average', metric='cosine')
dendrogram(Z, labels=dtdd_keys, leaf_rotation=90)
plt.title("Layer 4: LLM Semantic Embedding Hierarchical Clustering Dendrogram", fontsize=12)
plt.ylabel("Cosine Semantic Distance")
plt.tight_layout()
fig_path = 'results/figures/layer4_semantic_dendrogram.png'
plt.savefig(fig_path, dpi=300)
plt.close()

print(f"\nSaved semantic dendrogram figure to '{fig_path}'")
print(f"Saved semantic cluster table to 'results/semantic_item_embeddings_clusters.csv'")
print("="*60)
