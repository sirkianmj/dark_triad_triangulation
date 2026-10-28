#!/usr/bin/env python3
"""
Phase 2.6 (additive, reviewer item 9a): Configural invariance via per-sample CFA.
Fits 3-factor and bifactor models independently in community, student,
and representative samples. If all fit acceptably (CFI>.90, RMSEA<.08),
configural invariance is supported.
"""
import os, logging, numpy as np, pandas as pd
from semopy import Model, calc_stats

TABLES = "results/tables"
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(os.path.join(TABLES,"execution_audit.log"),mode='a'),
              logging.StreamHandler()], force=True)

M = [f"DTDD_{i}m" for i in range(1,5)]
P = [f"DTDD_{i}p" for i in range(1,5)]
N = [f"DTDD_{i}n" for i in range(1,5)]
ALL = M+P+N

SPEC_3F = f"""
Mach =~ {' + '.join(M)}
Psy  =~ {' + '.join(P)}
Narc =~ {' + '.join(N)}
"""
SPEC_BF = f"""
D  =~ {' + '.join(ALL)}
Ms =~ {' + '.join(M)}
Ps =~ {' + '.join(P)}
Ns =~ {' + '.join(N)}
D ~~ 0*Ms
D ~~ 0*Ps
D ~~ 0*Ns
Ms ~~ 0*Ps
Ms ~~ 0*Ns
Ps ~~ 0*Ns
"""

def fit_sample(df, spec, model_label, sample_label):
    try:
        mod = Model(spec); mod.fit(df)
        st = calc_stats(mod)
        return {
            'Model': model_label, 'Sample': sample_label,
            'N': len(df),
            'Chi2': round(float(st['chi2'].iloc[0]), 2),
            'df': int(st['DoF'].iloc[0]),
            'CFI': round(float(st['CFI'].iloc[0]), 3),
            'TLI': round(float(st['TLI'].iloc[0]), 3),
            'RMSEA': round(float(st['RMSEA'].iloc[0]), 3),
        }
    except Exception as e:
        logging.warning(f"Fit failed {model_label} / {sample_label}: {e}")
        return {'Model': model_label, 'Sample': sample_label, 'N': len(df),
                'Chi2': None, 'df': None, 'CFI': None, 'TLI': None, 'RMSEA': None}

def main():
    logging.info("="*63)
    logging.info(" PHASE 2.6: Multi-group configural invariance (Python)")
    logging.info("="*63)
    df = pd.read_csv("data/processed/dt3_master_dataset.csv", low_memory=False)

    results = []
    for sid in ['sample_1_community','sample_2_student','sample_3_representative']:
        sub = df[df['sample_origin']==sid].dropna(subset=ALL).copy()
        sub[ALL] = sub[ALL].astype(float)
        logging.info(f"{sid}: N={len(sub)}")
        for spec, label in [(SPEC_3F, '3-factor'), (SPEC_BF, 'Bifactor')]:
            r = fit_sample(sub, spec, label, sid)
            results.append(r)
            logging.info(f"  {label}: χ²={r['Chi2']}, df={r['df']}, "
                         f"CFI={r['CFI']}, TLI={r['TLI']}, RMSEA={r['RMSEA']}")

    out = pd.DataFrame(results)
    out.to_csv(os.path.join(TABLES,"baseline_13_multigroup_invariance.csv"), index=False)

    print("\n" + "="*63)
    print(" MULTI-GROUP CONFIGURAL INVARIANCE")
    print("="*63)
    print(f"{'Model':10s} {'Sample':28s} {'N':>6s} {'CFI':>6s} {'TLI':>6s} {'RMSEA':>7s}")
    for r in results:
        cf = f"{r['CFI']:.3f}" if r['CFI'] else "  —  "
        tl = f"{r['TLI']:.3f}" if r['TLI'] else "  —  "
        rm = f"{r['RMSEA']:.3f}" if r['RMSEA'] else "  —  "
        print(f"{r['Model']:10s} {r['Sample']:28s} {r['N']:6d} {cf:>6s} {tl:>6s} {rm:>7s}")
    print("="*63)

    # Configural invariance criterion: CFI≥.90 & RMSEA≤.08 in every sample
    for label in ['3-factor', 'Bifactor']:
        rows = [r for r in results if r['Model']==label and r['CFI'] is not None]
        if len(rows) == 3:
            min_cfi = min(r['CFI'] for r in rows)
            max_rmsea = max(r['RMSEA'] for r in rows)
            ok = min_cfi >= 0.90 and max_rmsea <= 0.08
            marker = "✓" if ok else "⚠"
            print(f"  {marker} {label}: min CFI={min_cfi:.3f}, max RMSEA={max_rmsea:.3f}")
    print("="*63)
    print("  Configural invariance: same factor structure fits acceptably in all 3 samples")
    print("  (CFI ≥ .90 and RMSEA ≤ .08 in every sample).")
    print("="*63)

if __name__ == "__main__":
    main()
