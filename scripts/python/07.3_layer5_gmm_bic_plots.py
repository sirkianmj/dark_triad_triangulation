#!/usr/bin/env python3
"""Phase 7.3 (additive, reviewer item 9b): GMM BIC elbow plots per trait."""
import os, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

TABLES, FIGURES = "results/tables", "results/figures"
os.makedirs(FIGURES, exist_ok=True)

df = pd.read_csv(f"{TABLES}/layer5_person_centered_bic.csv")
traits = ['Machiavellianism', 'Psychopathy', 'Narcissism']
fig, axes = plt.subplots(1, 3, figsize=(13, 4))
for ax, trait in zip(axes, traits):
    sub = df[df.Trait == trait].sort_values('N_Components')
    ax.plot(sub.N_Components, sub.BIC, marker='o', linewidth=2,
            markersize=8, color='#2a6bb0')
    best_n = int(sub.loc[sub.BIC.idxmin(), 'N_Components'])
    best_bic = float(sub.loc[sub.BIC.idxmin(), 'BIC'])
    ax.scatter([best_n], [best_bic], s=200, marker='*',
               color='red', zorder=5, label=f'min BIC at k={best_n}')
    ax.set_xlabel('Number of GMM components'); ax.set_ylabel('BIC')
    ax.set_title(trait, fontweight='bold'); ax.grid(alpha=0.3)
    ax.legend(fontsize=9)
plt.tight_layout()
plt.savefig(f"{FIGURES}/layer5_gmm_bic_curves.pdf", bbox_inches='tight')
plt.savefig(f"{FIGURES}/layer5_gmm_bic_curves.png", dpi=300, bbox_inches='tight')
plt.close()
print(f"Wrote {FIGURES}/layer5_gmm_bic_curves.{{pdf,png}}")
print(df.groupby('Trait').apply(lambda d: d.loc[d.BIC.idxmin(), 'N_Components']).to_string())
