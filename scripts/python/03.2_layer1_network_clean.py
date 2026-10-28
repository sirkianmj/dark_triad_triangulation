#!/usr/bin/env python3
"""
Phase 3.2 (additive, reviewer item 2): 88-item network, clean re-estimation.
- Community sample only (no pooled pairwise-deletion across samples)
- 82 clean items (drops 3 TEQ_CON_* reverse-scored variants and 3 experimental DTDD_1g/1i/1ma)
- Complete-case preference; fallback to pairwise WITHIN community only
- Louvain tested at multiple resolution parameters gamma
SAFETY: writes only layer1b_* CSVs. Does not overwrite layer1_* originals.
"""
import os, sys, logging, warnings
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import networkx as nx
import community as community_louvain
from sklearn.preprocessing import StandardScaler
from sklearn.covariance import graphical_lasso

PROCESSED, TABLES = "data/processed", "results/tables"
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(os.path.join(TABLES,"execution_audit.log"),mode='a'),
              logging.StreamHandler(sys.stdout)], force=True)

DTDD = [f"DTDD_{i}{s}" for s in 'mpn' for i in range(1,5)]
BFI = [f"BFI_{d}_{i}" for d,n in [('A',9),('C',9),('N',8),('O',10),('E',8)] for i in range(1,n+1)]
TEQ = [f"TEQ_{i}" for i in range(1,17)]
RSES = [f"RSES_{i}" for i in range(1,11)]
CLEAN_ITEMS = DTDD + BFI + TEQ + RSES

def make_pd(m, tol=1e-8):
    sym = (m + m.T) / 2.0
    w, v = np.linalg.eigh(sym)
    if np.all(w >= tol): return sym
    w[w < tol] = tol
    pd_m = v @ np.diag(w) @ v.T
    d = np.sqrt(np.diag(pd_m))
    return pd_m / np.outer(d, d)

def pairwise_corr(df, min_per_pair=10):
    cols = df.columns; P = len(cols)
    corr = np.eye(P); ns = np.zeros((P,P), dtype=int)
    for i in range(P):
        for j in range(i+1, P):
            mask = df.iloc[:,i].notna() & df.iloc[:,j].notna()
            n = mask.sum(); ns[i,j] = ns[j,i] = n
            if n >= min_per_pair:
                xi = df.iloc[:,i][mask].astype(float); xj = df.iloc[:,j][mask].astype(float)
                if xi.var() > 0 and xj.var() > 0:
                    r = np.corrcoef(xi, xj)[0,1]
                    if np.isfinite(r):
                        corr[i,j] = corr[j,i] = r; continue
            corr[i,j] = corr[j,i] = 0.0
    return corr, ns

def harmonic_mean(v):
    v = np.asarray(v); v = v[v>0]
    return len(v)/np.sum(1.0/v) if len(v) else 0.0

def ebic(logdet, trace, n, P, edges, gamma=0.5):
    nll = -n*(logdet - trace)
    pen = edges*np.log(n) + 4*gamma*edges*np.log(P)
    return nll + pen

