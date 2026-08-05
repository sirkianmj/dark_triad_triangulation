#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 5 (REMEDIATED v2): Layer 3 – Exploratory Dependence & Frozen Counterfactuals
===============================================================================

FLAW 4 FIX:
  - The PC algorithm has been removed entirely.
  - Instead, an **exploratory dependence graph** is built by computing partial
    correlations among the external predictors (Big Five, TEQ, age).  Edges are
    retained if the Fisher z‑test yields p < 0.001 (Bonferroni‑corrected).
  - All outputs are labelled "Exploratory Dependence Graph" – no causal claims.

FLAW 8 FIX (IMPROVED):
  - During counterfactual generation, immutable demographics (age) are FROZEN.
    Only psychological covariates (BFI, TEQ, RSES) are perturbed.
  - The algorithm uses a deterministic grid‑search over each modifiable feature
    to find the **smallest absolute shift** (within ±2 empirical standard deviations)
    that flips the predicted trait score below the population median.
  - This replaces the scipy optimizer, eliminating convergence failures.

STRICT CONSTRAINTS:
  - Train on sample_1_community, test on sample_3_representative.
  - Predictors dynamically aligned (RSES_sum dropped if missing).
  - All output labelled as exploratory.

OUTPUT FILES (results/tables/):
  - layer3_exploratory_dependence.csv
  - layer3_counterfactual_flipping.csv
