#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 8 (REMEDIATED): Layer 2 & 5 Extensions – SHAP Interactions Only
===============================================================================
Computes pairwise SHAP interaction strengths for each Dark Triad trait using
XGBoost models trained on the community sample and evaluated on the
representative sample.

FLAW 10 NOTE:
  - Person‑centered subtyping has been migrated to GMM/BIC in Phase 7.
    This script only produces SHAP interaction outputs.

OUTPUT:
  - results/tables/layer2_shap_interactions.csv
===============================================================================
"""

import os
import sys
import logging
import hashlib
import numpy as np
import pandas as pd
import xgboost as xgb
import shap
from sklearn.preprocessing import StandardScaler

# -----------------------------------------------------------------------------
# DIRECTORY & LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
PROCESSED_DIR = "data/processed"
TABLES_DIR = "results/tables"
os.makedirs(TABLES_DIR, exist_ok=True)

log_path = os.path.join(TABLES_DIR, "execution_audit.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(log_path, mode='a'), logging.StreamHandler(sys.stdout)],
    force=True
)

class FatalScienceError(Exception):
    pass

TARGETS = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']
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
# DATA LOADING (same logic as previous phases)
# -----------------------------------------------------------------------------
def get_available_predictors(df, sample_label, required_targets):
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
    sample = df[df['sample_origin'] == sample_label].copy()
    cols = common_preds + targets
    sample = sample[cols].dropna().astype(float)
    X = sample[common_preds].values
    y = sample[targets].values
    return X, y

def prepare_data():
    logging.info("--- Preparing Data for SHAP Interactions ---")
    master_path = os.path.join(PROCESSED_DIR, "dt3_master_dataset.csv")
    df = pd.read_csv(master_path, low_memory=False)
    preds_train = get_available_predictors(df, 'sample_1_community', TARGETS)
    preds_test  = get_available_predictors(df, 'sample_3_representative', TARGETS)
    common_preds = sorted(set(preds_train) & set(preds_test))
    if len(common_preds) < 3:
        raise FatalScienceError("Too few common predictors.")
    logging.info(f"Common predictors: {common_preds}")

    X_train, y_train = load_sample_data(df, 'sample_1_community', common_preds, TARGETS)
    X_test, y_test   = load_sample_data(df, 'sample_3_representative', common_preds, TARGETS)

    # Scale predictors on training data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    return X_train_scaled, y_train, X_test_scaled, y_test, common_preds

# -----------------------------------------------------------------------------
# MODULE: SHAP INTERACTIONS
# -----------------------------------------------------------------------------
def execute_shap_interactions(X_train, y_train, predictors):
    logging.info("--- Executing SHAP Interaction Analysis ---")
    all_interactions = []
    n_samples = min(1000, X_train.shape[0])  # use up to 1000 samples for speed

    for i, trait in enumerate(TARGETS):
        model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train[:, i])
        explainer = shap.TreeExplainer(model)
        # Compute interaction values on the subset
        interaction_values = explainer.shap_interaction_values(X_train[:n_samples])
        # Mean absolute interaction over samples
        mean_interactions = np.abs(interaction_values).mean(axis=0)
        # Ignore diagonal (main effects)
        np.fill_diagonal(mean_interactions, 0.0)

        # Extract all pairwise interactions
        P = len(predictors)
        for p1 in range(P):
            for p2 in range(p1 + 1, P):
                val = mean_interactions[p1, p2]
                if val > 0:
                    all_interactions.append({
                        'Trait': trait.replace('score_', ''),
                        'Feature_1': predictors[p1],
                        'Feature_2': predictors[p2],
                        'Absolute_Interaction_Strength': round(val, 4)
                    })
        logging.info(f"  {trait}: top interaction = {predictors[np.argmax(mean_interactions.max(axis=0))]} x ...")

    res_df = pd.DataFrame(all_interactions)
    # Sort by trait and strength
    res_df = res_df.sort_values(['Trait', 'Absolute_Interaction_Strength'], ascending=[True, False])
    out_path = os.path.join(TABLES_DIR, "layer2_shap_interactions.csv")
    res_df.to_csv(out_path, index=False)
    logging.info(f"SHAP interactions saved to {out_path}")
    return res_df

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.info("===============================================================")
    logging.info(" DT³ PHASE 8 (REMEDIATED): SHAP Interactions Extension ")
    logging.info("===============================================================")

    master_path = os.path.join(PROCESSED_DIR, "dt3_master_dataset.csv")
    if not os.path.exists(master_path):
        logging.fatal("Master dataset not found.")
        sys.exit(1)

    logging.info(f"Cryptographic Hash (Master): {hash_file(master_path)}")

    try:
        X_tr, y_tr, X_te, y_te, predictors = prepare_data()
        execute_shap_interactions(X_tr, y_tr, predictors)
        logging.info("=== PHASE 8 EXTENSIONS EXECUTION SUCCESSFULLY COMPLETED ===")
    except FatalScienceError as e:
        logging.fatal(f"PIPELINE HALTED: {e}")
        sys.exit(1)
    except Exception as e:
        logging.fatal(f"UNEXPECTED FAILURE: {e}", exc_info=True)
        sys.exit(1)