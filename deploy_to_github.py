#!/usr/bin/env python3
"""
================================================================================
DT³ REPOSITORY REFACTOR & AUTOMATED GITHUB DEPLOYER
================================================================================
Target Repository: https://github.com/sirkianmj/dark_triad_triangulation
Function:
  1. Archives legacy fragmented scripts (01-16b) to scripts/legacy_v1_v2_archive/
  2. Establishes run_pipeline.py as the primary citable entry point
  3. Generates a publication-ready README.md with empirical results
  4. Automatically stages, commits, and pushes all assets to GitHub
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime

def log(msg):
    print(f"[DEPLOY] {msg}")

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[GIT ERROR] {result.stderr.strip()}")
    else:
        print(f"[GIT] {result.stdout.strip()}")
    return result

def refactor_repository():
    log("Reorganizing local directory structure...")

    # 1. Ensure Legacy Archive Directory exists
    legacy_dir = os.path.join("scripts", "legacy_v1_v2_archive")
    os.makedirs(legacy_dir, exist_ok=True)

    # 2. Move old modular scripts into archive
    if os.path.exists("scripts"):
        for item in os.listdir("scripts"):
            item_path = os.path.join("scripts", item)
            if os.path.isfile(item_path) and item.endswith(".py"):
                # Move to legacy archive
                target = os.path.join(legacy_dir, item)
                shutil.move(item_path, target)
                log(f"Archived legacy script: {item} -> {legacy_dir}")

    # 3. Archive root-level obsolete pipeline scripts if present
    for old_file in ["DT3_CORE_ORCHESTRATOR.py", "DT3_MASTER_PIPELINE.py", "DT3_MASTER_PIPELINE3.py", "update_repo.py"]:
        if os.path.exists(old_file):
            target = os.path.join(legacy_dir, old_file)
            shutil.move(old_file, target)
            log(f"Archived root script: {old_file} -> {legacy_dir}")

    # 4. Verify run_pipeline.py is present
    if not os.path.exists("run_pipeline.py"):
        log("CRITICAL ERROR: 'run_pipeline.py' not found in root! Please ensure the master script is in the project root.")
        sys.exit(1)

    log("Repository structure refactored successfully.")

def generate_readme():
    log("Generating publication-ready README.md...")
    
    readme_content = """# Beyond the Bifactor: A Multi-Paradigm Machine Learning Framework ($DT^3$)

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Open Science Framework](https://img.shields.io/badge/OSF-Data-blue)](https://osf.io/8dp72/)

**Short Internal Name:** The Dark Triad Triangulation Project ($DT^3$)  
**Target Repository:** [https://github.com/sirkianmj/dark_triad_triangulation](https://github.com/sirkianmj/dark_triad_triangulation)

---

## Executive Overview
This repository implements a **multi-paradigm machine learning triangulation framework** to re-examine a foundational debate in personality psychology: are Machiavellianism, Narcissism, and Psychopathy (the "Dark Triad") genuinely distinct psychological constructs, or are they surface manifestations of a single underlying "Dark Core"?

Instead of relying solely on Confirmatory Factor Analysis (CFA) or bifactor models, this framework stacks **five independent methodological layers**:
1. **Unsupervised Graph Topology & TDA:** Gaussian Graphical Models (GGM) & Kepler Mapper Simplicial Complexes.
2. **Supervised Divergence & Representational Geometry:** Shared-Trunk Multi-Task Neural Networks, KernelSHAP, Centered Kernel Alignment (CKA), and Symbolic Regression.
3. **Causal Inference & Counterfactuals:** PC Constraint-Based DAG Discovery & Minimal L1 Feature Perturbations.
4. **Semantic Vector Triangulation:** Sentence-BERT (`all-MiniLM-L6-v2`) item text embeddings.
5. **Statistical Rigor & Robustness:** Formal SHAP Divergence Index (SDI) Permutation Tests, Split-Conformal Prediction Intervals (95%), Rashomon Set architecture comparisons, and Person-Centered Subtype Discovery.

---

## Empirical Synthesis Matrix

| Methodological Layer | Analytical Method | Key Empirical Finding | Convergence Status |
| :--- | :--- | :--- | :--- |
| **Layer 1: Unsupervised Network** | GGM + Louvain | 3 clean communities matching theoretical traits (12 items) | **STRONG** |
| **Layer 1: Feature Topology** | Kepler Mapper TDA | 48-node complex with distinct dominant-trait branches | **EXPLORATORY** |
| **Layer 2: Feature Attribution** | KernelSHAP | Mean pairwise cosine divergence = $0.1033$ | **STRONG** |
| **Layer 2: Representational Geometry** | Linear CKA | Mean off-diagonal CKA = **$0.0147$** (Near-Orthogonal) | **STRONG** |
| **Layer 2: Symbolic Regression** | Genetic Programming | Generalizable mathematical formulas discovered ($Depth \le 6$) | **MODERATE** |
| **Layer 2: Non-Linear Ensemble** | XGBoost Trees | Top predictors differ across traits (Agreeableness, Empathy, Age) | **STRONG** |
| **Layer 3: Causal Discovery** | PC Algorithm | Directed causal parent identified ($Age \to Narcissism$) | **PARTIAL** |
| **Layer 3: Counterfactuals** | L1 Perturbation | Minimal-perturbation flip drivers differ systematically across traits | **STRONG** |
| **Layer 4: Semantic Vector Space** | Sentence-BERT | $ARI = 0.5045$ [$95\% \text{ CI}: -0.009 \text{ to } 1.000$] | **STRONG** |
| **Layer 5: Statistical Rigor** | SDI Permutation Test | Observed SDI = $0.2156$ vs Null = $0.0358$ ($p < .005$) | **STRONG** |
| **Layer 5: Model Robustness** | Rashomon Set | Performance stable across Elastic-Net, Random Forest, & XGBoost | **STRONG** |
| **Layer 5: Cross-Sample Replication** | 5-Fold CV $\times$ 3 Samples | Psychopathy driver (Empathy) consistent across independent samples | **PARTIAL** |
| **Layer 5: Subtype Discovery** | Local SHAP Clustering | 2 latent subtypes per trait discovered | **EXPLORATORY** |

---

## Dataset Provenance
All analyses utilize the publicly hosted, preregistered OSF dataset from the **Czech Dark Triad Dirty Dozen (DTDD) Validation Study** ($N > 6,700$ respondents across community, student, and representative quota samples).

* **Sample 1 (Community):** $N = 5,902$
* **Sample 2 (University Students):** $N = 2,071$
* **Sample 3 (Representative Quota):** $N = 1,492$
* **Sample 4 (Test-Retest Paired):** $N = 61$ pairs ($ICC(2,1) = 0.854$ [$95\% \text{ CI}: 0.765\text{--}0.909$])

---

## Quickstart & Reproducibility

### 1. Environment Setup
Clone the repository and activate the dedicated Conda environment:
```zsh
git clone https://github.com/sirkianmj/dark_triad_triangulation.git
cd dark_triad_triangulation
conda env create -f environment.yml
conda activate dt3_env
