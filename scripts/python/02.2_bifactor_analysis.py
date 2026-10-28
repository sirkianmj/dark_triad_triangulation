#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 2.2 (ADDITIVE): Bifactor CFA — general Dark factor + 3 orthogonal specifics
===============================================================================
SAFETY CONTRACT:
  - Reads only data/processed/dt3_master_dataset.csv
  - Writes only baseline_06_bifactor_fit.csv and baseline_07_bifactor_loadings.csv
  - Does NOT modify existing pipeline scripts or CSVs
  - If model fails convergence, gives Heywood cases, or produces out-of-range
    indices, prints a clear FAIL message and writes NO CSV (so manuscript
    cannot accidentally cite garbage).
  - This is an ADDITIVE analysis. Deleted without consequence if undesired.

Model (Rodriguez et al. 2016 bifactor specification):
  D  =~ all 12 DTDD items
  Ms =~ DTDD_1m..4m ; Ps =~ DTDD_1p..4p ; Ns =~ DTDD_1n..4n
  All four factors orthogonal to each other.

Indices (Rodriguez et al. 2016, Psychological Methods 21(2), 137-150):
  ECV      = (Σλ_D²) / (Σλ_D² + Σλ_S²)
  ωH       = (Σλ_D)² / [(Σλ_D)² + Σ(1 - λ_D² - λ_S²)]
  ωHS_k    = (Σ_{i∈Sk} λ_Sk,i)² / [(Σ_{i∈Sk} λ_Sk,i)² + (Σ_{i∈Sk} λ_Di)²
                                   + Σ_{i∈Sk}(1 - λ_Di² - λ_Sk,i²)]
===============================================================================
"""
import os, sys, logging, hashlib
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

ITEMS = {
    "Ms": ["DTDD_1m","DTDD_2m","DTDD_3m","DTDD_4m"],
    "Ps": ["DTDD_1p","DTDD_2p","DTDD_3p","DTDD_4p"],
    "Ns": ["DTDD_1n","DTDD_2n","DTDD_3n","DTDD_4n"],
}
ALL_ITEMS = [it for sub in ITEMS.values() for it in sub]

BIFACTOR_SPEC = f"""
D  =~ {' + '.join(ALL_ITEMS)}
Ms =~ {' + '.join(ITEMS['Ms'])}
Ps =~ {' + '.join(ITEMS['Ps'])}
Ns =~ {' + '.join(ITEMS['Ns'])}

