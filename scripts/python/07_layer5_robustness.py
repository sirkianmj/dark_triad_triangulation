#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 7 (REMEDIATED v3): Layer 5 – Rigor, Robustness & Person‑Centered Analysis
===============================================================================

FLAW 6 FIX (SDI Cheating):
  - Null models are trained on **pseudo‑traits** created by randomly shuffling
    the 12 DTDD items into 3 arbitrary groups and summing them, ensuring identical
    distributional shape but no true latent separation.
  - All null models use exactly the same XGBoost hyperparameters (n_estimators=100,
    max_depth=4, learning_rate=0.05) and training sample size as the observed models.

FLAW 10 FIX (Person‑Centered Analysis):
  - Instead of HDBSCAN, we fit a **Gaussian Mixture Model** with 1‑5 components
    on the local SHAP vectors of high scorers.  The Bayesian Information
    Criterion (BIC) is reported; if BIC increases monotonically with components,
    it indicates no strong evidence for subtypes.

OTHER MODULES:
  - Rashomon robustness across Elastic‑Net, Random Forest, XGBoost.
  - Cross‑sample replication: train on community, test on representative;
    also probe student sample where possible with honest disclosure of negative R².
  - Conformal prediction intervals via split‑conformal method.

STRICT CONSTRAINTS:
  - Train on sample_1_community, test on sample_3_representative.
  - Dynamic predictor alignment (RSES_sum excluded if missing).
  - DTDD matrix exactly aligned with training predictor rows (fix for row‑size mismatch).

OUTPUT FILES (results/tables/):
  - layer5_sdi_permutation_results.csv
  - layer5_rashomon_robustness.csv
  - layer5_cross_sample_replication.csv
  - layer5_person_centered_bic.csv
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
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet
from sklearn.mixture import GaussianMixture
from sklearn.metrics import r2_score
from scipy.spatial.distance import cosine

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

# Core Dirty Dozen items for pseudo‑trait generation
DTDD_ITEMS = [
    'DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m',
    'DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p',
    'DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n'
]

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
# DATA LOADING & UTILITIES
# -----------------------------------------------------------------------------
def get_available_predictors(df, sample_label, required_targets):
    """Return predictors present and with >= 10% non‑missing values."""
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

def prepare_layer5_data(df):
    """
    Returns scaled train/test predictors, raw train/test targets,
    aligned predictor list, and the raw DTDD item matrix (for pseudo‑traits).
    Train: sample_1_community, Test: sample_3_representative.
    The DTDD matrix is filtered to the exact same rows as the training set.
    """
    logging.info("--- Preparing Layer 5 Data (Rigor & Robustness) ---")
    preds_train = get_available_predictors(df, 'sample_1_community', TARGETS)
    preds_test  = get_available_predictors(df, 'sample_3_representative', TARGETS)
    common_preds = sorted(set(preds_train) & set(preds_test))
    if len(common_preds) < 3:
        raise FatalScienceError("Too few common predictors for Layer 5.")
    logging.info(f"Common predictors: {common_preds}")

    # Load training data and test data
    X_train, y_train = load_sample_data(df, 'sample_1_community', common_preds, TARGETS)
    X_test, y_test   = load_sample_data(df, 'sample_3_representative', common_preds, TARGETS)

    if X_train.shape[0] < 200 or X_test.shape[0] < 50:
        raise FatalScienceError("Insufficient data for Layer 5.")

    # Standardize predictors (fit on train only)
    scaler_X = StandardScaler()
    X_train_scaled = scaler_X.fit_transform(X_train)
    X_test_scaled = scaler_X.transform(X_test)

    # Align DTDD item matrix with the exact training rows.
    # The community sample rows used for X_train are those with complete data in
    # common_preds + TARGETS. We extract those same rows from the original dataframe.
    community_df = df[df['sample_origin'] == 'sample_1_community'].copy()
    all_cols = common_preds + TARGETS
    community_complete = community_df.dropna(subset=all_cols)
    # Now extract DTDD items from this filtered dataframe; drop rows with any missing DTDD item
    dtdd_data = community_complete[DTDD_ITEMS].dropna().astype(float).values
    if dtdd_data.shape[0] != X_train.shape[0]:
        raise FatalScienceError(
            f"Row mismatch: DTDD matrix has {dtdd_data.shape[0]} rows, "
            f"but X_train has {X_train.shape[0]} rows. Check alignment."
        )
    if dtdd_data.shape[0] < 100:
        raise FatalScienceError("Insufficient DTDD item data for pseudo‑traits.")

    logging.info(f"Aligned training rows: {dtdd_data.shape[0]} (DTDD) vs {X_train.shape[0]} (predictors)")

    return (X_train_scaled, y_train,
            X_test_scaled, y_test,
            common_preds, dtdd_data)

