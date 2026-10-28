#!/usr/bin/env python3
"""Phase 6.4 (Requirement 7 residual): Linkage-rule robustness for Layer 4.
Tests 3 encoders × 3 linkage methods (average / ward / complete) = 9 configs.
Appends results to layer4b_multi_encoder.csv (or writes new file)."""
import os, logging
import numpy as np, pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sentence_transformers import SentenceTransformer
from collections import Counter

TABLES = "results/tables"
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(os.path.join(TABLES,"execution_audit.log"),mode='a'),
              logging.StreamHandler()], force=True)

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
LABEL = {'Machiavellianism':0, 'Psychopathy':1, 'Narcissism':2}
TRUE_NUM = np.array([LABEL[t] for t in THEO])

ENCODERS = [
    'all-MiniLM-L6-v2',
    'all-mpnet-base-v2',
    'BAAI/bge-small-en-v1.5',
]
LINKAGE = ['average', 'ward', 'complete']

def purity_by_trait(pred, trait):
    mask = TRUE_NUM == LABEL[trait]
    c = Counter(pred[mask])
    return c.most_common(1)[0][1] / mask.sum()

def main():
    logging.info("="*63)
    logging.info(" PHASE 6.4: Linkage-rule robustness (Layer 4)")
    logging.info("="*63)
    rows = []
    for enc_name in ENCODERS:
        logging.info(f"=== {enc_name} ===")
        try:
            enc = SentenceTransformer(enc_name)
            emb = enc.encode(TEXTS, show_progress_bar=False)
        except Exception as e:
            logging.error(f"  encoder load failed: {e}")
            continue
        # L2-normalize so Euclidean Ward == cosine-geometry Ward on unit sphere
        emb_norm = emb / np.linalg.norm(emb, axis=1, keepdims=True)
        for linkage in LINKAGE:
            try:
                if linkage == 'ward':
                    clu = AgglomerativeClustering(n_clusters=3, metric='euclidean', linkage='ward')
                    pred = clu.fit_predict(emb_norm)
                    sil_metric = 'euclidean'
                    sil_X = emb_norm
                else:
                    clu = AgglomerativeClustering(n_clusters=3, metric='cosine', linkage=linkage)
                    pred = clu.fit_predict(emb)
                    sil_metric = 'cosine'
                    sil_X = emb
                ari = adjusted_rand_score(TRUE_NUM, pred)
                sil = silhouette_score(sil_X, pred, metric=sil_metric)
                pur_m = purity_by_trait(pred, 'Machiavellianism')
                pur_p = purity_by_trait(pred, 'Psychopathy')
                pur_n = purity_by_trait(pred, 'Narcissism')
                # Identify which trait fractures (lowest purity)
                purities = {'Mach': pur_m, 'Psy': pur_p, 'Narc': pur_n}
                fractured = min(purities, key=purities.get)
                rows.append({
                    'Encoder': enc_name,
                    'Linkage': linkage,
                    'ARI': round(float(ari), 4),
                    'Silhouette': round(float(sil), 4),
                    'Purity_Mach': round(pur_m, 3),
                    'Purity_Psy': round(pur_p, 3),
                    'Purity_Narc': round(pur_n, 3),
                    'Fractured_Trait': fractured,
                })
                logging.info(f"  {linkage:8s}: ARI={ari:.3f}  purities M/P/N={pur_m:.2f}/{pur_p:.2f}/{pur_n:.2f}  fractured={fractured}")
            except Exception as e:
                logging.error(f"  {linkage}: failed - {e}")
                rows.append({'Encoder': enc_name, 'Linkage': linkage, 'Error': str(e)[:60]})

    out = pd.DataFrame(rows)
    out_path = os.path.join(TABLES, "layer4c_linkage_robustness.csv")
    out.to_csv(out_path, index=False)
    logging.info(f"Wrote {out_path}")

    print("\n" + "="*90)
    print(" LINKAGE RULE ROBUSTNESS (3 encoders × 3 linkage rules)")
    print("="*90)
    print(f"{'Encoder':<24s} {'Linkage':<10s} {'ARI':>7s} {'Sil':>7s} {'Mach':>6s} {'Psy':>6s} {'Narc':>6s} {'Fractured':>10s}")
    for r in rows:
        if 'Error' in r:
            print(f"{r['Encoder']:<24s} {r['Linkage']:<10s}  ERROR")
        else:
            print(f"{r['Encoder']:<24s} {r['Linkage']:<10s} {r['ARI']:7.4f} {r['Silhouette']:7.4f} "
                  f"{r['Purity_Mach']:6.2f} {r['Purity_Psy']:6.2f} {r['Purity_Narc']:6.2f} {r['Fractured_Trait']:>10s}")
    print("="*90)

    # Summary: how often does each trait fracture across 9 configs?
    fracs = [r['Fractured_Trait'] for r in rows if 'Fractured_Trait' in r]
    if fracs:
        from collections import Counter
        c = Counter(fracs)
        print(f"  Fracture frequency across {len(fracs)} configurations:")
        for k, v in c.most_common():
            print(f"    {k}: {v}/{len(fracs)}")
    print("="*90)

if __name__ == "__main__":
    main()
