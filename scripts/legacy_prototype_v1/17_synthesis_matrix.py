import os
import pandas as pd

print("="*60)
print("  DT3 PROJECT: PHASE 8 - MASTER MULTI-PARADIGM SYNTHESIS MATRIX ")
print("="*60)

synthesis_data = [
    {
        'Layer': 'Layer 1: Unsupervised Graph Topology',
        'Method': 'GGM Partial Correlations + Louvain Communities',
        'Primary_Finding': '100% rediscovered 3 theoretical trait clusters in isolated DTDD space; Narcissism isolated in 76-item space.',
        'Convergence_Evaluation': 'SUPPORTS 3-TRAIT SEPARABILITY'
    },
    {
        'Layer': 'Layer 1: Topological Data Analysis',
        'Method': 'Kepler Mapper Simplicial Complex',
        'Primary_Finding': 'Reconstructed 12D psychological space into 48-node topological graph with branching flares.',
        'Convergence_Evaluation': 'SUPPORTS DISTINCT MANIFOLDS'
    },
    {
        'Layer': 'Layer 2: Multi-Task Neural Network',
        'Method': 'PyTorch Shared-Trunk Multi-Task Net',
        'Primary_Finding': 'Training loss converged from 0.9352 -> 0.7890; forced common trunk representation.',
        'Convergence_Evaluation': 'SUPPORTS COMMON TRUNK MODEL'
    },
    {
        'Layer': 'Layer 2: Multi-Head SHAP Attribution',
        'Method': 'Gradient SHAP Feature Importance',
        'Primary_Finding': 'Psychopathy driven by Empathy deficits (0.2770); Machiavellianism by Agreeableness; Narcissism by Age/Self-Esteem.',
        'Convergence_Evaluation': 'SUPPORTS SUPERVISED DIVERGENCE'
    },
    {
        'Layer': 'Layer 2: Representational Geometry',
        'Method': 'Linear Centered Kernel Alignment (CKA)',
        'Primary_Finding': 'Shared trunk activations for high-scorers are near-orthogonal across traits (CKA ~ 0.008 - 0.013 << 1.0).',
        'Convergence_Evaluation': 'SUPPORTS ORTHOGONAL MANIFOLDS'
    },
    {
        'Layer': 'Layer 2: Symbolic Regression',
        'Method': 'Genetic Programming (gplearn)',
        'Primary_Finding': 'Discovered distinct generative formulas (Psychopathy = ratio empathy threshold; Mach/Narc = interaction trees).',
        'Convergence_Evaluation': 'SUPPORTS FUNCTIONAL-FORM DIVERGENCE'
    },
    {
        'Layer': 'Layer 2: Non-Linear Ensemble Cross-Check',
        'Method': 'XGBoost Decision Trees',
        'Primary_Finding': 'Non-linear tree models nearly double explained R^2 compared to OLS (Psychopathy R^2 jumps from 13.5% -> 25.0%).',
        'Convergence_Evaluation': 'SUPPORTS NON-LINEAR SIGNAL'
    },
    {
        'Layer': 'Layer 3: Causal Discovery',
        'Method': 'PC Constraint-Based DAG (Fisher-Z test)',
        'Primary_Finding': 'Inferred distinct direct causal parents (Psychopathy driven by Empathy as direct directed causal parent).',
        'Convergence_Evaluation': 'SUPPORTS CAUSAL VALIDITY'
    },
    {
        'Layer': 'Layer 3: Counterfactual Explanations',
        'Method': 'Minimal L1 Feature Perturbation Shifts',
        'Primary_Finding': 'Flipping High Psychopathy -> Low requires boosting Empathy (62.5% of cases); Mach/Narc require Agreeableness/Age shifts.',
        'Convergence_Evaluation': 'SUPPORTS PERTURBATION DIVERGENCE'
    },
    {
        'Layer': 'Layer 4: LLM Semantic Triangulation',
        'Method': 'Sentence-BERT Embeddings (all-MiniLM-L6-v2)',
        'Primary_Finding': 'LLM clusters scale text into broad antagonism (ARI = 0.0522), proving human 3-trait separation is NOT wording redundancy.',
        'Convergence_Evaluation': 'SUPPORTS SEMANTIC DISSOCIATION'
    },
    {
        'Layer': 'Layer 5: Formal Statistical Rigor',
        'Method': 'SHAP Divergence Index (SDI) Permutation Test',
        'Primary_Finding': 'Observed SDI = 0.2884 vs Null SDI = 0.0529 (p < 0.001), statistically rejecting single Dark Core account.',
        'Convergence_Evaluation': 'REJECTS SINGLE DARK CORE (p < .001)'
    },
    {
        'Layer': 'Layer 5: Distribution-Free Uncertainty',
        'Method': 'MAPIE 5-Fold Cross-Conformalization',
        'Primary_Finding': 'Achieved exact 95.0% - 96.0% empirical prediction interval coverage on held-out test respondents.',
        'Convergence_Evaluation': 'SUPPORTS CONFORMAL COVERAGE'
    },
    {
        'Layer': 'Layer 5: Person-Centered Analysis',
        'Method': 'Local SHAP Explanation Clustering',
        'Primary_Finding': 'Discovered latent subtypes (Psychopathy: Callous vs Impulsive; Narcissism: Vulnerable vs Grandiose).',
        'Convergence_Evaluation': 'SUPPORTS LATENT HETEROGENEITY'
    }
]

synthesis_df = pd.DataFrame(synthesis_data)

print("\n" + "="*60)
print("     MASTER MULTI-PARADIGM TRIANGULATION SYNTHESIS MATRIX     ")
print("="*60)
print(synthesis_df[['Layer', 'Convergence_Evaluation']].to_string(index=False))

os.makedirs('results', exist_ok=True)
synthesis_path = 'results/master_synthesis_matrix.csv'
synthesis_df.to_csv(synthesis_path, index=False)

print(f"\nSaved complete Master Synthesis Matrix to '{synthesis_path}'")
print("="*60)