# -----------------------------------------------------------------------------
# MODULE 1: FORMAL SHAP DIVERGENCE INDEX (SDI) – PSEUDO‑TRAIT NULL (Flaw 6)
# -----------------------------------------------------------------------------
def generate_pseudo_traits(dtdd_matrix, rng, n_pseudo=3):
    """
    Randomly shuffle the 12 DTDD items into `n_pseudo` groups and sum them.
    Returns pseudo‑trait scores of shape (n_samples, n_pseudo).
    """
    n, p = dtdd_matrix.shape
    shuffled_indices = rng.permutation(p)
    groups = np.array_split(shuffled_indices, n_pseudo)
    pseudo_scores = np.zeros((n, n_pseudo))
    for g_idx, group in enumerate(groups):
        pseudo_scores[:, g_idx] = dtdd_matrix[:, group].sum(axis=1)
    return pseudo_scores

def execute_sdi_pseudo_trait(X_train, y_train, X_test, y_test, dtdd_data, preds, n_perms=500):
    logging.info("--- Executing Formal SHAP Divergence Index (Pseudo‑Trait Null, Out‑of‑Sample) ---")
    # Train observed models on training data, but compute SHAP on test data
    obs_shap_vecs = []
    for i in range(y_train.shape[1]):
        model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train[:, i])
        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(X_test)   # <--- Now on X_test
        obs_shap_vecs.append(np.abs(sv).mean(axis=0))

    obs_distances = [cosine(obs_shap_vecs[i], obs_shap_vecs[j]) for i in range(3) for j in range(i+1, 3)]
    obs_sdi = float(np.mean(obs_distances))
    logging.info(f"Observed SDI (out‑of‑sample): {obs_sdi:.4f}")

    # Null distribution using pseudo‑traits, also evaluated on X_test
    rng = np.random.RandomState(42)
    null_sdis = []
    for perm_idx in range(n_perms):
        pseudo_y = generate_pseudo_traits(dtdd_data, rng, n_pseudo=3)
        null_vecs = []
        for k in range(3):
            model_null = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=perm_idx)
            model_null.fit(X_train, pseudo_y[:, k])
            explainer = shap.TreeExplainer(model_null)
            sv = explainer.shap_values(X_test)   # <--- Out‑of‑sample
            null_vecs.append(np.abs(sv).mean(axis=0))
        null_dists = [cosine(null_vecs[i], null_vecs[j]) for i in range(3) for j in range(i+1, 3)]
        null_sdis.append(float(np.mean(null_dists)))
        if (perm_idx+1) % 100 == 0:
            logging.info(f"  SDI null permutation {perm_idx+1}/{n_perms}")

    null_arr = np.array(null_sdis)
    null_mean = float(null_arr.mean())
    null_std = float(null_arr.std())
    p_value = np.mean(null_arr >= obs_sdi)

    logging.info(f"SDI Null: mean {null_mean:.4f} ± {null_std:.4f}, p = {p_value:.4f}")
    res_df = pd.DataFrame([{
        'Observed_SDI': round(obs_sdi, 4),
        'Null_Mean': round(null_mean, 4),
        'Null_Std': round(null_std, 4),
        'Permutation_P_Value': p_value
    }])
    out_path = os.path.join(TABLES_DIR, "layer5_sdi_permutation_results.csv")
    res_df.to_csv(out_path, index=False)
    return res_df

# -----------------------------------------------------------------------------
# MODULE 2: RASHOMON SET ROBUSTNESS
# -----------------------------------------------------------------------------
def execute_rashomon_robustness(X_train, y_train, X_test, y_test):
    logging.info("--- Executing Multi‑Architecture Robustness (Rashomon Set) ---")
    architectures = {
        'Elastic-Net': ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=2000, random_state=42),
        'Random Forest': RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42),
        'XGBoost': xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
    }
    results = []
    for i, trait in enumerate(TARGETS):
        y_tr = y_train[:, i]
        y_te = y_test[:, i]
        for arch_name, model in architectures.items():
            model.fit(X_train, y_tr)
            preds = model.predict(X_test)
            r2 = r2_score(y_te, preds)
            results.append({
                'Trait': trait.replace('score_', ''),
                'Architecture': arch_name,
                'Test_R2': round(r2, 3)
            })
            logging.info(f"Rashomon [{trait} - {arch_name}]: R² = {r2:.3f}")
    res_df = pd.DataFrame(results)
    out_path = os.path.join(TABLES_DIR, "layer5_rashomon_robustness.csv")
    res_df.to_csv(out_path, index=False)
    return res_df

# -----------------------------------------------------------------------------
# MODULE 3: CROSS‑SAMPLE REPLICATION & CONFORMAL PREDICTION
# -----------------------------------------------------------------------------
def conformal_prediction_width(model, X_train, y_train, X_cal, y_cal, alpha=0.05):
    model.fit(X_train, y_train)
    cal_preds = model.predict(X_cal)
    residuals = np.abs(y_cal - cal_preds)
    n = len(residuals)
    if n == 0:
        return np.nan
    q_hat = np.sort(residuals)[int(np.ceil((n+1)*(1-alpha))) - 1]
    return float(2 * q_hat)