===============================================================================
"""

import os
import sys
import logging
import hashlib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
from scipy.stats import norm

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
# Immutable demographics to freeze during counterfactuals
IMMUTABLE = ['age']  # 'gender' could be added if available

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
    Returns predictors that are present and have at least 10% non‑missing values.
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

def prepare_layer3_data(df):
    """
    Returns train/test data and aligned predictor list.
    Train: sample_1_community, Test: sample_3_representative.
    Targets are unscaled; predictors are standardized (fit on train).
    """
    logging.info("--- Preparing Layer 3 Data (Exploratory Dependence + Counterfactuals) ---")
    preds_train = get_available_predictors(df, 'sample_1_community', TARGETS)
    preds_test  = get_available_predictors(df, 'sample_3_representative', TARGETS)
    common_preds = sorted(set(preds_train) & set(preds_test))
    if len(common_preds) < 3:
        raise FatalScienceError("Too few common predictors for Layer 3.")
    logging.info(f"Common predictors: {common_preds}")

    X_train, y_train = load_sample_data(df, 'sample_1_community', common_preds, TARGETS)
    X_test, y_test   = load_sample_data(df, 'sample_3_representative', common_preds, TARGETS)

    if X_train.shape[0] < 200 or X_test.shape[0] < 50:
        raise FatalScienceError("Insufficient data for Layer 3.")

    # Standardize predictors
    scaler_X = StandardScaler()
    X_train_scaled = scaler_X.fit_transform(X_train)
    X_test_scaled = scaler_X.transform(X_test)

    return (X_train_scaled, y_train,
            X_test_scaled, y_test,
            common_preds, scaler_X)

# -----------------------------------------------------------------------------
# MODULE 1: EXPLORATORY PARTIAL CORRELATION GRAPH (Flaw 4)
# -----------------------------------------------------------------------------
def partial_corr(X):
    """Compute pairwise partial correlations (all other variables controlled)."""
    n, p = X.shape
    cov = np.cov(X, rowvar=False)
    try:
        prec = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        return np.zeros((p, p)), np.ones((p, p))
    diag = np.diag(prec)
    pcorr = -prec / np.sqrt(np.outer(diag, diag))
    np.fill_diagonal(pcorr, 0.0)
    return pcorr

def fisher_z_test(r, n, k):
    """Fisher z‑transform for partial correlation, p‑value."""
    z = 0.5 * np.log((1 + r) / (1 - r)) * np.sqrt(n - k - 3)
    p_val = 2 * (1 - norm.cdf(abs(z)))
    return p_val

def explore_dependence_graph(X_train, predictor_names, alpha=0.001):
    """
    Build an exploratory dependence graph using partial correlations.
    Edges are drawn if p < alpha (Bonferroni‑corrected for pairwise tests).
    """
    logging.info("--- Executing Exploratory Dependence Graph (Partial Correlations) ---")
    n, p = X_train.shape
    pcorr = partial_corr(X_train)
    num_tests = p * (p - 1) / 2
    alpha_corrected = alpha / num_tests

    edges = []
    for i in range(p):
        for j in range(i+1, p):
            r = pcorr[i, j]
            p_val = fisher_z_test(r, n, k=p-2)
            if p_val < alpha_corrected:
                edges.append({
                    'Source': predictor_names[i],
                    'Target': predictor_names[j],
                    'Partial_Correlation': round(r, 4),
                    'p_value': p_val
                })

    logging.info(f"Exploratory Dependence Graph: {len(edges)} significant edges (α corrected = {alpha_corrected:.6f}).")
    df_edges = pd.DataFrame(edges)
    out_path = os.path.join(TABLES_DIR, "layer3_exploratory_dependence.csv")
    df_edges.to_csv(out_path, index=False)
    return df_edges

# -----------------------------------------------------------------------------
# MODULE 2: COUNTERFACTUALS – GRID SEARCH WITH FROZEN DEMOGRAPHICS (Flaw 8)
# -----------------------------------------------------------------------------
def find_minimal_counterfactual(model, sample, predictor_names, immutable_set,
                                median_threshold):
    """
    Grid‑search over each modifiable feature to find the smallest absolute shift
    (within ±2.5 standard deviations) that pushes the predicted score below the
    median.  Returns (feature_name, minimal_shift_required) or (None, np.inf)
    if no shift succeeds.
    """
    # Identify modifiable features (indices)
    modifiable_idx = [i for i, name in enumerate(predictor_names) if name not in immutable_set]
    if not modifiable_idx:
        return None, np.inf

    # Search grid: shifts from -2.5 to 2.5 in steps of 0.05 std
    shifts = np.linspace(-2.5, 2.5, 101)  # 101 points
    best_feature = None
    best_shift_magnitude = np.inf

    for fi in modifiable_idx:
        feature_name = predictor_names[fi]
        for shift in shifts:
            perturbed = sample.copy()
            perturbed[fi] += shift
            pred = model.predict(perturbed.reshape(1, -1))[0]
            if pred <= median_threshold:
                abs_shift = abs(shift)
                if abs_shift < best_shift_magnitude:
                    best_shift_magnitude = abs_shift
                    best_feature = feature_name
                break  # No need to try larger shifts for this feature once success
        # Continue to next feature

    if best_feature is None:
        return None, np.inf
    else:
        return best_feature, best_shift_magnitude

def execute_counterfactuals(X_train, y_train, X_test, y_test, predictor_names, scaler_X):
    logging.info("--- Executing Frozen‑Demographics Counterfactual Analysis (Grid Search) ---")
    immutable_set = set(IMMUTABLE)
    immutable_existing = [name for name in IMMUTABLE if name in predictor_names]
    if not immutable_existing:
        logging.warning("No immutable demographics found in predictors; age not frozen?")
    logging.info(f"Immutable features (frozen): {immutable_existing}")

    # Train XGBoost models for each trait on training data
    models = []
    median_thresholds = []
    for i, trait in enumerate(TARGETS):
        model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train[:, i])
        models.append(model)
        median_thresholds.append(np.median(y_test[:, i]))
        logging.info(f"Median threshold for {trait}: {median_thresholds[-1]:.2f}")

    # Identify high scorers (top 20%) in the test set for each trait
    summary = []
    n_test = X_test.shape[0]
    for i, trait in enumerate(TARGETS):
        trait_scores = y_test[:, i]
        threshold_high = np.percentile(trait_scores, 80)
        high_idx = np.where(trait_scores >= threshold_high)[0]
        logging.info(f"Counterfactuals for {trait}: {len(high_idx)} high scorers (≥{threshold_high:.2f}).")

        if len(high_idx) == 0:
            summary.append({'Trait': trait.replace('score_', ''),
                            'Most_Frequent_Flip_Driver': 'none',
                            'Proportion_Requiring_Flip': 0.0})
            continue

        flip_features = []
        for idx in high_idx:
            sample = X_test[idx].copy()
            best_feat, _ = find_minimal_counterfactual(
                models[i], sample, predictor_names,
                immutable_set=immutable_set,
                median_threshold=median_thresholds[i]
            )
            flip_features.append(best_feat if best_feat is not None else 'none')

        from collections import Counter
        counts = Counter(flip_features)
        total = len(flip_features)
        # Most common feature excluding 'none'
        most_common = counts.most_common(2)
        primary = 'none'
        prop = 0.0
        for feat, cnt in most_common:
            if feat != 'none':
                primary = feat
                prop = cnt / total
                break
        if primary == 'none':
            logging.warning(f"  No modifiable feature successfully flipped for {trait}.")
        else:
            logging.info(f"  [{trait}] Primary tipping feature: {primary} ({prop*100:.1f}%)")
        summary.append({
            'Trait': trait.replace('score_', ''),
            'Most_Frequent_Flip_Driver': primary,
            'Proportion_Requiring_Flip': round(prop, 3)
        })

    res_df = pd.DataFrame(summary)
    out_path = os.path.join(TABLES_DIR, "layer3_counterfactual_flipping.csv")
    res_df.to_csv(out_path, index=False)
    logging.info(f"Counterfactual results saved to {out_path}")
    return res_df

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.info("===============================================================")
    logging.info(" DT³ PHASE 5 (REMEDIATED v2): Layer 3 – Exploratory Dependence & Frozen Counterfactuals")
    logging.info("===============================================================")

    master_path = os.path.join(PROCESSED_DIR, "dt3_master_dataset.csv")
    if not os.path.exists(master_path):
        logging.fatal("Master dataset not found. Run Phase 1 first.")
        sys.exit(1)

    logging.info(f"Cryptographic Hash (Master): {hash_file(master_path)}")
    df_master = pd.read_csv(master_path, low_memory=False)

    try:
        X_tr, y_tr, X_te, y_te, preds, scaler_X = prepare_layer3_data(df_master)

        # 1. Exploratory dependence graph (replaces PC algorithm)
        explore_dependence_graph(X_tr, preds)

        # 2. Counterfactuals with frozen demographics (grid search)
        execute_counterfactuals(X_tr, y_tr, X_te, y_te, preds, scaler_X)

        logging.info("=== PHASE 5 EXECUTION SUCCESSFULLY COMPLETED ===")
    except FatalScienceError as e:
        logging.fatal(f"PIPELINE HALTED: {e}")
        sys.exit(1)
    except Exception as e:
        logging.fatal(f"UNEXPECTED FAILURE: {e}", exc_info=True)
        sys.exit(1)