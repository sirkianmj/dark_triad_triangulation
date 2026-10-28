#!/usr/bin/env python3
"""
Phase 7.2 (additive, reviewer item 8a): Signed SHAP Divergence Index.
Adds a directional metric to complement baseline_05_..._sdi (unsigned).
For each feature: signed_magnitude_j = mean(|SHAP_j|) * sign(mean(SHAP_j))
SAFETY: writes only layer5b_signed_sdi.csv.
"""
import os, sys, logging
import numpy as np, pandas as pd
import xgboost as xgb, shap
from sklearn.preprocessing import StandardScaler
from scipy.spatial.distance import cosine

PROCESSED, TABLES = "data/processed", "results/tables"
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(os.path.join(TABLES,"execution_audit.log"),mode='a'),
              logging.StreamHandler(sys.stdout)], force=True)

PREDS = ['BFI_A_sum','BFI_C_sum','BFI_E_sum','BFI_N_sum','BFI_O_sum','TEQ_sum','age']
TARGETS = ['score_Machiavellianism','score_Psychopathy','score_Narcissism']
ITEMS = [f"DTDD_{i}{s}" for s in 'mpn' for i in range(1,5)]

def load_split(df):
    tr = df[df['sample_origin']=='sample_1_community'].dropna(subset=PREDS+TARGETS).copy()
    te = df[df['sample_origin']=='sample_3_representative'].dropna(subset=PREDS+TARGETS).copy()
    sc = StandardScaler().fit(tr[PREDS].astype(float))
    Xtr = sc.transform(tr[PREDS].astype(float))
    Xte = sc.transform(te[PREDS].astype(float))
    return Xtr, te[PREDS].astype(float).values, te[TARGETS].values.astype(float), tr, Xte

def signed_shap_vec(shap_vals):
    """mean |shap| * sign(mean shap) — per feature."""
    mag = np.abs(shap_vals).mean(axis=0)
    direction = np.sign(shap_vals.mean(axis=0))
    direction[direction == 0] = 1.0
    return mag * direction

def pseudo_traits(dtdd, rng, n=3):
    n_s, p = dtdd.shape
    idx = rng.permutation(p)
    groups = np.array_split(idx, n)
    out = np.zeros((n_s, n))
    for g, cols in enumerate(groups):
        out[:, g] = dtdd[:, cols].sum(axis=1)
    return out

def main():
    logging.info("="*63); logging.info(" PHASE 7.2: Signed SHAP Divergence Index"); logging.info("="*63)
    df = pd.read_csv(os.path.join(PROCESSED,"dt3_master_dataset.csv"), low_memory=False)
    Xtr, Xte_raw, yte, tr_raw, Xte = load_split(df)
    ytr = tr_raw[TARGETS].values.astype(float)
    dtdd = tr_raw[ITEMS].astype(float).values

    # Observed SHAP vectors (signed and unsigned)
    obs_signed, obs_unsigned = [], []
    for i in range(3):
        m = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        m.fit(Xtr, ytr[:, i])
        sv = shap.TreeExplainer(m).shap_values(Xte)
        obs_signed.append(signed_shap_vec(sv))
        obs_unsigned.append(np.abs(sv).mean(axis=0))

    def mean_cos(vectors):
        return float(np.mean([cosine(vectors[i], vectors[j])
                              for i in range(3) for j in range(i+1, 3)]))

    sdi_unsigned = mean_cos(obs_unsigned)
    sdi_signed = mean_cos(obs_signed)
    logging.info(f"Observed unsigned SDI: {sdi_unsigned:.4f}   signed SDI: {sdi_signed:.4f}")

    # Null: pseudo-traits, both metrics
    rng = np.random.RandomState(42)
    null_u, null_s = [], []
    for perm in range(500):
        py = pseudo_traits(dtdd, rng, n=3)
        vec_u, vec_s = [], []
        for k in range(3):
            m = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05,
                                 random_state=perm)
            m.fit(Xtr, py[:, k])
            sv = shap.TreeExplainer(m).shap_values(Xte)
            vec_u.append(np.abs(sv).mean(axis=0))
            vec_s.append(signed_shap_vec(sv))
        null_u.append(mean_cos(vec_u))
        null_s.append(mean_cos(vec_s))
        if (perm+1) % 100 == 0:
            logging.info(f"  null {perm+1}/500")
    null_u, null_s = np.array(null_u), np.array(null_s)

    res = pd.DataFrame([{
        'Observed_SDI_Unsigned': round(sdi_unsigned, 4),
        'Observed_SDI_Signed':   round(sdi_signed, 4),
        'Null_Mean_Unsigned':    round(float(null_u.mean()), 4),
        'Null_Std_Unsigned':     round(float(null_u.std()), 4),
        'Null_Mean_Signed':      round(float(null_s.mean()), 4),
        'Null_Std_Signed':       round(float(null_s.std()), 4),
        'P_Unsigned':            round(float((null_u >= sdi_unsigned).mean()), 4),
        'P_Signed':              round(float((null_s >= sdi_signed).mean()), 4),
    }])
    out = os.path.join(TABLES, "layer5b_signed_sdi.csv")
    res.to_csv(out, index=False)
    logging.info(f"Wrote {out}")

    print("\n" + "="*63); print(" SIGNED vs UNSIGNED SDI"); print("="*63)
    print(f"  Unsigned SDI: obs={sdi_unsigned:.4f}  null={null_u.mean():.4f}±{null_u.std():.4f}  p={(null_u>=sdi_unsigned).mean():.4f}")
    print(f"  Signed   SDI: obs={sdi_signed:.4f}  null={null_s.mean():.4f}±{null_s.std():.4f}  p={(null_s>=sdi_signed).mean():.4f}")
    print("="*63)

if __name__ == "__main__":
    main()
