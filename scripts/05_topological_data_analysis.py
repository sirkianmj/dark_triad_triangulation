import os
import pandas as pd
import numpy as np
import kmapper as km
from sklearn.decomposition import PCA
from sklearn.cluster import DBSCAN

print("="*60)
print("  DT3 PROJECT: PHASE 3 - LAYER 1: TOPOLOGICAL DATA ANALYSIS (MAPPER) ")
print("="*60)

# Load master dataset
df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

# Select 12 DTDD item features
dtdd_cols = [f'DTDD_{i}{t}' for t in ['m', 'p', 'n'] for i in range(1, 5)]
data_df = df[dtdd_cols].dropna()

# Extract item matrix X and trait target vectors
X = data_df.values
trait_mach = df.loc[data_df.index, 'score_Machiavellianism'].values
trait_psy  = df.loc[data_df.index, 'score_Psychopathy'].values
trait_narc = df.loc[data_df.index, 'score_Narcissism'].values
trait_tot  = df.loc[data_df.index, 'score_DarkCore_Total'].values

print(f"\n[1/3] Prepared item matrix X: shape {X.shape} across N = {len(X)} respondents.")

# 1. Initialize Kepler Mapper
mapper = km.KeplerMapper(verbose=1)

# 2. Project Data onto 2D Lens using PCA
print("\n[2/3] Projecting psychological space onto 2D PCA Lens...")
lens = mapper.fit_transform(X, projection=PCA(n_components=2, random_state=42))

# 3. Create Topological Map
print("\n[3/3] Constructing Mapper Simplicial Complex (Cover = 10 intervals, Gain = 0.3, Clustering = DBSCAN)...")
graph = mapper.map(
    lens,
    X,
    cover=km.Cover(n_cubes=10, perc_overlap=0.3),
    clusterer=DBSCAN(eps=0.5, min_samples=5)
)

num_nodes = len(graph['nodes'])
num_edges = sum(len(v) for v in graph['links'].values()) // 2
print(f"\n -> Mapper Simplicial Complex created: {num_nodes} node clusters, {num_edges} topological edges.")

# Save HTML interactive visualization
os.makedirs('results/figures', exist_ok=True)
html_out = 'results/figures/layer1_mapper_topology.html'
mapper.visualize(
    graph,
    path_html=html_out,
    title="Layer 1: Topological Data Analysis (Psychological Space Shape)",
    custom_tooltips=trait_tot,
    color_values=trait_mach,
    color_function_name="Machiavellianism Intensity"
)

print(f"\nSaved interactive TDA Mapper graph to '{html_out}'")
print("="*60)
