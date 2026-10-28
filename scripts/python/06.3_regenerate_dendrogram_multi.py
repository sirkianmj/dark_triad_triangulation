#!/usr/bin/env python3
"""Phase 6.3: Regenerate Figure 3 as 3-panel multi-encoder dendrogram."""
import os, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.cluster.hierarchy import dendrogram, linkage
from sentence_transformers import SentenceTransformer

DTDD = {
    'DTDD_1m': 'manipulate others', 'DTDD_2m': 'used deceit or lied',
    'DTDD_3m': 'used flattery', 'DTDD_4m': 'exploit others',
    'DTDD_1p': 'lack remorse', 'DTDD_2p': 'not concerned with morality',
    'DTDD_3p': 'callous or insensitive', 'DTDD_4p': 'cynical',
    'DTDD_1n': 'want others to admire me', 'DTDD_2n': 'want others to pay attention',
    'DTDD_3n': 'seek prestige or status', 'DTDD_4n': 'expect special favors',
}
KEYS = list(DTDD.keys()); TEXTS = list(DTDD.values())
ENCODERS = ['all-MiniLM-L6-v2', 'all-mpnet-base-v2', 'BAAI/bge-small-en-v1.5']

fig, axes = plt.subplots(1, 3, figsize=(18, 6))
for ax, enc_name in zip(axes, ENCODERS):
    enc = SentenceTransformer(enc_name)
    emb = enc.encode(TEXTS, show_progress_bar=False)
    Z = linkage(emb, method='average', metric='cosine')
    dendrogram(Z, labels=KEYS, leaf_rotation=60, leaf_font_size=9, ax=ax)
    ax.set_title(enc_name, fontweight='bold', fontsize=11)
    ax.set_ylabel('Cosine distance')
plt.suptitle('DTDD semantic clustering across three sentence encoders — '
             'which trait fractures varies by encoder', fontsize=12, y=1.02)
plt.tight_layout()
plt.savefig("results/figures/layer4_semantic_dendrogram_multi.pdf", bbox_inches='tight')
plt.savefig("results/figures/layer4_semantic_dendrogram_multi.png", dpi=300, bbox_inches='tight')
plt.close()
print("Wrote results/figures/layer4_semantic_dendrogram_multi.{pdf,png}")
