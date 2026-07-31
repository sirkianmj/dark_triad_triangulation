import os
import sys
import time
import subprocess
import pandas as pd

print("="*80)
print("     THE DARK TRIAD TRIANGULATION PROJECT (DT³)")
print("     MASTER PIPELINE AUTOMATION & STRICT VERIFICATION SUITE")
print("="*80)

start_time = time.time()

# Define the exact sequential pipeline stages (skipping manuscript generation)
pipeline_stages = [
    ("Phase 1: Preprocessing & Data Quality Pipeline", "scripts/01_data_preprocessing.py", ["data/processed/dt3_master_dataset.csv", "data/processed/dt3_test_retest_dataset.csv"]),
    ("Phase 2: Baseline Psychometrics & Reliability", "scripts/02_baseline_reproduction.py", ["results/baseline_reliability.csv"]),
    ("Phase 2: Exact Hypothesis Regressions (H1-H9)", "scripts/03_nomological_regression.py", ["results/baseline_ols_regressions.csv"]),
    ("Phase 2: Confirmatory Factor Analysis (CFA)", "scripts/03b_cfa_reproduction.py", ["results/baseline_cfa_fit.csv"]),
    ("Phase 3: Layer 1 12-Item GGM Network Psychometrics", "scripts/04_network_psychometrics.py", ["results/figures/layer1_ggm_network.png"]),
    ("Phase 3: Layer 1 Full 76-Item Space GGM Network", "scripts/04b_full_layer1_expansion.py", ["results/figures/layer1_full_ggm_network.png"]),
    ("Phase 3: Layer 1 TDA Kepler Mapper Topology", "scripts/05_topological_data_analysis.py", ["results/figures/layer1_mapper_topology.html"]),
    ("Phase 4: Layer 2 PyTorch Multi-Task Neural Net", "scripts/06_multitask_neural_network.py", ["results/shared_trunk_multitask_net.pt", "results/multitask_data_spec.npz"]),
    ("Phase 4: Layer 2 Multi-Head SHAP Attribution", "scripts/07_shap_attribution.py", ["results/shap_head_importance.csv"]),
    ("Phase 4: Layer 2 CKA Representational Geometry", "scripts/08_cka_rsa_analysis.py", ["results/cka_representational_similarity.csv", "results/figures/layer2_cka_similarity.png"]),
    ("Phase 4: Layer 2 Symbolic Genetic Programming", "scripts/09_symbolic_regression.py", ["results/symbolic_discovered_equations.csv"]),
    ("Phase 4: Layer 2 XGBoost Gradient Boosting", "scripts/10_xgboost_nam_crosscheck.py", ["results/xgboost_performance_summary.csv"]),
    ("Phase 5: Layer 3 PC Constraint-Based Causal DAG", "scripts/11_causal_discovery.py", ["results/causal_parents_summary.csv"]),
    ("Phase 5: Layer 3 Counterfactual Perturbations", "scripts/12_counterfactual_explanations.py", ["results/counterfactual_perturbation_summary.csv"]),
    ("Phase 6: Layer 4 LLM S-BERT Item Embeddings", "scripts/13_semantic_triangulation.py", ["results/semantic_item_embeddings_clusters.csv", "results/figures/layer4_semantic_dendrogram.png"]),
    ("Phase 6: Layer 4 Three-Way Triangulation Matrix", "scripts/13b_full_triangulation_matrix.py", ["results/three_way_triangulation_matrix.csv"]),
    ("Phase 7: Layer 5 Formal SDI Permutation Test", "scripts/14_shap_divergence_index.py", ["results/formal_shap_divergence_index.csv"]),
    ("Phase 7: Layer 5 Rashomon Set & Conformal Bounds", "scripts/15_rashomon_conformal_bounds.py", ["results/rashomon_set_robustness.csv", "results/conformal_prediction_bounds.csv"]),
    ("Phase 7: Layer 5 Local SHAP Subtype Discovery", "scripts/16_person_centered_subtypes.py", ["results/person_centered_subtypes_summary.csv", "results/figures/layer5_subtype_profiles.png"]),
    ("Phase 7: Layer 5 Cross-Sample Replication & Interactions", "scripts/16b_phase7_expansion.py", ["results/cross_sample_replication_summary.csv", "results/shap_interaction_pairs_summary.csv"]),
    ("Phase 8: Master Synthesis & Triangulation Matrix", "scripts/17_synthesis_matrix.py", ["results/master_synthesis_matrix.csv"]),
    ("Single-File Export: Complete Project Bundle", "scripts/export_full_project.py", ["DT3_FULL_PROJECT_DUMP.txt"])
]

execution_audit = []

for idx, (stage_name, script_path, expected_artifacts) in enumerate(pipeline_stages, 1):
    print("\n" + "="*80)
    print(f"[{idx}/{len(pipeline_stages)}] EXECUTING: {stage_name}")
    print(f"    Script: {script_path}")
    print("="*80)
    
    if not os.path.exists(script_path):
        print(f" [ERROR] Script '{script_path}' not found! Halting pipeline.")
        sys.exit(1)
        
    t0 = time.time()
    result = subprocess.run([sys.executable, script_path], capture_output=False, text=True)
    t_elapsed = time.time() - t0
    
    if result.returncode != 0:
        print(f"\n [FAILURE] {stage_name} crashed with exit code {result.returncode}!")
        execution_audit.append({'Stage': stage_name, 'Script': script_path, 'Status': 'FAILED', 'Time_s': round(t_elapsed, 1)})
        sys.exit(1)
        
    missing_artifacts = [art for art in expected_artifacts if not os.path.exists(art) or os.path.getsize(art) == 0]
            
    if missing_artifacts:
        print(f"\n [FAILURE] Missing or empty output artifacts: {missing_artifacts}")
        execution_audit.append({'Stage': stage_name, 'Script': script_path, 'Status': 'FAILED (MISSING ARTIFACTS)', 'Time_s': round(t_elapsed, 1)})
        sys.exit(1)
        
    print(f"\n [VERIFIED PASS] {stage_name} completed in {t_elapsed:.1f}s.")
    execution_audit.append({'Stage': stage_name, 'Script': script_path, 'Status': 'VERIFIED PASS', 'Time_s': round(t_elapsed, 1)})

total_elapsed = time.time() - start_time

print("\n\n" + "="*80)
print("     MASTER PIPELINE AUTOMATION & VERIFICATION REPORT")
print("="*80)

audit_df = pd.DataFrame(execution_audit)
print(audit_df.to_string(index=False))

print("\n" + "="*80)
print(f"  ALL {len(pipeline_stages)} PIPELINE STAGES COMPLETED & VERIFIED WITH 100% SUCCESS!")
print(f"  Total End-to-End Pipeline Execution Time: {total_elapsed/60.0:.2f} minutes")
print("="*80)
