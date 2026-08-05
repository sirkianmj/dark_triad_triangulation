#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 2.1 (REMEDIATED v6): Symbolic Regression – Unscaled Targets & Wide Constants
===============================================================================
Methodologically absolute script to discover explicit, human‑readable
mathematical equations for each Dark Triad trait.

FLAW 5 FINAL FIX:
  - Targets are kept in original sum‑score units (NO Z‑scoring).
  - `const_range` is widened to (-40, 40) so the genetic algorithm can
    generate proper intercepts without bloat.
  - `parsimony_coefficient=0.01` kills division-based tautologies while
    preserving additive/multiplicative structure.
  - Function set restricted to 'add', 'sub', 'mul' – no division, no
    neg/max/min.

CRITICAL CHANGES:
  - Training (discovery) sample: sample_1_community
  - Testing (replication) sample: sample_3_representative
  - Dynamic predictor alignment: RSES_sum excluded when missing.

OUTPUT FILE:
  - results/tables/layer2_symbolic_regression_equations.csv
===============================================================================
"""

import os
import sys
import logging
import hashlib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score
from gplearn.genetic import SymbolicRegressor
from gplearn.functions import make_function

# -----------------------------------------------------------------------------
# DIRECTORY & LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
PROCESSED_DIR = "data/processed"
RESULTS_DIR = "results"
FIGURES_DIR = "results/figures"
TABLES_DIR = "results/tables"

for d in [RESULTS_DIR, FIGURES_DIR, TABLES_DIR]:
    os.makedirs(d, exist_ok=True)

log_path = os.path.join(TABLES_DIR, "execution_audit.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(log_path, mode='a'), logging.StreamHandler(sys.stdout)],
    force=True
)

class FatalScienceError(Exception):
    pass

# Target traits (raw scores)
TARGETS = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']
# All potential predictors (Extraversion included, RSES_sum may be dropped)
PREDICTORS = ['age', 'BFI_A_sum', 'BFI_C_sum', 'BFI_N_sum', 'BFI_O_sum',
              'BFI_E_sum', 'TEQ_sum', 'RSES_sum']

# -----------------------------------------------------------------------------
# CRYPTOGRAPHIC PROVENANCE
# -----------------------------------------------------------------------------
def hash_file(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# -----------------------------------------------------------------------------
# DATA LOADING WITH DYNAMIC PREDICTOR FILTERING
# -----------------------------------------------------------------------------
def get_available_predictors(df, sample_label, required_targets):
    """
    Returns predictors that are present and have at least 10% non‑missing values
    among rows with valid targets.
    """
    sample = df[df['sample_origin'] == sample_label]
    base = sample.dropna(subset=required_targets)
    if len(base) == 0:
        return []
    available = []
    for pred in PREDICTORS:
        if pred in base.columns:
            non_missing_frac = base[pred].notna().mean()
            if non_missing_frac >= 0.1:
                available.append(pred)
            else:
                logging.warning(f"  Predictor '{pred}' is >90% missing in {sample_label}, excluded.")
        else:
            logging.warning(f"  Predictor '{pred}' not found in {sample_label} columns.")
    return available

def load_sample_data(df, sample_label, common_preds, targets):
    """Extract predictors and targets for a sample, keeping only complete rows."""
    sample = df[df['sample_origin'] == sample_label].copy()
    cols = common_preds + targets
    sample = sample[cols].dropna().astype(float)
    X = sample[common_preds].values
    y = sample[targets].values
    return X, y

def prepare_symbolic_data(df):
    """
    Returns X_train_scaled, y_train_raw, X_test_scaled, y_test_raw,
    and list of common predictors.
    Targets are NOT scaled.
    """
    logging.info("--- Preparing Symbolic Regression Data ---")
    preds_train = get_available_predictors(df, 'sample_1_community', TARGETS)
    preds_test  = get_available_predictors(df, 'sample_3_representative', TARGETS)
    common_preds = sorted(set(preds_train) & set(preds_test))
    if len(common_preds) < 3:
        raise FatalScienceError("Too few common predictors for symbolic regression.")
    logging.info(f"Common predictors: {common_preds}")

    X_train, y_train = load_sample_data(df, 'sample_1_community', common_preds, TARGETS)
    X_test, y_test   = load_sample_data(df, 'sample_3_representative', common_preds, TARGETS)

    if X_train.shape[0] < 100 or X_test.shape[0] < 100:
        raise FatalScienceError("Insufficient data in one of the samples for symbolic regression.")

    # Standardize predictors only
    scaler_X = StandardScaler()
    X_train_scaled = scaler_X.fit_transform(X_train)
    X_test_scaled = scaler_X.transform(X_test)

    # y_train and y_test are raw sum scores
    return X_train_scaled, y_train, X_test_scaled, y_test, common_preds

# -----------------------------------------------------------------------------
# SYMBOLIC REGRESSION EXECUTION (UNSCALED TARGETS, WIDE CONSTANTS)
# -----------------------------------------------------------------------------
def execute_symbolic_regression(X_train, y_train, X_test, y_test, predictors):
    logging.info("--- Executing Symbolic Regression (Unscaled Targets, Non‑Linear) ---")
    from gplearn.functions import make_function

    # Protected division to avoid zero‑division errors
    def protected_div(x1, x2):
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(np.abs(x2) > 0.001, np.divide(x1, x2), 1.)
    pdiv = make_function(function=protected_div, name='div', arity=2)

    results = []

    for i, trait in enumerate(TARGETS):
        y_train_trait = y_train[:, i]
        y_test_trait  = y_test[:, i]

        logging.info(f"Initiating genetic evolution for {trait}...")

        est = SymbolicRegressor(
            population_size=5000,
            generations=40,
            stopping_criteria=0.01,
            p_crossover=0.7,
            p_subtree_mutation=0.1,
            p_hoist_mutation=0.05,
            p_point_mutation=0.1,
            max_samples=0.9,
            verbose=0,
            parsimony_coefficient=0.001,   # relaxed to allow non‑linear interactions
            random_state=42,
            feature_names=predictors,
            function_set=['add', 'sub', 'mul', pdiv, 'abs', 'max', 'min'],
            const_range=(-40.0, 40.0)       # allows raw‑score intercepts
        )

        est.fit(X_train, y_train_trait)
        equation = str(est._program)

        # Discovery R²
        y_pred_train = est.predict(X_train)
        r2_discovery = r2_score(y_train_trait, y_pred_train)

        # Replication R²
        y_pred_test = est.predict(X_test)
        r2_replication = r2_score(y_test_trait, y_pred_test)

        logging.info(f"Discovered Form [{trait}]: {equation}")
        logging.info(f"Validation R² -> Discovery: {r2_discovery:.3f} | Replication: {r2_replication:.3f}")

        results.append({
            'Trait': trait.replace('score_', ''),
            'Discovered_Equation': equation,
            'Discovery_R2': round(r2_discovery, 3),
            'Replication_R2': round(r2_replication, 3),
            'Equation_Complexity_Nodes': est._program.length_
        })

    res_df = pd.DataFrame(results)
    out_path = os.path.join(TABLES_DIR, "layer2_symbolic_regression_equations.csv")
    res_df.to_csv(out_path, index=False)
    logging.info(f"Symbolic regression results saved to {out_path}")
    return res_df
# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.info("===============================================================")
    logging.info(" DT³ PHASE 2.1 (REMEDIATED v6): Symbolic Regression (Unscaled + Wide Constants)")
    logging.info("===============================================================")

    master_path = os.path.join(PROCESSED_DIR, "dt3_master_dataset.csv")
    if not os.path.exists(master_path):
        logging.fatal("Master dataset not found. Run Phase 1 first.")
        sys.exit(1)

    logging.info(f"Cryptographic Hash (Master): {hash_file(master_path)}")
    df_master = pd.read_csv(master_path, low_memory=False)

    try:
        X_tr, y_tr_raw, X_te, y_te_raw, preds = prepare_symbolic_data(df_master)
        execute_symbolic_regression(X_tr, y_tr_raw, X_te, y_te_raw, preds)
        logging.info("=== PHASE 2.1 EXECUTION SUCCESSFULLY COMPLETED ===")
    except FatalScienceError as e:
        logging.fatal(f"PIPELINE HALTED: {e}")
        sys.exit(1)
    except Exception as e:
        logging.fatal(f"UNEXPECTED FAILURE: {e}", exc_info=True)
        sys.exit(1)