D ~~ 0*Ms
D ~~ 0*Ps
D ~~ 0*Ns
Ms ~~ 0*Ps
Ms ~~ 0*Ns
Ps ~~ 0*Ns
"""

def main():
    logging.info("="*63)
    logging.info(" DT³ PHASE 2.2 (ADDITIVE): Bifactor CFA")
    logging.info("="*63)

    master = os.path.join(PROCESSED, "dt3_master_dataset.csv")
    if not os.path.exists(master):
        logging.fatal(f"Master dataset not found: {master}")
        sys.exit(1)
    logging.info(f"Reading {master}")
    df = pd.read_csv(master, low_memory=False)

    # Same sample as the existing baseline CFA (community)
    s1 = df[df["sample_origin"] == "sample_1_community"].copy()
    s1 = s1.dropna(subset=ALL_ITEMS)
    s1[ALL_ITEMS] = s1[ALL_ITEMS].astype(float)
    logging.info(f"Community sample N = {len(s1)} (matches baseline CFA N)")

    # Fit bifactor
    logging.info("Fitting bifactor model with semopy ...")
    try:
        mod = Model(BIFACTOR_SPEC)
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

    # ---- Extract standardized loadings ----
    # semopy returns unstandardized by default. We use std estimates via
    # computing standardized loadings ourselves from unstandardized params.
    params = mod.inspect()
    est_col = "Estimate" if "Estimate" in params.columns else "Est."

    def get_loadings(factor):
        rows = params[(params["op"] == "~") &
                      (params["rval"] == factor) &
                      (params["lval"].isin(ALL_ITEMS))]
        return dict(zip(rows["lval"], rows[est_col].astype(float)))

    raw_D  = get_loadings("D")
    raw_Ms = get_loadings("Ms")
    raw_Ps = get_loadings("Ps")
    raw_Ns = get_loadings("Ns")

    # Latent variances (for standardization)
    def get_var(factor):
        m = params[(params["op"] == "~~") &
                   (params["lval"] == factor) &
                   (params["rval"] == factor)]
        return float(m[est_col].iloc[0]) if len(m) else 1.0

    var_D  = get_var("D")
    var_Ms = get_var("Ms")
    var_Ps = get_var("Ps")
    var_Ns = get_var("Ns")

    # Residual (item) variances for standardization
    def get_resid(item):
        m = params[(params["op"] == "~~") &
                   (params["lval"] == item) &
                   (params["rval"] == item)]
        return float(m[est_col].iloc[0]) if len(m) else np.nan

    resid = {it: get_resid(it) for it in ALL_ITEMS}

    # Standardized loadings: lambda_std = lambda_raw * sqrt(var_factor) / sqrt(var_item)
    # where var_item = (lambda_D_raw)^2 * var_D + (lambda_S_raw)^2 * var_S + resid
    def std_loadings(factor_name, factor_var, raw_loadings, factor_items, other_factors):
        out = {}
        for it, lam_raw in raw_loadings.items():
            if it not in factor_items:
                continue
            var_item = (raw_D.get(it, 0)**2) * var_D + resid[it]
            for other, ovar in other_factors.items():
                var_item += (other.get(it, 0)**2) * ovar
            denom = np.sqrt(var_item) if var_item > 0 else np.nan
            out[it] = lam_raw * np.sqrt(factor_var) / denom if denom and np.isfinite(denom) else np.nan
        return out

    # Compute all standardized loadings
    std_D = {}
    for it in ALL_ITEMS:
        lam_D = raw_D.get(it, 0)
        # Which specific factor does it load on?
        lam_S = 0.0
        var_S = 0.0
        for fname, items in ITEMS.items():
            if it in items:
                lam_S = {"Ms": raw_Ms, "Ps": raw_Ps, "Ns": raw_Ns}[fname].get(it, 0)
                var_S = {"Ms": var_Ms, "Ps": var_Ps, "Ns": var_Ns}[fname]
                break
        var_item = lam_D**2 * var_D + lam_S**2 * var_S + resid[it]
        denom = np.sqrt(var_item) if var_item > 0 else np.nan
        std_D[it] = lam_D * np.sqrt(var_D) / denom if np.isfinite(denom) and denom > 0 else np.nan

    std_S = {"Ms": {}, "Ps": {}, "Ns": {}}
    for fname, items in ITEMS.items():
        raw_S = {"Ms": raw_Ms, "Ps": raw_Ps, "Ns": raw_Ns}[fname]
        var_S = {"Ms": var_Ms, "Ps": var_Ps, "Ns": var_Ns}[fname]
        for it in items:
            lam_D = raw_D.get(it, 0)
            lam_S = raw_S.get(it, 0)
            var_item = lam_D**2 * var_D + lam_S**2 * var_S + resid[it]
            denom = np.sqrt(var_item) if var_item > 0 else np.nan
            std_S[fname][it] = lam_S * np.sqrt(var_S) / denom if np.isfinite(denom) and denom > 0 else np.nan

    # ---- Sanity checks ----
    all_std = list(std_D.values()) + \
              list(std_S["Ms"].values()) + \
              list(std_S["Ps"].values()) + \
              list(std_S["Ns"].values())
    heywood = [x for x in all_std if np.isfinite(x) and abs(x) > 1.0]
    nan_count = sum(1 for x in all_std if not np.isfinite(x))

    if heywood:
        logging.error(f"HEYWOOD CASES detected ({len(heywood)} loadings |λ|>1). "
                      f"Model is not well-identified on this data. NO CSV WILL BE WRITTEN.")
        sys.exit(3)
    if nan_count > 0:
        logging.error(f"{nan_count} NaN loadings. Model extraction failed. NO CSV WILL BE WRITTEN.")
        sys.exit(4)
    if not (0 <= cfi <= 1 and 0 <= tli <= 1 and rmsea >= 0):
        logging.error(f"Fit indices out of range (CFI={cfi}, TLI={tli}, RMSEA={rmsea}). "
                      f"Model is invalid. NO CSV WILL BE WRITTEN.")
        sys.exit(5)

    # ---- Compute ECV, omega_H, omega_HS ----
    # ECV = Σλ_D² / (Σλ_D² + Σλ_S²)
    sum_lD_sq = sum(v**2 for v in std_D.values())
    sum_lS_sq = sum(v**2 for f in std_S.values() for v in f.values())
    ecv = sum_lD_sq / (sum_lD_sq + sum_lS_sq) if (sum_lD_sq + sum_lS_sq) > 0 else np.nan

    # omega_H = (Σλ_D)² / [(Σλ_D)² + Σθ_ii]
    #   θ_ii = 1 - λ_D² - λ_S²   (item uniqueness)
    sum_lD = sum(std_D.values())
    sum_theta = sum(1 - std_D[it]**2 - sum(std_S[f].get(it, 0)**2 for f in std_S)
                    for it in ALL_ITEMS)
    # Full-variance formula: include specific factor contribution in denominator.
    # Var(T) = (Σλ_D)² + Σ_k (Σ_{i∈k} λ_Sk_i)² + Σθ  (Rodriguez et al. 2016)
    S_specific = sum(sum(std_S[fname][it] for it in items)**2
                     for fname, items in ITEMS.items())
    omega_H = (sum_lD**2) / (sum_lD**2 + S_specific + sum_theta) \
              if (sum_lD**2 + S_specific + sum_theta) > 0 else np.nan

    # omega_HSk per Rodriguez 2016:
    #   numerator   = (Σ_{i∈Sk} λ_Sk,i)²
    #   denominator = (Σ_{i∈Sk} λ_Sk,i)² + (Σ_{i∈Sk} λ_Di)² + Σ_{i∈Sk} θ_ii
    omega_HS = {}
    for fname, items in ITEMS.items():
        sum_lSk = sum(std_S[fname][it] for it in items)
        sum_lDi = sum(std_D[it] for it in items)
        sum_theta_k = sum(1 - std_D[it]**2 - std_S[fname][it]**2 for it in items)
        num = sum_lSk**2
        den = num + sum_lDi**2 + sum_theta_k
        omega_HS[fname] = num / den if den > 0 else np.nan

    # ---- Final sanity on indices ----
    if not (0 <= ecv <= 1 and 0 <= omega_H <= 1 and all(0 <= v <= 1 for v in omega_HS.values())):
        logging.error(f"Indices out of [0,1]: ECV={ecv}, ωH={omega_H}, ωHS={omega_HS}. NO CSV.")
        sys.exit(6)

    # ---- Write CSVs (only if all checks passed) ----
    fit_df = pd.DataFrame([{
        "Model": "Bifactor (D + Ms + Ps + Ns)",
        "Chi_Square": round(chi2, 2),
        "Degrees_of_Freedom": dof,
        "CFI": round(cfi, 3),
        "TLI": round(tli, 3),
        "RMSEA": round(rmsea, 3),
        "N": len(s1),
        "ECV": round(ecv, 3),
        "Omega_H": round(omega_H, 3),
        "Omega_HS_Ms": round(omega_HS["Ms"], 3),
        "Omega_HS_Ps": round(omega_HS["Ps"], 3),
        "Omega_HS_Ns": round(omega_HS["Ns"], 3),
    }])
    fit_path = os.path.join(TABLES, "baseline_06_bifactor_fit.csv")
    fit_df.to_csv(fit_path, index=False)
    logging.info(f"Wrote {fit_path}")

    load_rows = []
    for it in ALL_ITEMS:
        spec_factor = next(f for f, items in ITEMS.items() if it in items)
        load_rows.append({
            "Item": it,
            "D_loading": round(std_D[it], 3),
            "Specific_loading": round(std_S[spec_factor][it], 3),
            "Specific_factor": spec_factor,
        })
    load_df = pd.DataFrame(load_rows)
    load_path = os.path.join(TABLES, "baseline_07_bifactor_loadings.csv")
    load_df.to_csv(load_path, index=False)
    logging.info(f"Wrote {load_path}")

    # ---- Print summary ----
    print("\n" + "="*63)
    print(" BIFACTOR CFA RESULT")
    print("="*63)
    print(f"  χ²({dof}) = {chi2:.2f}   CFI = {cfi:.3f}   TLI = {tli:.3f}   RMSEA = {rmsea:.3f}")
    print(f"  ECV     = {ecv:.3f}")
    print(f"  ωH      = {omega_H:.3f}")
    print(f"  ωHS:    Ms = {omega_HS['Ms']:.3f}   Ps = {omega_HS['Ps']:.3f}   Ns = {omega_HS['Ns']:.3f}")
    print("="*63)
    print(f"  N = {len(s1)}")
    print(f"  CSV: {fit_path}")
    print(f"  CSV: {load_path}")
    print("="*63)
    logging.info("=== PHASE 2.2 BIFACTOR EXECUTION SUCCESSFULLY COMPLETED ===")

if __name__ == "__main__":
    main()