def run(df, items, tag, min_complete=30):
    logging.info(f"=== Clean network: {tag} ===")
    logging.info(f"Items: {len(items)}  Cases: {len(df)}")
    complete = df[items].dropna()
    N_c = len(complete)
    logging.info(f"Complete cases: {N_c}")
    if N_c >= min_complete:
        X = StandardScaler().fit_transform(complete.astype(float).values)
        corr = np.corrcoef(X, rowvar=False); N_eff = N_c
        logging.info(f"Using complete-case correlation (N={N_eff}, P={len(items)})")
    else:
        corr, ns = pairwise_corr(df[items]); corr = make_pd(corr)
        off = ns[np.triu_indices_from(ns, k=1)]
        N_eff = harmonic_mean(off)
        logging.info(f"Pairwise fallback (effective N≈{N_eff:.0f}, P={len(items)})")
    P = corr.shape[0]
    # EBIC alpha search
    alphas = np.logspace(-3, 0, 40)
    best = (np.inf, None, None)
    for a in alphas:
        try:
            _, prec = graphical_lasso(corr, alpha=a, max_iter=1000)
            sign, logdet = np.linalg.slogdet(prec)
            if not np.isfinite(logdet) or sign <= 0: continue
            trace = np.sum(corr * prec)
            off_diag = prec - np.diag(np.diag(prec))
            edges = np.count_nonzero(off_diag) / 2
            e = ebic(logdet, trace, N_eff, P, edges)
            if e < best[0]: best = (e, a, prec)
        except Exception: continue
    if best[2] is None:
        logging.error("EBICglasso failed"); return None
    e_val, alpha, prec = best
    diag = np.diag(prec); pcorr = -prec * np.outer(1/np.sqrt(diag), 1/np.sqrt(diag))
    np.fill_diagonal(pcorr, 1.0)
    G = nx.Graph(); G.add_nodes_from(items)
    for i in range(P):
        for j in range(i+1, P):
            if abs(pcorr[i,j]) > 0.01:
                G.add_edge(items[i], items[j], weight=abs(pcorr[i,j]))
    logging.info(f"Min EBIC={e_val:.2f} at alpha={alpha:.4f}, edges={G.number_of_edges()}")

    # Louvain at multiple gammas
    results = []
    for gamma in [0.5, 1.0, 1.5, 2.0, 3.0]:
        partition = community_louvain.best_partition(
            G, weight='weight', resolution=gamma, random_state=42)
        n_comm = len(set(partition.values()))
        dtdd_comm = set(partition[it] for it in DTDD if it in partition)
        dtdd_clusters = len(dtdd_comm)
        # Are all 12 DTDD in a single community?
        dtdd_single = 1 if dtdd_clusters == 1 else 0
        # Purity: how many non-DTDD items are in the same community as DTDD?
        if len(dtdd_comm) == 1:
            shared = sum(1 for it, c in partition.items() if c in dtdd_comm and it not in DTDD)
        else:
            shared = 0
        results.append({
            'Gamma': gamma, 'Communities': n_comm,
            'DTDD_Clusters': dtdd_clusters,
            'DTDD_All_One': dtdd_single,
            'NonDTDD_in_DTDD_comm': shared,
            'Total_Edges': G.number_of_edges(),
            'Alpha_L1': round(alpha, 4),
            'Effective_N': round(N_eff, 0),
        })
        logging.info(f"  γ={gamma}: {n_comm} comms; DTDD → {dtdd_clusters} cluster(s)")

    # Save per-gamma summary
    out = os.path.join(TABLES, f"layer1b_network_summary_{tag}.csv")
    pd.DataFrame(results).to_csv(out, index=False)
    # Save community assignment at default gamma=1.0
    default_part = community_louvain.best_partition(
        G, weight='weight', resolution=1.0, random_state=42)
    pd.DataFrame([{'Node': k, 'Community': v} for k, v in default_part.items()]) \
      .to_csv(os.path.join(TABLES, f"layer1b_communities_{tag}.csv"), index=False)
    logging.info(f"Wrote layer1b_network_summary_{tag}.csv and layer1b_communities_{tag}.csv")
    return results

def main():
    logging.info("="*63)
    logging.info(" PHASE 3.2: Clean 88-item network re-estimation")
    logging.info("="*63)
    df = pd.read_csv(os.path.join(PROCESSED,"dt3_master_dataset.csv"), low_memory=False)
    community = df[df['sample_origin']=='sample_1_community'].copy()
    logging.info(f"Community sample: {len(community)} rows")

    # Confirm all 82 items exist
    missing = [it for it in CLEAN_ITEMS if it not in community.columns]
    if missing:
        logging.error(f"Missing items: {missing}")
        sys.exit(1)
    logging.info(f"All {len(CLEAN_ITEMS)} clean items present")

    results = run(community, CLEAN_ITEMS, "clean_community")
    if results is None:
        logging.error("Network fit failed"); sys.exit(2)

    # Compare to baseline (original 88-item pooled)
    print("\n" + "="*63)
    print(" COMPARISON: Clean vs Baseline 88-item network")
    print("="*63)
    print(f"  Baseline (original 88-item pooled pairwise):")
    print(f"    20 communities; DTDD items all in 1 community")
    print(f"    N_complete=0 → pairwise-deletion → non-PD → projection artifact")
    print(f"  Clean re-estimation (community-only, 82 clean items):")
    for r in results:
        print(f"    γ={r['Gamma']:.1f}: {r['Communities']} communities; "
              f"DTDD → {r['DTDD_Clusters']} cluster(s); "
              f"All-one={bool(r['DTDD_All_One'])}")
    print("="*63)
    print("\n  INTERPRETATION:")
    if any(r['DTDD_All_One'] for r in results):
        print("    ✓ DTDD items collapse to one community in clean data →")
        print("      'Dark Core Collapse' confirmed on corrected specification.")
    else:
        print("    ⚠ DTDD items do NOT collapse to one community in clean data →")
        print("      'Dark Core Collapse' was an artifact of pooled pairwise-deletion.")
        print("      Manuscript must revise this claim.")
    print("="*63)

if __name__ == "__main__":
    main()