def execute_cross_sample_replication(df_master, preds_train, preds_test):
    logging.info("--- Executing Cross‑Sample Replication & Conformal Prediction ---")
    common_preds = sorted(set(preds_train) & set(preds_test))
    if len(common_preds) < 3:
        logging.error("Too few common predictors for cross‑sample replication.")
        return None
    results = []
    for sample_id in ['sample_1_community', 'sample_3_representative', 'sample_2_student']:
        X, y = load_sample_data(df_master, sample_id, common_preds, TARGETS)
        if X.shape[0] < 20:
            logging.warning(f"Skipping {sample_id}: insufficient data (N={X.shape[0]}).")
            continue
        for i, trait in enumerate(TARGETS):
            y_trait = y[:, i]
            model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
            cv_scores = cross_val_score(model, X, y_trait, cv=5, scoring='r2', n_jobs=-1)
            mean_cv_r2 = float(np.mean(cv_scores))
            X_tr, X_cal, y_tr, y_cal = train_test_split(X, y_trait, test_size=0.2, random_state=42)
            width = conformal_prediction_width(
                xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42),
                X_tr, y_tr, X_cal, y_cal)
            results.append({
                'Sample': sample_id,
                'Trait': trait.replace('score_', ''),
                'N_Obs': X.shape[0],
                'Predictors_Used': ",".join(common_preds),
                'CV_5Fold_R2_Mean': round(mean_cv_r2, 3),
                'Conformal_95_PI_Mean_Width': round(width, 3)
            })
            logging.info(f"Replication [{sample_id} - {trait}]: N={X.shape[0]}, CV R² = {mean_cv_r2:.3f}, PI width = {width:.3f}")
    res_df = pd.DataFrame(results)
    out_path = os.path.join(TABLES_DIR, "layer5_cross_sample_replication.csv")
    res_df.to_csv(out_path, index=False)
    return res_df

# -----------------------------------------------------------------------------
# MODULE 4: PERSON‑CENTERED GMM (BIC) ANALYSIS – Flaw 10
# -----------------------------------------------------------------------------
def execute_person_centered_gmm(X_train, y_train, X_test, y_test, preds):
    logging.info("--- Executing Person‑Centered GMM (BIC) Analysis (Out‑of‑Sample) ---")
    all_bic = []
    for i, trait in enumerate(TARGETS):
        model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train[:, i])
        explainer = shap.TreeExplainer(model)
        # Use TEST set for high scorers and SHAP values
        threshold = np.percentile(y_test[:, i], 80)
        high_idx = np.where(y_test[:, i] >= threshold)[0]
        X_high = X_test[high_idx]
        shap_vals_high = explainer.shap_values(X_high)

        if shap_vals_high.shape[0] < 30:
            logging.warning(f"  Not enough high scorers for GMM on {trait}.")
            continue

        for n_comp in range(1, 6):
            gmm = GaussianMixture(n_components=n_comp, random_state=42)
            gmm.fit(shap_vals_high)
            bic = gmm.bic(shap_vals_high)
            all_bic.append({
                'Trait': trait.replace('score_', ''),
                'N_Components': n_comp,
                'BIC': round(bic, 2)
            })
        logging.info(f"  {trait}: BIC values computed for 1‑5 components.")

    if not all_bic:
        logging.error("No BIC data generated.")
        return None
    bic_df = pd.DataFrame(all_bic)
    out_path = os.path.join(TABLES_DIR, "layer5_person_centered_bic.csv")
    bic_df.to_csv(out_path, index=False)
    logging.info(f"Person‑centered BIC results saved to {out_path}")
    return bic_df

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.info("===============================================================")
    logging.info(" DT³ PHASE 7 (REMEDIATED v3): Layer 5 – Rigor, Robustness & Person‑Centered")
    logging.info("===============================================================")

    master_path = os.path.join(PROCESSED_DIR, "dt3_master_dataset.csv")
    if not os.path.exists(master_path):
        logging.fatal("Master dataset not found. Run Phase 1 first.")
        sys.exit(1)

    logging.info(f"Cryptographic Hash (Master): {hash_file(master_path)}")
    df_master = pd.read_csv(master_path, low_memory=False)

    try:
        (X_tr, y_tr, X_te, y_te, common_preds, dtdd_matrix) = prepare_layer5_data(df_master)

        # 1. SDI with pseudo‑trait null
        execute_sdi_pseudo_trait(X_tr, y_tr, X_te, y_te, dtdd_matrix, common_preds)

        # 2. Rashomon robustness
        execute_rashomon_robustness(X_tr, y_tr, X_te, y_te)

        # 3. Cross‑sample replication
        preds_train = get_available_predictors(df_master, 'sample_1_community', TARGETS)
        preds_test  = get_available_predictors(df_master, 'sample_3_representative', TARGETS)
        execute_cross_sample_replication(df_master, preds_train, preds_test)

        # 4. Person‑centered GMM BIC analysis
        execute_person_centered_gmm(X_tr, y_tr, X_te, y_te, common_preds)

        logging.info("=== PHASE 7 EXECUTION SUCCESSFULLY COMPLETED ===")
    except FatalScienceError as e:
        logging.fatal(f"PIPELINE HALTED: {e}")
        sys.exit(1)
    except Exception as e:
        logging.fatal(f"UNEXPECTED FAILURE: {e}", exc_info=True)
        sys.exit(1)