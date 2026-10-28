#!/usr/bin/env python3
"""
Phase 2.4 (additive, reviewer item 1): Bifactor-(S-1) and Bifactor-(S.I-1)
Resolves the orthogonal-bifactor factor-collapse anomaly documented by
Knitter et al. (2025) and Eid et al. (2017).

SAFETY: writes only baseline_09_* and baseline_10_* CSVs. Does not modify
baseline_06 or baseline_07 (symmetric orthogonal bifactor).
"""
import os, sys, logging, warnings
import numpy as np, pandas as pd
from semopy import Model, calc_stats
warnings.filterwarnings('ignore')

PROCESSED, TABLES = "data/processed", "results/tables"
os.makedirs(TABLES, exist_ok=True)
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(os.path.join(TABLES,"execution_audit.log"),mode='a'),
              logging.StreamHandler(sys.stdout)], force=True)

M = ["DTDD_1m","DTDD_2m","DTDD_3m","DTDD_4m"]
P = ["DTDD_1p","DTDD_2p","DTDD_3p","DTDD_4p"]
N = ["DTDD_1n","DTDD_2n","DTDD_3n","DTDD_4n"]
ALL = M + P + N

# Bifactor-(S-1): Machiavellianism items load on D only (reference domain)
SPEC_S1 = f"""
D =~ {' + '.join(ALL)}
Ps =~ {' + '.join(P)}
Ns =~ {' + '.join(N)}
D ~~ 0*Ps
D ~~ 0*Ns
Ps ~~ Ns
"""

# Bifactor-(S.I-1): DTDD_4m is reference item (loads on D only, not on Ms)
SPEC_SI1 = f"""
D =~ {' + '.join(ALL)}
Ms =~ DTDD_1m + DTDD_2m + DTDD_3m
Ps =~ {' + '.join(P)}
Ns =~ {' + '.join(N)}
D ~~ 0*Ms
D ~~ 0*Ps
D ~~ 0*Ns
Ms ~~ 0*Ps
Ms ~~ 0*Ns
Ps ~~ Ns
"""

def extract(mod):
    par = mod.inspect()
    col = 'Estimate' if 'Estimate' in par.columns else 'Est.'
    def g(op, lval, rval):
        m = (par['op']==op) & (par['lval']==lval) & (par['rval']==rval)
        return float(par.loc[m, col].iloc[0]) if m.any() else 0.0
    def get_v(f):  # factor variance
        v = g('~~', f, f); return v if v > 0 else 1.0
    return par, col, g, get_v

def standardize(g, get_v, factor_items, factor_names):
    """Return dict {(item, factor): std_loading}."""
    var_f = {f: get_v(f) for f in factor_names}
    std = {}
    for it in ALL:
        # Raw loadings on every factor this item loads on
        raw = {f: g('~', it, f) for f in factor_names}
        resid = g('~~', it, it)
        # Total variance of item
        tot = sum((raw[f]**2) * var_f[f] for f in factor_names if f in raw) + resid
        if tot <= 0: continue
        for f in factor_names:
            if raw[f] != 0:
                std[(it, f)] = raw[f] * np.sqrt(var_f[f]) / np.sqrt(tot)
    return std

def omega_H(std, factor_names):
    sum_lD = sum(std.get((it, 'D'), 0.0) for it in ALL)
    spec_sum_sq = sum(sum(std.get((it, f), 0.0) for it in ALL)**2
                      for f in factor_names if f != 'D')
    theta = sum(1 - std.get((it,'D'),0.0)**2 -
                    sum(std.get((it,f),0.0)**2 for f in factor_names if f != 'D')
                for it in ALL)
    return (sum_lD**2) / (sum_lD**2 + spec_sum_sq + theta)

def omega_HS(std, factor_name, items):
    num = sum(std.get((it, factor_name), 0.0) for it in items)**2
    den = (num
           + sum(std.get((it, 'D'), 0.0) for it in items)**2
           + sum(1 - std.get((it,'D'),0.0)**2 - std.get((it,factor_name),0.0)**2
                 for it in items))
    return num / den if den > 0 else float('nan')

def ecv(std, factor_names):
    lD2 = sum(std.get((it,'D'),0.0)**2 for it in ALL)
    lS2 = sum(std.get((it,f),0.0)**2 for f in factor_names if f!='D' for it in ALL)
    return lD2 / (lD2 + lS2) if (lD2 + lS2) > 0 else float('nan')

def H_factor(std, factor_name, items):
    loadings = [std.get((it, factor_name), 0.0) for it in items]
    denom = sum(l**2 / (1 - l**2) for l in loadings if abs(l) < 0.999)
    return 1 / (1 + 1/denom) if denom > 0 else float('nan')

