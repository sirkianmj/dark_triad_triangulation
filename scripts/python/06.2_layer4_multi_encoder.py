#!/usr/bin/env python3
"""
Phase 6.2 (additive, reviewer item 7): Multi-encoder semantic clustering.
Runs 3 sentence encoders on the same 12 English items, compares ARI.
SAFETY: writes only layer4b_*.csv. Does not overwrite layer4_* originals.
"""
import os, sys, logging
import numpy as np, pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sentence_transformers import SentenceTransformer

TABLES = "results/tables"
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(os.path.join(TABLES,"execution_audit.log"),mode='a'),
              logging.StreamHandler(sys.stdout)], force=True)

DTDD = {
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
    'DTDD_4n': 'I tend to expect special favors from others.',
}
KEYS = list(DTDD.keys()); TEXTS = list(DTDD.values())
THEO = ['Machiavellianism']*4 + ['Psychopathy']*4 + ['Narcissism']*4
LABEL = {'Machiavellianism':0,'Psychopathy':1,'Narcissism':2}
TRUE_NUM = np.array([LABEL[t] for t in THEO])

ENCODERS = [
    'all-MiniLM-L6-v2',         # baseline
    'all-mpnet-base-v2',        # heavier, 768-d
    'BAAI/bge-small-en-v1.5',   # modern retrieval-optimized
]

def main():
    logging.info("="*63)
    logging.info(" PHASE 6.2: Multi-encoder semantic clustering")
    logging.info("="*63)
    rows = []
    crosstab_rows = []
    for enc_name in ENCODERS:
        logging.info(f"=== {enc_name} ===")
        try:
            enc = SentenceTransformer(enc_name)
        except Exception as e:
            logging.error(f"  Load failed: {e}")
            rows.append({'Encoder': enc_name, 'ARI': None, 'Silhouette': None,
                         'Purity_Mach': None, 'Purity_Psy': None, 'Purity_Narc': None,
                         'Error': str(e)[:80]})
            continue
        emb = enc.encode(TEXTS, show_progress_bar=False)
        clu = AgglomerativeClustering(n_clusters=3, metric='cosine', linkage='average')
        pred = clu.fit_predict(emb)
        ari = adjusted_rand_score(TRUE_NUM, pred)
        sil = silhouette_score(emb, pred, metric='cosine')
        # Purity per trait
        pur = {}
        for trait, label in LABEL.items():
            mask = TRUE_NUM == label
            sub_pred = pred[mask]
            from collections import Counter
            c = Counter(sub_pred)
            pur[trait] = c.most_common(1)[0][1] / len(sub_pred)
            crosstab_rows.append({
                'Encoder': enc_name, 'Theoretical_Trait': trait,
                'Cluster_0': int((sub_pred == 0).sum()),
                'Cluster_1': int((sub_pred == 1).sum()),
                'Cluster_2': int((sub_pred == 2).sum()),
                'Purity': round(pur[trait], 3),
            })
        rows.append({
            'Encoder': enc_name, 'ARI': round(float(ari), 4),
            'Silhouette': round(float(sil), 4),
            'Purity_Mach': round(pur['Machiavellianism'], 3),
            'Purity_Psy': round(pur['Psychopathy'], 3),
            'Purity_Narc': round(pur['Narcissism'], 3),
            'Error': '',
        })
        logging.info(f"  ARI={ari:.4f}  Sil={sil:.4f}  "
                     f"Purity: {pur['Machiavellianism']:.2f}/"
                     f"{pur['Psychopathy']:.2f}/{pur['Narcissism']:.2f}")

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(TABLES, "layer4b_multi_encoder.csv"), index=False)
    pd.DataFrame(crosstab_rows).to_csv(
        os.path.join(TABLES, "layer4b_multi_encoder_crosstab.csv"), index=False)

    print("\n" + "="*63)
    print(" MULTI-ENCODER SEMANTIC CLUSTERING")
    print("="*63)
    print(f"{'Encoder':26s} {'ARI':>7s} {'Sil':>7s} {'Mach':>6s} {'Psy':>6s} {'Narc':>6s}")
    for r in rows:
        if r.get('Error'):
            print(f"{r['Encoder']:26s}  ERROR: {r['Error']}")
        else:
            print(f"{r['Encoder']:26s} {r['ARI']:7.4f} {r['Silhouette']:7.4f} "
                  f"{r['Purity_Mach']:6.2f} {r['Purity_Psy']:6.2f} {r['Purity_Narc']:6.2f}")
    print("="*63)
    ari_vals = [r['ARI'] for r in rows if r['ARI'] is not None]
    if len(ari_vals) >= 2:
        print(f"  ARI range across encoders: {min(ari_vals):.3f} – {max(ari_vals):.3f}")
        narc_purities = [r['Purity_Narc'] for r in rows
                         if r['Purity_Narc'] is not None and not r.get('Error')]
        print(f"  Narcissism purity range: {min(narc_purities):.2f} – {max(narc_purities):.2f}")
        if max(ari_vals) - min(ari_vals) <= 0.15:
            print("  → ARI stable across encoders (Δ≤.15); the semantic clustering")
            print("    structure is encoder-robust.")
        else:
            print("  → ARI varies notably across encoders (Δ>.15); 'Narcissism Fracture'")
            print("    should be framed as encoder-dependent, not universal.")
    print("="*63)
    print("  Note: Czech translations were not tested (not available in repo).")
    print("  This is now reported as a limitation of Layer 4.")

if __name__ == "__main__":
    main()
