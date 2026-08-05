#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 1 (REMEDIATED): Data Preprocessing & Provenance
===============================================================================
This script converts raw .csv files (originally .Rds) into a clean, unified 
master dataset for the DT³ project. It applies the original study's quality 
filters, computes composite scores, and preserves sample origin for future 
split‑sample cross‑validation (Flaw 1 remediation). 

SPECIFIC REMEDIATION (Flaw 9 - Missing Extraversion):
- Searches for BFI‑E items (e.g., BFI_E_1 … BFI_E_8) in each sample file.
- If items are present, computes BFE_E_sum and adds it to the master dataset.
- If items are completely absent, logs a severe warning and omits the column.
  This omission will be clearly documented in the manuscript Limitations.

STRICT CONSTRAINTS:
- No data leakage between samples at this stage; `sample_origin` column is 
  preserved so that subsequent modelling scripts can isolate training (Community),
  test (Representative), and probe (Student) samples independently.
- Cryptographic hashes of input files are logged for auditability.
- All numeric conversions and outlier handling are explicit and validated.
- Composites are computed using `min_count` to avoid treating missing data as 0.

OUTPUT:
- data/processed/dt3_master_dataset.csv (merged all samples)
- data/processed/dt3_test_retest.csv (matched pairs)
- logs are written to results/tables/execution_audit.log
===============================================================================
"""

import os
import sys
import logging
import hashlib
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# DIRECTORY & LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
PROCESSED_DIR = "data/processed"
RESULTS_DIR = "results/tables"
for d in [PROCESSED_DIR, RESULTS_DIR]:
    os.makedirs(d, exist_ok=True)

log_path = os.path.join(RESULTS_DIR, "execution_audit.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(log_path, mode='a'), logging.StreamHandler(sys.stdout)],
    force=True
)

class FatalPreprocessingError(Exception):
    """Raised when critical data integrity assumptions are violated."""
    pass

# -----------------------------------------------------------------------------
# CRYPTOGRAPHIC PROVENANCE
# -----------------------------------------------------------------------------
def hash_file(filepath):
    """Generate SHA‑256 hash for strict data provenance."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# -----------------------------------------------------------------------------
# CONSTANTS: Core Dirty Dozen items
# -----------------------------------------------------------------------------
CORE_12_DTDD = [
    'DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m',
    'DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p',
    'DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n'
]

# Prefixes for external scale items
BIG_FIVE_PREFIXES = {
    'BFI_A_': 'BFI_A_sum',
    'BFI_C_': 'BFI_C_sum',
    'BFI_N_': 'BFI_N_sum',
    'BFI_O_': 'BFI_O_sum',
    'BFI_E_': 'BFI_E_sum'   # Extraversion – crucial for Narcissism distinctiveness
}
OTHER_SCALES = {
    'TEQ_': 'TEQ_sum',
    'RSES_': 'RSES_sum'
}
ALL_SCALE_PREFIXES = {**BIG_FIVE_PREFIXES, **OTHER_SCALES}