def run(df, spec, label, factor_items, factor_names, out_stem):
    logging.info(f"=== {label} ===")
    try:
        mod = Model(spec); mod.fit(df)
    except Exception as e:
        logging.error(f"FIT FAILED: {e}"); return
    stats = calc_stats(mod)
    chi2 = float(stats['chi2'].iloc[0]); dof = int(stats['DoF'].iloc[0])
    cfi  = float(stats['CFI'].iloc[0]);  tli = float(stats['TLI'].iloc[0])
    rmsea = float(stats['RMSEA'].iloc[0])
    _, col, g, get_v = extract(mod)
    std = standardize(g, get_v, factor_items, factor_names)

    # Sanity: reject if any |λ|>1 (Heywood)
    if any(abs(v) > 1.0 for v in std.values()):
        logging.error(f"HEYWOOD CASES in {label}. NO CSV."); return

    idx = {
        'Model': label,
        'Chi_Square': round(chi2,2), 'Degrees_of_Freedom': dof,
        'CFI': round(cfi,3), 'TLI': round(tli,3), 'RMSEA': round(rmsea,3),
        'N': len(df),
        'ECV': round(ecv(std, factor_names), 3),
        'Omega_H': round(omega_H(std, factor_names), 3),
        'H_D': round(H_factor(std, 'D', ALL), 3),
    }
    for f in factor_names:
        if f == 'D': continue
        idx[f'Omega_HS_{f}'] = round(omega_HS(std, f, factor_items[f]), 3)
        idx[f'H_{f}'] = round(H_factor(std, f, factor_items[f]), 3)

    pd.DataFrame([idx]).to_csv(os.path.join(TABLES, f"{out_stem}_indices.csv"), index=False)
    rows = []
    for it in ALL:
        d = {'Item': it, 'D_loading': round(std.get((it,'D'), 0.0), 3)}
        for f in factor_names:
            if f != 'D' and (it, f) in std:
                d[f'{f}_loading'] = round(std[(it, f)], 3)
        rows.append(d)
    pd.DataFrame(rows).to_csv(os.path.join(TABLES, f"{out_stem}_loadings.csv"), index=False)
    logging.info(f"Wrote {out_stem}_indices.csv and _loadings.csv")
    return idx

def main():
    logging.info("="*63); logging.info(" PHASE 2.4: Bifactor-(S-1) and Bifactor-(S.I-1)"); logging.info("="*63)
    df = pd.read_csv(os.path.join(PROCESSED,"dt3_master_dataset.csv"), low_memory=False)
    s1 = df[df['sample_origin']=='sample_1_community'].dropna(subset=ALL).copy()
    s1[ALL] = s1[ALL].astype(float)
    logging.info(f"Community N = {len(s1)}")

    run(s1, SPEC_S1, "Bifactor-(S-1) [Mach reference]",
        {'Ps': P, 'Ns': N}, ['D','Ps','Ns'], "baseline_09_bifactor_S1")
    run(s1, SPEC_SI1, "Bifactor-(S.I-1) [DTDD_4m reference]",
        {'Ms': M[:3], 'Ps': P, 'Ns': N}, ['D','Ms','Ps','Ns'], "baseline_10_bifactor_SI1")

    # Comparison to symmetric orthogonal (baseline_06)
    try:
        old = pd.read_csv(os.path.join(TABLES, "baseline_06_bifactor_fit.csv")).iloc[0]
        print("\n" + "="*63)
        print(" COMPARISON TO SYMMETRIC ORTHOGONAL (baseline_06)")
        print("="*63)
        print(f"  Symmetric orthogonal : CFI={old['CFI']:.3f}  RMSEA={old['RMSEA']:.3f}  "
              f"ωH={old['Omega_H']:.3f}  ωHS(M/P/N)={old['Omega_HS_Ms']:.3f}/{old['Omega_HS_Ps']:.3f}/{old['Omega_HS_Ns']:.3f}")
        for f in ['baseline_09_bifactor_S1_indices','baseline_10_bifactor_SI1_indices']:
            p = os.path.join(TABLES, f + ".csv")
            if os.path.exists(p):
                r = pd.read_csv(p).iloc[0]
                hs = " / ".join(f"{c.split('_')[-1]}={r[c]:.3f}" for c in r.index if c.startswith('Omega_HS'))
                print(f"  {r['Model']:22s} : CFI={r['CFI']:.3f}  RMSEA={r['RMSEA']:.3f}  "
                      f"ωH={r['Omega_H']:.3f}  ωHS({hs})")
        print("="*63)
    except Exception as e:
        logging.warning(f"Comparison to baseline_06 failed: {e}")

if __name__ == "__main__":
    main()
