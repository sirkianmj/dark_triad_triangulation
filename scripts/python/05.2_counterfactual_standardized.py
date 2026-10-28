#!/usr/bin/env python3
"""
Phase 5.2 (additive, reviewer item 6): z-standardized counterfactual analysis.
Reports (i) the original % flipped and (ii) the median z-shift required to flip,
plus a compression factor = SD(predictions)/SD(actual y).
SAFETY: writes only layer3b_*.csv. Does not overwrite layer3_counterfactual_*.
"""
import os, sys, logging
import numpy as np, pandas as pd
import xgboost as xgb
from sklearn.preprocessing import StandardScaler

PROCESSED, TABLES = "data/processed", "results/tables"
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(os.path.join(TABLES,"execution_audit.log"),mode='a'),
              logging.StreamHandler(sys.stdout)], force=True)

PREDS = ['BFI_A_sum','BFI_C_sum','BFI_E_sum','BFI_N_sum','BFI_O_sum','TEQ_sum','age']
TARGETS = ['score_Machiavellianism','score_Psychopathy','score_Narcissism']
IMMUTABLE = ['age']

def minimal_shift(model, sample, preds, immutable, threshold):
    mod_idx = [i for i, p in enumerate(preds) if p not in immutable]
    shifts = np.linspace(-2.5, 2.5, 101)
    best_feat, best_mag = None, np.inf
    for fi in mod_idx:
        for s in shifts:
            p = sample.copy(); p[fi] += s
            if model.predict(p.reshape(1,-1))[0] <= threshold:
                if abs(s) < best_mag: best_mag = abs(s); best_feat = preds[fi]
                break
    return best_feat, best_mag

def main():
    logging.info("="*63)
    logging.info(" PHASE 5.2: Z-standardized counterfactual analysis")
    logging.info("="*63)
    df = pd.read_csv(os.path.join(PROCESSED,"dt3_master_dataset.csv"), low_memory=False)
    tr = df[df['sample_origin']=='sample_1_community'].dropna(subset=PREDS+TARGETS).copy()
    te = df[df['sample_origin']=='sample_3_representative'].dropna(subset=PREDS+TARGETS).copy()
    sc = StandardScaler().fit(tr[PREDS].astype(float))
    Xtr = sc.transform(tr[PREDS].astype(float)); Xte = sc.transform(te[PREDS].astype(float))
    ytr = tr[TARGETS].astype(float).values; yte = te[TARGETS].astype(float).values

    summary = []
    for i, t in enumerate(TARGETS):
        mdl = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        mdl.fit(Xtr, ytr[:, i])
        preds_te = mdl.predict(Xte)
        thr = np.median(yte[:, i])
        high_idx = np.where(yte[:, i] >= np.percentile(yte[:, i], 80))[0]

        # Compression factor
        comp = np.std(preds_te) / np.std(yte[:, i])
        # Flip analysis
        feats, mags = [], []
        for idx in high_idx:
            s = Xte[idx].copy()
            f, m = minimal_shift(mdl, s, PREDS, IMMUTABLE, thr)
            if f is not None:
                feats.append(f); mags.append(m)
        from collections import Counter
        counts = Counter(feats)
        top = counts.most_common(1)
        if top:
            primary = top[0][0]
            prop = counts[primary] / len(high_idx)
            mags_arr = np.array(mags)
            median_mag = float(np.median(mags_arr)) if len(mags_arr) else np.nan
            p25_mag = float(np.percentile(mags_arr, 25)) if len(mags_arr) else np.nan
        else:
            primary, prop, median_mag, p25_mag = 'none', 0.0, np.nan, np.nan

        summary.append({
            'Trait': t.replace('score_',''),
            'N_high': int(len(high_idx)),
            'Primary_driver': primary,
            'Pct_flipped': round(prop, 3),
            'Median_|z_shift|': round(median_mag, 3) if not np.isnan(median_mag) else None,
            'Q1_|z_shift|': round(p25_mag, 3) if not np.isnan(p25_mag) else None,
            'Compression_factor': round(float(comp), 3),
            'SD_pred': round(float(np.std(preds_te)), 3),
            'SD_y': round(float(np.std(yte[:, i])), 3),
        })
        logging.info(f"  [{t}] primary={primary} prop={prop:.3f} "
                     f"median|z|={median_mag:.3f} comp={comp:.3f}")

    out = pd.DataFrame(summary)
    path = os.path.join(TABLES, "layer3b_counterfactual_standardized.csv")
    out.to_csv(path, index=False)
    logging.info(f"Wrote {path}")

    print("\n" + "="*63)
    print(" Z-STANDARDIZED COUNTERFACTUAL ANALYSIS")
    print("="*63)
    print(f"{'Trait':20s} {'%flipped':>9s} {'med|z|':>8s} {'Q1|z|':>7s} {'comp':>7s}")
    for r in summary:
        print(f"{r['Trait']:20s} {r['Pct_flipped']*100:8.1f}% "
              f"{r['Median_|z_shift|']:8.3f} {r['Q1_|z_shift|']:7.3f} "
              f"{r['Compression_factor']:7.3f}")
    print("="*63)
    print("  Median |z| = median SD-shift needed to flip, conditional on flipping")
    print("  Compression = SD(predictions) / SD(actual y) — lower = more compressed")
    print("  If compression_factor and median |z| track together across traits,")
    print("  the flip-% artifact is confirmed and quantified.")
    print("="*63)

if __name__ == "__main__":
    main()
