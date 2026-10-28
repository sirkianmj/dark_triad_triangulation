#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 2.3 (ADDITIVE): CFA — 2-factor model merging Machiavellianism + Narcissism
===============================================================================
SAFETY CONTRACT:
  - Reads only data/processed/dt3_master_dataset.csv
  - Writes only baseline_08_cfa_2factor_mach_narc.csv
  - Does NOT modify existing pipeline scripts or CSVs
  - Uses the exact same community sample and preprocessing as baseline_04
  - Provides the missing 2-factor comparison for the §4.3 Discussion claim

Model:
  MN =~ Machiavellianism items + Narcissism items   (merged factor)
  Psy =~ Psychopathy items                          (separate factor)

Comparison target (already committed in baseline_04):
  3-factor:        chi2=1838.65, df=51, CFI=.941, TLI=.923, RMSEA=.077
  2-factor M+P:    chi2=4589.6,  df=53, CFI=.849, TLI=.812, RMSEA=.120
===============================================================================
"""
import os, sys, logging
import numpy as np
import pandas as pd
from semopy import Model, calc_stats

PROCESSED = "data/processed"
TABLES    = "results/tables"
os.makedirs(TABLES, exist_ok=True)
log_path  = os.path.join(TABLES, "execution_audit.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(log_path, mode='a'),
              logging.StreamHandler(sys.stdout)],
    force=True
)

M_ITEMS = ["DTDD_1m","DTDD_2m","DTDD_3m","DTDD_4m"]
P_ITEMS = ["DTDD_1p","DTDD_2p","DTDD_3p","DTDD_4p"]
N_ITEMS = ["DTDD_1n","DTDD_2n","DTDD_3n","DTDD_4n"]
ALL_ITEMS = M_ITEMS + P_ITEMS + N_ITEMS

SPEC = f"""
MN  =~ {' + '.join(M_ITEMS + N_ITEMS)}
Psy =~ {' + '.join(P_ITEMS)}
"""

def main():
    logging.info("="*63)
    logging.info(" DT³ PHASE 2.3 (ADDITIVE): 2-factor CFA (Mach+Narc merged)")
    logging.info("="*63)

    master = os.path.join(PROCESSED, "dt3_master_dataset.csv")
    if not os.path.exists(master):
        logging.fatal(f"Master dataset not found: {master}")
        sys.exit(1)
    df = pd.read_csv(master, low_memory=False)

    # Same sample as baseline_04 (community, listwise on 12 items)
    s1 = df[df["sample_origin"] == "sample_1_community"].copy()
    s1 = s1.dropna(subset=ALL_ITEMS)
    s1[ALL_ITEMS] = s1[ALL_ITEMS].astype(float)
    logging.info(f"Community sample N = {len(s1)} (matches baseline_04 CFA N)")

    try:
        mod = Model(SPEC)
        mod.fit(s1)
    except Exception as e:
        logging.error(f"FIT FAILED: {e}")
        logging.error("Model did not converge. NO CSV WILL BE WRITTEN.")
        sys.exit(2)

    stats = calc_stats(mod)
    chi2 = float(stats["chi2"].iloc[0])
    dof  = int(stats["DoF"].iloc[0])
    cfi  = float(stats["CFI"].iloc[0])
    tli  = float(stats["TLI"].iloc[0])
    rmsea= float(stats["RMSEA"].iloc[0])

    # Sanity checks
    if not (0 <= cfi <= 1 and 0 <= tli <= 1 and rmsea >= 0):
        logging.error(f"Fit indices out of range (CFI={cfi}, TLI={tli}, RMSEA={rmsea}). "
                      f"NO CSV.")
        sys.exit(3)
    if dof != 53:
        logging.warning(f"Expected df=53 (as in the M+P merge), got df={dof}. "
                        f"Investigate before interpreting.")

    # Write CSV
    out_df = pd.DataFrame([{
        "Model": "2-Factor (Mach.+Narc. merged)",
        "Chi_Square": round(chi2, 2),
        "Degrees_of_Freedom": dof,
        "CFI": round(cfi, 3),
        "TLI": round(tli, 3),
        "RMSEA": round(rmsea, 3),
        "N": len(s1),
    }])
    out_path = os.path.join(TABLES, "baseline_08_cfa_2factor_mach_narc.csv")
    out_df.to_csv(out_path, index=False)
    logging.info(f"Wrote {out_path}")

    # Comparison summary
    print("\n" + "="*63)
    print(" 2-FACTOR CFA (Mach.+Narc. merged) RESULT")
    print("="*63)
    print(f"  chi2({dof}) = {chi2:.2f}   CFI = {cfi:.3f}   TLI = {tli:.3f}   RMSEA = {rmsea:.3f}")
    print(f"  N = {len(s1)}")
    print("="*63)
    print(" Comparison:")
    print("   3-factor:             CFI=.941  TLI=.923  RMSEA=.077  <-- best")
    print("   2-factor M+P merge:   CFI=.849  TLI=.812  RMSEA=.120")
    print(f"   2-factor M+N merge:   CFI={cfi:.3f}  TLI={tli:.3f}  RMSEA={rmsea:.3f}  <-- new")
    print("="*63)
    if cfi < 0.941 - 0.01:
        print(" INTERPRETATION: M+N merge is WORSE than 3-factor.")
        print(" -> Supports §4.3: Narcissism Fracture is semantic/predictive, NOT latent.")
    elif cfi > 0.941 + 0.01:
        print(" INTERPRETATION: M+N merge is BETTER than 3-factor.")
        print(" -> CONTRADICTS §4.3: the Narcissism Fracture IS also a latent phenomenon.")
        print(" -> Discussion must be revised.")
    else:
        print(" INTERPRETATION: M+N merge ~= 3-factor (within .01).")
        print(" -> Ambiguous. §4.3 claim should be softened.")
    print("="*63)
    logging.info("=== PHASE 2.3 EXECUTION SUCCESSFULLY COMPLETED ===")

if __name__ == "__main__":
    main()