# -----------------------------------------------------------------------------
# SAMPLE‑LEVEL CLEANING FUNCTION
# -----------------------------------------------------------------------------
def clean_sample(df, sample_id, speeder_limit=26):
    """
    Applies original study quality filters and computes composites for one sample.
    Returns cleaned DataFrame with standardized column names.
    """
    logging.info(f"--- Cleaning {sample_id} ---")
    initial_n = len(df)

    # 1. Standardize demographic column names
    rename_map = {}
    for col in df.columns:
        lc = col.lower()
        if lc == 'age':
            rename_map[col] = 'age'
        elif lc in ('gender', 'sex'):
            rename_map[col] = 'gender'
        elif lc == 'education':
            rename_map[col] = 'education'
    df = df.rename(columns=rename_map)

    # 2. Age filter (18‑100)
    if 'age' in df.columns:
        df['age'] = pd.to_numeric(df['age'], errors='coerce')
        before_age = len(df)
        df = df[df['age'].between(18, 100)]
        logging.info(f"Age filter removed {before_age - len(df)} rows.")

    # 3. Quality flags / speeders
    for qcol in ['speeder', 'speeder_flag', 'low_q_res_std', 'low_q_res']:
        if qcol in df.columns:
            if qcol.startswith('speeder'):
                before = len(df)
                df = df[~df[qcol].astype(str).str.lower().isin(['true', '1', 'yes'])]
                logging.info(f"Speeder filter on '{qcol}' removed {before - len(df)} rows.")
            else:
                # 'low_q_res' expects 'HQ' for high quality
                before = len(df)
                df = df[df[qcol].astype(str).str.upper() == 'HQ']
                logging.info(f"Quality filter on '{qcol}' removed {before - len(df)} rows.")

    # 4. Convert core DTDD items to numeric and drop rows where all DTDD items are missing
    present_dtdd = [c for c in CORE_12_DTDD if c in df.columns]
    for c in present_dtdd:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=present_dtdd, how='all')
    logging.info(f"After DTDD item cleaning: {len(df)} rows remain.")

    # 5. Compute Dark Triad composites
    m_cols = [c for c in ['DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m'] if c in df.columns]
    p_cols = [c for c in ['DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p'] if c in df.columns]
    n_cols = [c for c in ['DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n'] if c in df.columns]

    df['score_Machiavellianism'] = df[m_cols].sum(axis=1, min_count=len(m_cols))
    df['score_Psychopathy'] = df[p_cols].sum(axis=1, min_count=len(p_cols))
    df['score_Narcissism'] = df[n_cols].sum(axis=1, min_count=len(n_cols))
    df['score_DarkCore_Total'] = df[present_dtdd].sum(axis=1, min_count=len(present_dtdd))

    # 6. Compute composite scores for all external scales (item‑level sums)
    for prefix, composite_name in ALL_SCALE_PREFIXES.items():
        # Find all columns starting with the prefix but not already a composite
        sub_items = [c for c in df.columns if c.startswith(prefix) and not c.endswith(('sum', 'Total'))]
        if not sub_items:
            if prefix == 'BFI_E_':
                logging.warning(f"No BFI‑E items found in {sample_id}. Extraversion will be missing.")
                continue
            else:
                logging.warning(f"No items found for prefix {prefix}. Skipping composite {composite_name}.")
                continue

        # Convert to numeric
        for c in sub_items:
            df[c] = pd.to_numeric(df[c], errors='coerce')

        # Compute sum with at least 80% non‑missing items
        required_count = int(len(sub_items) * 0.8) if len(sub_items) > 0 else 1
        df[composite_name] = df[sub_items].sum(axis=1, min_count=max(1, required_count))
        logging.info(f"Computed {composite_name} from {len(sub_items)} items in {sample_id}.")

    df['sample_origin'] = sample_id
    logging.info(f"Finished cleaning {sample_id}: retained {len(df)} / {initial_n} rows.")
    return df

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
def main():
    logging.info("===============================================================")
    logging.info(" DT³ PHASE 1 (REMEDIATED): Data Preprocessing")
    logging.info("===============================================================")

    # Input file mapping (from OSF conversion)
    file_map = {
        'sample_1_community': os.path.join(PROCESSED_DIR, "imported_data_expro_filtred.csv"),
        'sample_2_student': os.path.join(PROCESSED_DIR, "imported_data_filtred_2.csv"),
        'sample_3_representative': os.path.join(PROCESSED_DIR, "imported_data_filtred_3.csv")
    }

    # Verify input files exist and log hashes
    for sid, path in file_map.items():
        if not os.path.exists(path):
            raise FatalPreprocessingError(f"Required input file missing: {path}")
        logging.info(f"Cryptographic Hash ({sid}): {hash_file(path)}")

    # Clean each sample and collect
    cleaned_dfs = []
    for sid, path in file_map.items():
        raw_df = pd.read_csv(path, low_memory=False)
        c_df = clean_sample(raw_df, sid)
        cleaned_dfs.append(c_df)

    # Concatenate all samples (sample_origin column preserves separation)
    master_df = pd.concat(cleaned_dfs, ignore_index=True)

    # Final validation
    if master_df.empty:
        raise FatalPreprocessingError("Master dataset is empty after cleaning. Cannot continue.")
    if 'BFI_E_sum' not in master_df.columns:
        logging.critical("BFI_E_sum is missing from the master dataset. "
                         "Narcissism distinctiveness analyses will be severely limited. "
                         "This limitation MUST be disclosed in the manuscript.")
    else:
        logging.info("BFI_E_sum successfully constructed and included.")

    master_path = os.path.join(PROCESSED_DIR, "dt3_master_dataset.csv")
    master_df.to_csv(master_path, index=False)
    logging.info(f"Saved master dataset to {master_path} with shape {master_df.shape}")

    # -------------------------------------------------------------------------
    # TEST‑RETEST PREPARATION (unchanged logic)
    # -------------------------------------------------------------------------
    pre_path = os.path.join(PROCESSED_DIR, "data_DTDD_pretest.csv")
    post_path = os.path.join(PROCESSED_DIR, "data_DTDD_retest.csv")
    if os.path.exists(pre_path) and os.path.exists(post_path):
        pre = pd.read_csv(pre_path)
        post = pd.read_csv(post_path)

        # Pivot from long to wide: each participant (code) has a row per item
        pre_w = pre.drop_duplicates(subset=['code', 'question_name'])\
                    .pivot(index='code', columns='question_name', values='value').reset_index()
        post_w = post.drop_duplicates(subset=['code', 'question_name'])\
                     .pivot(index='code', columns='question_name', values='value').reset_index()

        # Merge T1 and T2 on participant code
        tr_df = pd.merge(pre_w, post_w, on='code', suffixes=('_T1', '_T2'))
        tr_path = os.path.join(PROCESSED_DIR, "dt3_test_retest.csv")
        tr_df.to_csv(tr_path, index=False)
        logging.info(f"Saved test‑retest dataset to {tr_path} with {len(tr_df)} matched pairs.")
    else:
        logging.warning("Test‑retest files not found. Baseline ICC cannot be computed.")

    logging.info("=== PHASE 1 EXECUTION SUCCESSFULLY COMPLETED ===")

if __name__ == "__main__":
    try:
        main()
    except FatalPreprocessingError as e:
        logging.fatal(f"PIPELINE HALTED DUE TO FATAL PREPROCESSING ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        logging.fatal(f"UNEXPECTED FAILURE: {e}", exc_info=True)
        sys.exit(1)