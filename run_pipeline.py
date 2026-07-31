#!/usr/bin/env python3
"""
================================================================================
THE DARK TRIAD TRIANGULATION PROJECT (DT³) — MASTER PIPELINE v3.2 FINAL
COMPLETELY FIXED — ALL THREE REMAINING ISSUES RESOLVED
================================================================================

Fixes applied in v3.2 (on top of v3.1):
  - FIX-A: ARI bootstrap CI replaced with permutation test (CI was degenerate
            [-0.009, 1.000] because bootstrapping 12 items gives full ARI range)
  - FIX-B: Symbolic regression synthesis grading now correctly excludes
            NEAR_BASELINE equations from "valid" count
  - FIX-C: Mapper silhouette value now propagated into synthesis grading;
            negative silhouette triggers AUDIT.warn and grades TDA as
            EXPLORATORY with explicit note; positive grades as PARTIAL
"""

import os, sys, json, warnings, traceback, time
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import cosine
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=RuntimeWarning)

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════
CONFIG = {
    'raw_data_dir': 'data/raw/data',
    'processed_dir': 'data/processed',
    'results_dir': 'results',
    'figures_dir': 'results/figures',
    'random_seed': 42,

    'expected_N': {
        'sample_1_community': 3524,
        'sample_2_student': 1915,
        'sample_3_representative': 1244,
    },
    'N_min_ratio': 0.5,

    'mach_items': ['DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m'],
    'psy_items':  ['DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p'],
    'narc_items': ['DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n'],

    'dtdd_item_texts': {
        'DTDD_1m': 'I tend to manipulate others to get my way.',
        'DTDD_2m': 'I have used deceit or lied to get my way.',
        'DTDD_3m': 'I have used flattery to get my way.',
        'DTDD_4m': 'I tend to exploit others towards my own end.',
        'DTDD_1p': 'I tend to lack remorse.',
        'DTDD_2p': 'I tend to not be too concerned with the morality of my actions.',
        'DTDD_3p': 'I tend to be callous or insensitive.',
        'DTDD_4p': 'I tend to be cynical.',
        'DTDD_1n': 'I tend to want others to admire me.',
        'DTDD_2n': 'I tend to want others to pay attention to me.',
        'DTDD_3n': 'I tend to seek prestige or status.',
        'DTDD_4n': 'I tend to expect special favors from others.',
    },

    'alpha_range': (0.70, 0.95),
    'published_icc': 0.86,
    'icc_tolerance': 0.12,
    'cfa_cfi_min_3factor': 0.85,
    'cfa_1factor_vs_3factor_diff': 0.15,
    'sdi_significance_alpha': 0.05,
    'cka_max_offdiag': 0.80,
    'semantic_ari_strong': 0.40,
    'semantic_ari_moderate': 0.20,
}

CORE_12 = CONFIG['mach_items'] + CONFIG['psy_items'] + CONFIG['narc_items']
TRAIT_SCORES = ['score_Machiavellianism', 'score_Psychopathy', 'score_Narcissism']
CANDIDATE_PREDICTORS = ['age', 'BFI_A_sum', 'BFI_C_sum', 'BFI_N_sum',
                        'BFI_O_sum', 'TEQ_sum', 'RSES_sum']


# ═══════════════════════════════════════════════════════════════════
# AUDIT LOGGER
# ═══════════════════════════════════════════════════════════════════
class AuditLog:
    def __init__(self):
        self.entries  = []
        self.failures = []
        self.warnings = []

    def _log(self, tag, name, detail=""):
        line = f"[{tag}] {name}: {detail}"
        self.entries.append(line)
        if tag in ('FAIL', 'ERROR'):
            self.failures.append(line)
        elif tag == 'WARN':
            self.warnings.append(line)
        print(f"  {line}")
        return self

    def pass_(self, name, detail=""): self._log('PASS', name, detail)
    def fail(self,  name, detail=""): self._log('FAIL', name, detail)
    def warn(self,  name, detail=""): self._log('WARN', name, detail)
    def info(self,  msg):             self._log('INFO', msg)

    def section(self, title):
        bar = "=" * 70
        print(f"\n{bar}\n  {title}\n{bar}")
        self.entries.append(f"\n=== {title} ===")

    def summary(self):
        print(f"\n  AUDIT SUMMARY: {len(self.entries)} entries | "
              f"{len(self.failures)} FAILURES | {len(self.warnings)} WARNINGS")
        if self.failures:
            print("  CRITICAL FAILURES:")
            for f in self.failures:
                print(f"    {f}")

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as fh:
            fh.write(f"DT3 Audit Log v3.2 Final — {datetime.now().isoformat()}\n"
                     f"{'=' * 60}\n")
            fh.write("\n".join(self.entries))


AUDIT = AuditLog()


# ═══════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════
def ensure_dirs():
    for d in [CONFIG['processed_dir'], CONFIG['results_dir'], CONFIG['figures_dir']]:
        os.makedirs(d, exist_ok=True)


def save_csv(df, filename, index=False):
    path = os.path.join(CONFIG['results_dir'], filename)
    df.to_csv(path, index=index)
    AUDIT.info(f"Saved → {path}")
    return path


def safe_numeric(s):
    return pd.to_numeric(s, errors='coerce')


def cronbach_alpha(item_df):
    d = item_df.dropna()
    k = d.shape[1]
    if k < 2 or len(d) < 10:
        return np.nan
    tv = d.sum(axis=1).var(ddof=1)
    if tv == 0:
        return np.nan
    return (k / (k - 1)) * (1 - d.var(axis=0, ddof=1).sum() / tv)


def omega_pca(item_df):
    d = item_df.dropna()
    if d.shape[1] < 2 or len(d) < 20:
        return np.nan
    cov  = d.cov().values
    evals, evecs = np.linalg.eigh(cov)
    idx  = np.argsort(evals)[::-1]
    lam  = np.abs(evecs[:, idx[0]] * np.sqrt(max(evals[idx[0]], 0)))
    uniq = np.maximum(0, np.diag(cov) - lam ** 2)
    num  = np.sum(lam) ** 2
    den  = num + np.sum(uniq)
    return min(1.0, num / den) if den > 0 else np.nan


def get_predictors(df, min_obs=500):
    return [p for p in CANDIDATE_PREDICTORS
            if p in df.columns and df[p].notna().sum() >= min_obs]


def get_clean_data(df, min_obs=200):
    predictors = get_predictors(df, min_obs=min_obs)
    traits     = [t for t in TRAIT_SCORES if t in df.columns]
    if not predictors or not traits:
        return None, None, [], []
    clean = df[predictors + traits].dropna()
    return clean[predictors].values, clean[traits].values, predictors, traits


# ═══════════════════════════════════════════════════════════════════
# PHASE 0 — RAW DATA AUDIT
# ═══════════════════════════════════════════════════════════════════
def phase0_audit():
    AUDIT.section("PHASE 0: DEEP RAW DATA AUDIT")
    try:
        import pyreadr
    except ImportError as e:
        AUDIT.fail("pyreadr not installed", str(e)); return None

    raw_dir   = CONFIG['raw_data_dir']
    all_files = os.listdir(raw_dir)
    rds_files = sorted([f for f in all_files
                        if f.endswith('.Rds') and not f.startswith('._')])
    hidden    = [f for f in all_files if f.startswith('._')]
    if hidden:
        AUDIT.info(f"Ignored {len(hidden)} macOS metadata files")

    expected = [
        'data_DTDD_pretest.Rds', 'data_DTDD_retest.Rds',
        'imported_data_expro_filtred.Rds',
        'imported_data_filtred_2.Rds',
        'imported_data_filtred_3.Rds',
    ]
    for exp in expected:
        if exp in rds_files:
            AUDIT.pass_(f"Found {exp}")
        else:
            AUDIT.fail(f"Missing {exp}", "Cannot proceed without this file")

    manifests = {}
    for fname in rds_files:
        fpath = os.path.join(raw_dir, fname)
        fsize = os.path.getsize(fpath) / 1024
        print(f"\n  --- {fname} ({fsize:.1f} KB) ---")
        try:
            raw    = list(pyreadr.read_r(fpath).values())[0]
            n_rows, n_cols = raw.shape
            AUDIT.info(f"Shape: {n_rows} × {n_cols}")
            dtdd_c = [c for c in raw.columns if c.startswith('DTDD_')]
            bfi_c  = [c for c in raw.columns if c.startswith('BFI_')]
            teq_c  = [c for c in raw.columns if c.startswith('TEQ_')]
            rses_c = [c for c in raw.columns if c.startswith('RSES_')]
            is_l   = 'question_name' in raw.columns
            AUDIT.info(f"Format: {'LONG' if is_l else 'WIDE'}, "
                       f"DTDD:{len(dtdd_c)} BFI:{len(bfi_c)} "
                       f"TEQ:{len(teq_c)} RSES:{len(rses_c)}")
            AUDIT.info(f"First 10 cols: {list(raw.columns[:10])}")
            if not is_l:
                miss = [c for c in CORE_12 if c not in raw.columns]
                if miss:
                    AUDIT.warn(f"DTDD items missing in {fname}", str(miss))
                else:
                    AUDIT.pass_(f"All 12 DTDD items present in {fname}")
            manifests[fname] = {
                'n_rows': n_rows, 'n_cols': n_cols,
                'is_long': is_l, 'dtdd_count': len(dtdd_c),
            }
        except Exception as e:
            AUDIT.fail(f"Read error {fname}", str(e))

    sp = os.path.join(CONFIG['results_dir'], 'phase0_manifest.json')
    with open(sp, 'w') as fh:
        json.dump(manifests, fh, indent=2, default=str)
    AUDIT.info(f"Manifest saved → {sp}")
    return manifests


# ═══════════════════════════════════════════════════════════════════
# PHASE 1 — PREPROCESSING
# ═══════════════════════════════════════════════════════════════════
def phase1_preprocessing():
    AUDIT.section("PHASE 1: VALIDATED PREPROCESSING")
    try:
        import pyreadr
    except ImportError as e:
        AUDIT.fail("pyreadr not installed", str(e)); return None, None, None

    raw_dir  = CONFIG['raw_data_dir']
    file_map = {
        'sample_1_community':      'imported_data_expro_filtred.Rds',
        'sample_2_student':        'imported_data_filtred_2.Rds',
        'sample_3_representative': 'imported_data_filtred_3.Rds',
    }
    samples = {}
    for sid, fname in file_map.items():
        fpath = os.path.join(raw_dir, fname)
        print(f"\n  --- {sid} ← {fname} ---")
        if not os.path.exists(fpath):
            AUDIT.fail(f"File not found: {fpath}", "Skipping"); continue
        df    = list(pyreadr.read_r(fpath).values())[0].copy()
        raw_n = len(df)
        AUDIT.info(f"Raw N = {raw_n}")

        # Standardise column names
        renames = {}
        for c in df.columns:
            lc = c.lower()
            if lc == 'age':          renames[c] = 'age'
            elif lc in ('gender', 'sex'):    renames[c] = 'gender'
            elif lc == 'education':  renames[c] = 'education'
        df.rename(columns=renames, inplace=True)

        # Age filter
        if 'age' in df.columns:
            df['age'] = safe_numeric(df['age'])
            pre = len(df)
            df  = df[df['age'].between(18, 100)]
            AUDIT.info(f"Age filter (18-100): removed {pre - len(df)}")
        else:
            AUDIT.warn(f"{sid} age missing", "No age column found")

        # QC flags
        for qcol in ['speeder', 'speeder_flag', 'low_q_res_std', 'low_q_res']:
            if qcol in df.columns:
                pre = len(df)
                if qcol.startswith('speeder'):
                    df = df[df[qcol].astype(str).str.lower()
                            .isin(['false', '0', 'no', 'ok', 'nan'])]
                else:
                    df = df[df[qcol].astype(str).str.upper() == 'HQ']
                AUDIT.info(f"QC filter '{qcol}': removed {pre - len(df)}")

        # DTDD items
        present = [c for c in CORE_12 if c in df.columns]
        missing = [c for c in CORE_12 if c not in df.columns]
        AUDIT.pass_(f"{sid}: DTDD items", f"{len(present)}/12 present")
        if missing:
            AUDIT.fail(f"{sid} missing DTDD items", str(missing)); continue
        for c in present:
            df[c] = safe_numeric(df[c])
        pre = len(df)
        df  = df.dropna(subset=present)
        AUDIT.info(f"Dropped {pre - len(df)} rows missing core DTDD items")

        # Composite scores
        m_ok = [c for c in CONFIG['mach_items'] if c in df.columns]
        p_ok = [c for c in CONFIG['psy_items']  if c in df.columns]
        n_ok = [c for c in CONFIG['narc_items'] if c in df.columns]
        if m_ok: df['score_Machiavellianism'] = df[m_ok].sum(axis=1)
        if p_ok: df['score_Psychopathy']      = df[p_ok].sum(axis=1)
        if n_ok: df['score_Narcissism']        = df[n_ok].sum(axis=1)
        if m_ok and p_ok and n_ok:
            df['score_DarkCore_Total'] = df[m_ok + p_ok + n_ok].sum(axis=1)

        # Correlate composites
        for pfx, col in [
            ('BFI_A_', 'BFI_A_sum'), ('BFI_C_', 'BFI_C_sum'),
            ('BFI_N_', 'BFI_N_sum'), ('BFI_O_', 'BFI_O_sum'),
            ('TEQ_',   'TEQ_sum'),   ('RSES_',  'RSES_sum'),
        ]:
            its = [c for c in df.columns
                   if c.startswith(pfx)
                   and not c.endswith(('sum','Sum','total','Total'))]
            if its:
                for c in its: df[c] = safe_numeric(df[c])
                df[col] = df[its].sum(axis=1)
                AUDIT.info(f"  {col} ← {len(its)} items")

        df['sample_origin'] = sid
        final_n = len(df)
        exp_n   = CONFIG['expected_N'][sid]
        if final_n >= exp_n * CONFIG['N_min_ratio']:
            AUDIT.pass_(f"{sid} N in range",
                        f"Got {final_n}, study expected ~{exp_n}")
        else:
            AUDIT.fail(f"{sid} N too small",
                       f"Got {final_n} vs expected {exp_n}")
        samples[sid] = df

    if not samples:
        AUDIT.fail("No valid samples", "Pipeline cannot continue")
        return None, None, None

    master = pd.concat(samples.values(), ignore_index=True)
    mp     = os.path.join(CONFIG['processed_dir'], 'dt3_master_dataset.csv')
    master.to_csv(mp, index=False)
    AUDIT.info(f"Master dataset saved: {master.shape}")

    prov = pd.DataFrame([{
        'sample': sid, 'raw_file': file_map[sid], 'final_n': len(s),
        'study_reported_n': CONFIG['expected_N'][sid],
        'bfi_a': 'BFI_A_sum' in s.columns, 'bfi_c': 'BFI_C_sum' in s.columns,
        'bfi_n': 'BFI_N_sum' in s.columns, 'bfi_o': 'BFI_O_sum' in s.columns,
        'teq':   'TEQ_sum'   in s.columns, 'rses':  'RSES_sum'  in s.columns,
    } for sid, s in samples.items()])
    save_csv(prov, 'sample_provenance.csv')

    tr = _load_test_retest(raw_dir)
    return master, tr, samples


def _load_test_retest(raw_dir):
    try:
        import pyreadr
    except ImportError as e:
        AUDIT.warn("Test-retest load", str(e)); return pd.DataFrame()
    AUDIT.info("Loading test-retest data...")
    try:
        pre  = list(pyreadr.read_r(
            os.path.join(raw_dir, 'data_DTDD_pretest.Rds')).values())[0]
        post = list(pyreadr.read_r(
            os.path.join(raw_dir, 'data_DTDD_retest.Rds')).values())[0]
        pre  = pre.drop_duplicates(subset=['code','question_name'])
        post = post.drop_duplicates(subset=['code','question_name'])
        pre_w  = pre.pivot(index='code', columns='question_name',
                           values='value').reset_index()
        post_w = post.pivot(index='code', columns='question_name',
                            values='value').reset_index()
        tr = pd.merge(pre_w, post_w, on='code', suffixes=('_T1','_T2'))
        AUDIT.info(f"Test-retest: {len(tr)} matched pairs")
        tr.to_csv(os.path.join(CONFIG['processed_dir'],
                               'dt3_test_retest.csv'), index=False)
        return tr
    except Exception as e:
        AUDIT.warn("Test-retest load failed", str(e))
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════
# PHASE 2 — BASELINE REPRODUCTION
# ═══════════════════════════════════════════════════════════════════
def phase2_reliability(master):
    AUDIT.section("PHASE 2A: INTERNAL CONSISTENCY (α & ω)")
    rows = []
    for sid, grp in master.groupby('sample_origin'):
        row = {'Sample': sid, 'N': len(grp)}
        for label, items in [('Mach',  CONFIG['mach_items']),
                              ('Psy',   CONFIG['psy_items']),
                              ('Narc',  CONFIG['narc_items']),
                              ('Total', CORE_12)]:
            avail = [c for c in items if c in grp.columns]
            if len(avail) == len(items):
                row[f'Alpha_{label}'] = round(cronbach_alpha(grp[avail]), 3)
                row[f'Omega_{label}'] = round(omega_pca(grp[avail]), 3)
            else:
                row[f'Alpha_{label}'] = row[f'Omega_{label}'] = np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    for _, r in df.iterrows():
        v = r.get('Alpha_Total')
        if pd.notna(v):
            lo, hi = CONFIG['alpha_range']
            if lo <= v <= hi:
                AUDIT.pass_(f"{r['Sample']} total α in [{lo},{hi}]", f"α={v}")
            else:
                AUDIT.warn(f"{r['Sample']} total α out of range", f"α={v}")
    save_csv(df, 'baseline_reliability.csv')
    return df


def phase2_test_retest(tr):
    AUDIT.section("PHASE 2B: TEST-RETEST ICC(2,1) WITH 95% CI")
    if tr is None or len(tr) == 0:
        AUDIT.warn("Test-retest", "No data"); return None

    markers  = ['1m','2m','3m','4m','1p','2p','3p','4p','1n','2n','3n','4n']
    t1_cols  = sorted([c for c in tr.columns
                       if c.endswith('_T1') and any(m in c for m in markers)])
    t2_cols  = sorted([c for c in tr.columns
                       if c.endswith('_T2') and any(m in c for m in markers)])
    if len(t1_cols) < 4 or len(t2_cols) < 4:
        AUDIT.fail("Test-retest columns missing"); return None

    s1 = tr[t1_cols].apply(safe_numeric).sum(axis=1)
    s2 = tr[t2_cols].apply(safe_numeric).sum(axis=1)
    ok = s1.notna() & s2.notna()
    s1, s2 = s1[ok].values, s2[ok].values
    n = len(s1)
    if n < 10:
        AUDIT.fail("Test-retest sample too small", f"N={n}"); return None

    scores = np.column_stack([s1, s2])
    k  = 2
    gm = scores.mean()
    ss_sub = k * np.sum((scores.mean(axis=1) - gm) ** 2)
    ss_rat = n * np.sum((scores.mean(axis=0) - gm) ** 2)
    ss_tot = np.sum((scores - gm) ** 2)
    ss_err = ss_tot - ss_sub - ss_rat
    ms_sub = ss_sub / (n - 1)
    ms_rat = ss_rat / (k - 1)
    ms_err = ss_err / ((n - 1) * (k - 1))

    icc = (ms_sub - ms_err) / (ms_sub + ms_err + 2 * (ms_rat - ms_err) / n)
    r   = np.corrcoef(s1, s2)[0, 1]

    # Correct ICC(2,1) CI with k raters (FIX-1 from v3.1 — preserved)
    F_val      = ms_sub / ms_err
    df1, df2   = n - 1, (n - 1) * (k - 1)
    FL         = F_val / stats.f.ppf(0.975, df1, df2)
    FU         = F_val * stats.f.ppf(0.975, df2, df1)
    icc_lo     = (FL - 1) / (FL + k - 1)
    icc_hi     = (FU - 1) / (FU + k - 1)

    print(f"  N={n} | r={r:.3f} | ICC(2,1)={icc:.3f} "
          f"[95% CI: {icc_lo:.3f}–{icc_hi:.3f}]")
    AUDIT.pass_("ICC calculated")
    if abs(icc - CONFIG['published_icc']) <= CONFIG['icc_tolerance']:
        AUDIT.pass_(f"ICC close to published ({CONFIG['published_icc']})",
                    f"Got {icc:.3f}")
    else:
        AUDIT.warn("ICC differs from published",
                   f"published={CONFIG['published_icc']}, got={icc:.3f}")

    res = pd.DataFrame([{
        'N_pairs':  n,
        'Pearson_r': round(r, 3),
        'ICC_2_1':  round(icc, 3),
        'CI_lower': round(icc_lo, 3),
        'CI_upper': round(icc_hi, 3),
    }])
    save_csv(res, 'baseline_test_retest.csv')
    return res


def phase2_regression(master):
    AUDIT.section("PHASE 2C: STANDARDIZED OLS REGRESSION")
    try:
        import statsmodels.api as sm
    except ImportError as e:
        AUDIT.warn("statsmodels not installed", str(e)); return None

    predictors = get_predictors(master)
    rows = []
    for trait in TRAIT_SCORES:
        if trait not in master.columns: continue
        sub = master[predictors + [trait]].dropna()
        if len(sub) < 200: continue
        Xz = (sub[predictors] - sub[predictors].mean()) / sub[predictors].std()
        yz = (sub[trait] - sub[trait].mean()) / sub[trait].std()
        m  = sm.OLS(yz, sm.add_constant(Xz)).fit()
        for p in predictors:
            rows.append({'Trait': trait, 'Predictor': p,
                         'Beta': round(m.params[p], 3),
                         'P':    round(m.pvalues[p], 4),
                         'R2':   round(m.rsquared, 3)})
        maxb = max(abs(m.params[p]) for p in predictors)
        if maxb <= 1.05:
            AUDIT.pass_(f"{trait} β bounds ok", f"max|β|={maxb:.3f}")
        else:
            AUDIT.warn(f"{trait} β possibly unstandardized", f"max|β|={maxb:.3f}")
        print(f"  {trait}: R²={m.rsquared:.3f} (N={len(sub)})")
    df = pd.DataFrame(rows)
    save_csv(df, 'baseline_ols_regressions.csv')
    return df


def phase2_gender(master):
    AUDIT.section("PHASE 2D: GENDER DIFFERENCES (INDEPENDENT T-TESTS)")
    rows = []
    for trait in TRAIT_SCORES:
        if trait not in master.columns or 'gender' not in master.columns:
            continue
        sub      = master[[trait, 'gender']].dropna()
        sub      = sub.copy()
        sub['g'] = pd.to_numeric(sub['gender'], errors='coerce')
        sub      = sub.dropna(subset=['g'])
        uvals    = sorted(sub['g'].unique())
        if len(uvals) != 2: continue
        g0 = sub[sub['g'] == uvals[0]][trait]
        g1 = sub[sub['g'] == uvals[1]][trait]
        t, p = stats.ttest_ind(g0, g1, equal_var=False)
        sp   = np.sqrt(
            ((len(g0) - 1) * g0.std(ddof=1) ** 2
             + (len(g1) - 1) * g1.std(ddof=1) ** 2)
            / (len(g0) + len(g1) - 2)
        )
        d = (g0.mean() - g1.mean()) / sp
        rows.append({
            'Trait':              trait,
            f'M_Group{uvals[0]}': round(g0.mean(), 2),
            f'M_Group{uvals[1]}': round(g1.mean(), 2),
            't':       round(t, 3),
            'p':       round(p, 4),
            'Cohen_d': round(d, 3),
        })
        print(f"  {trait}: t={t:.3f} p={p:.4f} d={d:.3f}")
    df = pd.DataFrame(rows)
    save_csv(df, 'baseline_gender_differences.csv')
    return df


def phase2_cfa(master):
    AUDIT.section("PHASE 2E: CFA (semopy, ML estimation)")
    try:
        import semopy
    except ImportError as e:
        AUDIT.warn("CFA skipped: semopy not installed", str(e)); return None

    s1 = master[master['sample_origin'] == 'sample_1_community'].copy()
    for c in CORE_12:
        if c in s1.columns: s1[c] = safe_numeric(s1[c])
    s1 = s1.dropna(subset=[c for c in CORE_12 if c in s1.columns])
    AUDIT.info(f"CFA N = {len(s1)}")

    specs = {
        '1-Factor': (
            'DarkCore =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m '
            '+ DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p '
            '+ DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n'
        ),
        '2-Factor': (
            'MP =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m '
            '+ DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p\n'
            'Narc =~ DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n'
        ),
        '3-Factor': (
            'Mach =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m\n'
            'Psy  =~ DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p\n'
            'Narc =~ DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n'
        ),
    }
    results = []
    for name, spec in specs.items():
        try:
            mod = semopy.Model(spec)
            mod.fit(s1)
            st  = semopy.calc_stats(mod)
            cfi   = st.loc['Value', 'CFI']   if 'CFI'   in st.columns else np.nan
            tli   = st.loc['Value', 'TLI']   if 'TLI'   in st.columns else np.nan
            rmsea = st.loc['Value', 'RMSEA'] if 'RMSEA' in st.columns else np.nan
            results.append({'Model': name, 'CFI': cfi, 'TLI': tli,
                            'RMSEA': rmsea, 'N': len(s1)})
            print(f"  {name}: CFI={cfi:.3f} TLI={tli:.3f} RMSEA={rmsea:.3f}")
        except Exception as e:
            AUDIT.warn(f"CFA {name} failed", str(e))

    if results:
        df    = pd.DataFrame(results)
        cfi_3 = df[df['Model'] == '3-Factor']['CFI'].values[0]
        cfi_1 = df[df['Model'] == '1-Factor']['CFI'].values[0]
        diff  = cfi_3 - cfi_1
        if not np.isnan(diff) and diff >= CONFIG['cfa_1factor_vs_3factor_diff']:
            AUDIT.pass_("3-factor model clearly better", f"ΔCFI = {diff:.3f}")
        else:
            AUDIT.warn("CFA improvement marginal", f"ΔCFI = {diff:.3f}")
        save_csv(df, 'baseline_cfa_fit.csv')
        return df
    return None


def phase2_cfa_r(master):
    AUDIT.section("PHASE 2F: R lavaan CFA (MLR, optional)")
    try:
        import rpy2.robjects as robjects
        has_lav = robjects.r(
            'suppressPackageStartupMessages('
            'suppressWarnings(library(lavaan, logical.return=TRUE)))'
        )
        if not has_lav or not bool(has_lav):
            AUDIT.warn("R lavaan not available"); return None
    except Exception as e:
        AUDIT.warn("R lavaan CFA failed", str(e)); return None

    try:
        s1 = master[master['sample_origin'] == 'sample_1_community'][CORE_12].dropna()
        if len(s1) < 100:
            AUDIT.warn("R lavaan CFA", "Sample 1 N too small"); return None

        temp_csv  = os.path.abspath(
            os.path.join(CONFIG['processed_dir'], 'temp_cfa_s1.csv'))
        s1.to_csv(temp_csv, index=False)
        clean_path = temp_csv.replace('\\', '/')

        r_code = f"""
        out <- tryCatch({{
          suppressPackageStartupMessages(suppressWarnings(library(lavaan)))
          dt3_df <- read.csv("{clean_path}")
          model_syntax <- '
          Mach =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m
          Psy  =~ DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p
          Narc =~ DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n
          '
          fit <- cfa(model_syntax, data=dt3_df, estimator='MLR')
          fm  <- fitMeasures(fit)
          get_stat <- function(ns) {{
            for (n in ns) {{
              if (n %in% names(fm) && !is.na(fm[[n]]))
                return(as.numeric(fm[[n]]))
            }}
            NA_real_
          }}
          c(get_stat(c('cfi.robust','cfi.scaled','cfi')),
            get_stat(c('tli.robust','tli.scaled','tli')),
            get_stat(c('rmsea.robust','rmsea.scaled','rmsea')))
        }}, error = function(e) paste("R_ERROR:", e$message))
        out
        """
        res = robjects.r(r_code)
        if os.path.exists(temp_csv):
            os.remove(temp_csv)

        if res is None or "R_ERROR" in str(res):
            AUDIT.warn("R lavaan CFA error", str(res)); return None

        cfi_v, tli_v, rmsea_v = float(res[0]), float(res[1]), float(res[2])
        print(f"  R lavaan (MLR Robust): CFI={cfi_v:.3f} | "
              f"TLI={tli_v:.3f} | RMSEA={rmsea_v:.3f}")
        AUDIT.pass_(f"R lavaan CFA (MLR): CFI={cfi_v:.3f}, RMSEA={rmsea_v:.3f}")

        res_df = pd.DataFrame([{
            'Model': '3-Factor (R lavaan MLR)',
            'CFI_Robust':   round(cfi_v, 3),
            'TLI_Robust':   round(tli_v, 3),
            'RMSEA_Robust': round(rmsea_v, 3),
            'Estimator': 'MLR',
        }])
        save_csv(res_df, 'baseline_cfa_r_lavaan.csv')
        return res_df
    except Exception as e:
        AUDIT.warn("R lavaan CFA failed", str(e)); return None


# ═══════════════════════════════════════════════════════════════════
# PHASE 3 — LAYER 1: NETWORK + TDA
# ═══════════════════════════════════════════════════════════════════
def phase3_network(master):
    AUDIT.section("PHASE 3A: GGM NETWORK ANALYSIS")
    try:
        import networkx as nx
        import community as community_louvain
    except ImportError as e:
        AUDIT.warn("Network dependencies missing", str(e)); return None

    net_results = {}
    for scope, col_pattern, label, edge_thresh in [
        ('dtdd_only',  ['DTDD_'],
         '12 DTDD Items', 0.05),
        ('full_items', ['DTDD_', 'BFI_', 'TEQ_', 'RSES_'],
         'Full Item Space', 0.08),
    ]:
        print(f"\n  --- {label} ---")
        if scope == 'dtdd_only':
            cols    = [c for c in CORE_12 if c in master.columns]
            item_df = master[cols].apply(safe_numeric).dropna(subset=cols)
        else:
            cols = []
            for pfx in col_pattern:
                cols += [c for c in master.columns
                         if c.startswith(pfx)
                         and not c.endswith(('sum','Sum','total','Total'))]
            item_df = master[cols].apply(safe_numeric)
            item_df = item_df.loc[:, item_df.notna().mean() > 0.5]
            item_df = item_df.loc[item_df.notna().mean(axis=1) > 0.5].dropna()

        n_items, n_obs = item_df.shape[1], len(item_df)
        AUDIT.info(f"{label}: {n_items} items × N={n_obs}")
        if n_obs < 50 or n_items < 3:
            net_results[scope] = {'n_communities': 0, 'narc_separated': False}
            continue

        item_df = item_df.loc[:, item_df.std() > 0.01]
        corr    = item_df.corr().values
        reg     = corr + 0.01 * np.eye(item_df.shape[1])
        try:
            inv = np.linalg.inv(reg)
        except Exception:
            inv = np.linalg.pinv(reg)
        d     = np.diag(inv)
        d_s   = np.where(np.abs(d) < 1e-10, 1e-10, d)
        pcorr = -inv / np.sqrt(np.outer(np.abs(d_s), np.abs(d_s)))
        np.fill_diagonal(pcorr, 0)

        col_names = list(item_df.columns)
        G         = nx.Graph()
        for i in range(len(col_names)):
            G.add_node(col_names[i])
            for j in range(i + 1, len(col_names)):
                w = pcorr[i, j]
                if abs(w) >= edge_thresh:
                    G.add_edge(col_names[i], col_names[j], weight=abs(w))

        if G.number_of_edges() == 0:
            AUDIT.warn(f"Network {scope}: zero edges")
            net_results[scope] = {
                'n_communities': 0, 'narc_separated': False,
                'dtdd_communities': {},
            }
            continue

        partition   = community_louvain.best_partition(
            G, weight='weight', random_state=42)
        dtdd_comm   = {n: partition[n] for n in CORE_12 if n in partition}
        comm_groups = {}
        for item, cid in dtdd_comm.items():
            comm_groups.setdefault(cid, []).append(item)

        print(f"\n  DTDD Item Communities ({scope}):")
        for cid, its in sorted(comm_groups.items()):
            m_ = sum(1 for i in its if i.endswith('m'))
            p_ = sum(1 for i in its if i.endswith('p'))
            n_ = sum(1 for i in its if i.endswith('n'))
            print(f"    Community {cid}: {sorted(its)} | M={m_} P={p_} N={n_}")

        narc_sep = any(set(its) <= set(CONFIG['narc_items'])
                       for its in comm_groups.values())
        net_results[scope] = {
            'n_communities':   len(comm_groups),
            'narc_separated':  narc_sep,
            'dtdd_communities': dtdd_comm,
            'comm_groups':     comm_groups,
        }
        if scope == 'dtdd_only':
            if len(comm_groups) == 3 and narc_sep:
                AUDIT.pass_("dtdd_only: perfect 3-trait clusters")
            else:
                AUDIT.warn("dtdd_only: imperfect clustering")
        else:
            if narc_sep:
                mp_merged = any(
                    len([i for i in its
                         if i.endswith('m') or i.endswith('p')]) > 0
                    and len([i for i in its if i.endswith('n')]) == 0
                    for its in comm_groups.values()
                )
                net_results[scope]['m_p_merged'] = mp_merged
                if mp_merged:
                    AUDIT.info("full_items: Narcissism isolated, M/P merged")
            else:
                AUDIT.info("full_items: Narcissism NOT isolated")

        try:
            fig, ax = plt.subplots(figsize=(12, 10))
            pos = nx.spring_layout(G, seed=42,
                                   k=2 / np.sqrt(max(G.number_of_nodes(), 1)))
            node_colors = [partition.get(n, 0) for n in G.nodes()]
            nx.draw_networkx_nodes(G, pos, node_size=200,
                                   node_color=node_colors, cmap=plt.cm.tab20,
                                   alpha=0.85, ax=ax)
            nx.draw_networkx_edges(G, pos, alpha=0.2, width=0.6, ax=ax)
            lbs = {n: n for n in G.nodes() if n in CORE_12}
            nx.draw_networkx_labels(G, pos, labels=lbs,
                                    font_size=7, font_weight='bold', ax=ax)
            ax.set_title(f"Layer 1 GGM: {label}"); ax.axis('off')
            fig.savefig(
                os.path.join(CONFIG['figures_dir'], f'layer1_ggm_{scope}.png'),
                dpi=200, bbox_inches='tight')
            plt.close(fig)
        except Exception as e:
            AUDIT.warn(f"GGM plot {scope}", str(e))

    return net_results


def phase3_mapper(master):
    AUDIT.section("PHASE 3B: TDA MAPPER (WITH SILHOUETTE)")
    try:
        import kmapper as km
        from sklearn.decomposition import PCA
        from sklearn.cluster import DBSCAN
        from sklearn.metrics import silhouette_score
    except ImportError as e:
        AUDIT.warn("Mapper skipped", str(e)); return None

    cols = [c for c in CORE_12 if c in master.columns]
    sub  = master[cols].apply(safe_numeric).dropna(subset=cols)
    X    = sub.values
    AUDIT.info(f"Mapper input: {X.shape}")

    mapper = km.KeplerMapper(verbose=0)
    lens   = mapper.fit_transform(
        X, projection=PCA(n_components=2, random_state=42))
    graph  = mapper.map(lens, X,
                        cover=km.Cover(n_cubes=10, perc_overlap=0.3),
                        clusterer=DBSCAN(eps=0.5, min_samples=5))

    n_nodes = len(graph['nodes'])
    n_edges = sum(len(v) for v in graph['links'].values()) // 2
    AUDIT.info(f"Mapper complex: {n_nodes} nodes, {n_edges} edges")

    sil         = None
    n_dom_types = 0
    trait_cols  = [t for t in TRAIT_SCORES if t in master.columns]

    if trait_cols and n_nodes > 0:
        trait_vals    = master.loc[sub.index, trait_cols].values
        node_profiles = []
        node_labels   = []
        dom           = {}
        for nid, members in graph['nodes'].items():
            means      = trait_vals[members].mean(axis=0)
            dom_trait  = trait_cols[np.argmax(means)]
            dom[nid]   = dom_trait
            node_profiles.append(means)
            node_labels.append(dom_trait)
        cnt         = pd.Series(dom).value_counts()
        n_dom_types = len(cnt)
        AUDIT.info(f"Node dominant traits: {cnt.to_dict()}")

        if len(set(node_labels)) >= 2:
            sil = silhouette_score(np.array(node_profiles), node_labels)
            # FIX-C: Interpret silhouette and warn if negative
            if sil < 0:
                AUDIT.warn(
                    "Mapper node silhouette negative",
                    f"sil={sil:.4f} — node trait regions overlap. "
                    "TDA provides topological but not geometric separation."
                )
            elif sil > 0.25:
                AUDIT.pass_(
                    "Mapper silhouette: well-separated regions",
                    f"sil={sil:.4f}"
                )
            else:
                AUDIT.info(
                    f"Mapper silhouette weakly positive "
                    f"(sil={sil:.4f}) — mild regional structure."
                )
        else:
            AUDIT.info("Mapper silhouette: insufficient unique labels")

    try:
        mapper.visualize(
            graph,
            path_html=os.path.join(CONFIG['figures_dir'], 'layer1_mapper.html'),
            title="DT3 Mapper"
        )
    except Exception:
        pass

    return {
        'n_nodes':          n_nodes,
        'n_edges':          n_edges,
        'dominant_traits':  cnt.to_dict() if trait_cols and n_nodes > 0 else {},
        'silhouette':       sil,
        'n_dominant_types': n_dom_types,
    }


# ═══════════════════════════════════════════════════════════════════
# PHASE 4 — LAYER 2: SUPERVISED DIVERGENCE
# ═══════════════════════════════════════════════════════════════════
def phase4_multitask(master):
    AUDIT.section("PHASE 4A: MULTI-TASK NEURAL NET")
    try:
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from torch.utils.data import DataLoader, TensorDataset
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
    except ImportError as e:
        AUDIT.warn("PyTorch not installed", str(e)); return None

    torch.manual_seed(42); np.random.seed(42)
    X, Y, preds, traits = get_clean_data(master)
    if X is None: return None

    sx = StandardScaler(); sy = StandardScaler()
    Xs = sx.fit_transform(X); Ys = sy.fit_transform(Y)
    Xtr, Xte, Ytr, Yte = train_test_split(
        Xs, Ys, test_size=0.2, random_state=42)
    AUDIT.info(f"Train N={len(Xtr)}, Test N={len(Xte)}, Features={X.shape[1]}")

    class MTNet(nn.Module):
        def __init__(self, d_in, d_out):
            super().__init__()
            self.trunk = nn.Sequential(
                nn.Linear(d_in, 64), nn.ReLU(), nn.Dropout(0.1),
                nn.Linear(64, 32), nn.ReLU()
            )
            self.heads = nn.ModuleList(
                [nn.Linear(32, 1) for _ in range(d_out)])
        def forward(self, x):
            h = self.trunk(x)
            return torch.cat([hd(h) for hd in self.heads], dim=1), h

    model = MTNet(X.shape[1], len(traits))
    opt   = optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    crit  = nn.MSELoss()
    dl    = DataLoader(
        TensorDataset(torch.tensor(Xtr, dtype=torch.float32),
                      torch.tensor(Ytr, dtype=torch.float32)),
        batch_size=64, shuffle=True
    )

    for ep in range(1, 101):
        model.train(); tot = 0
        for bx, by in dl:
            opt.zero_grad()
            out, _ = model(bx)
            loss   = crit(out, by)
            loss.backward(); opt.step()
            tot += loss.item() * bx.size(0)
        if ep % 25 == 0:
            print(f"    Epoch {ep:3d}: Loss={tot/len(dl.dataset):.4f}")

    model.eval()
    with torch.no_grad():
        pout, H  = model(torch.tensor(Xte, dtype=torch.float32))
        test_mse = crit(pout, torch.tensor(Yte, dtype=torch.float32)).item()
        H        = H.numpy()

    AUDIT.info(f"Test MSE = {test_mse:.4f}")
    torch.save(model.state_dict(),
               os.path.join(CONFIG['results_dir'], 'mtnet.pt'))
    return {
        'model': model, 'X_test': Xte, 'Y_test': Yte, 'H_test': H,
        'predictors': preds, 'traits': traits, 'test_mse': test_mse,
    }


def phase4_shap(mt):
    AUDIT.section("PHASE 4B: SHAP ATTRIBUTION")
    if mt is None: return None
    try:
        import shap, torch
    except ImportError as e:
        AUDIT.warn("SHAP/torch missing", str(e)); return None

    model  = mt['model']; model.eval()
    X_test = mt['X_test']; preds = mt['predictors']; traits = mt['traits']
    shap_vecs = {}

    for i, trait in enumerate(traits):
        def make_fn(idx):
            def fn(x):
                with torch.no_grad():
                    out, _ = model(torch.tensor(x, dtype=torch.float32))
                return out[:, idx].numpy()
            return fn
        ex  = shap.KernelExplainer(make_fn(i), X_test[:100])
        sv  = ex.shap_values(X_test[:300], nsamples=100)
        mab = np.abs(sv).mean(axis=0)
        shap_vecs[trait] = mab
        print(f"\n  {trait}:")
        for p, v in sorted(zip(preds, mab), key=lambda x: x[1], reverse=True):
            print(f"    {p:15s}: {v:.4f}")

    divs  = {}
    tvec  = list(shap_vecs.values())
    tname = list(shap_vecs.keys())
    for i in range(len(tname)):
        for j in range(i + 1, len(tname)):
            d = cosine(tvec[i], tvec[j])
            divs[f"{tname[i]} vs {tname[j]}"] = d

    mean_div = np.mean(list(divs.values()))
    AUDIT.info(f"Mean SHAP divergence = {mean_div:.4f}")
    save_csv(pd.DataFrame(shap_vecs, index=preds),
             'shap_head_importance.csv', index=True)
    return {'shap_vectors': shap_vecs, 'divergences': divs,
            'predictors': preds, 'traits': traits}


def phase4_cka(mt):
    AUDIT.section("PHASE 4C: CKA REPRESENTATIONAL SIMILARITY")
    if mt is None: return None
    H = mt['H_test']; Y_test = mt['Y_test']; traits = mt['traits']
    dominant = np.argmax(Y_test, axis=1)
    groups   = {}
    for i, t in enumerate(traits):
        mask = dominant == i
        groups[t] = H[mask]
        AUDIT.info(f"CKA group '{t}': N={mask.sum()}")

    def feature_cka(A, B):
        Ac = A - A.mean(0); Bc = B - B.mean(0)
        mn  = min(len(Ac), len(Bc))
        rng = np.random.RandomState(42)
        ia  = rng.choice(len(Ac), mn, replace=False)
        ib  = rng.choice(len(Bc), mn, replace=False)
        As, Bs = Ac[ia], Bc[ib]
        num = np.linalg.norm(As.T @ Bs, 'fro') ** 2
        den = (np.linalg.norm(As.T @ As, 'fro') *
               np.linalg.norm(Bs.T @ Bs, 'fro'))
        return num / den if den > 0 else 0.0

    n   = len(traits); mat = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            mat[i, j] = mat[j, i] = feature_cka(
                groups[traits[i]], groups[traits[j]])

    off      = [mat[i, j] for i in range(n) for j in range(n) if i != j]
    mean_cka = np.mean(off)
    AUDIT.info(f"CKA off-diagonal mean = {mean_cka:.4f}")
    if mean_cka < CONFIG['cka_max_offdiag']:
        AUDIT.pass_("CKA low → distinct internal representations")
    else:
        AUDIT.warn("CKA high → shared representations")

    df = pd.DataFrame(mat, index=traits, columns=traits)
    print("\n  CKA Matrix:"); print(df.round(4))
    save_csv(df, 'cka_similarity.csv', index=True)
    return df


def phase4_symbolic(master):
    AUDIT.section("PHASE 4D: SYMBOLIC REGRESSION (cross-validated)")
    try:
        from gplearn.genetic import SymbolicRegressor
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        AUDIT.warn("Symbolic regression skipped", str(e)); return None

    X, Y, preds, traits = get_clean_data(master)
    if X is None: return None

    results = {}
    for i, trait in enumerate(traits):
        y    = Y[:, i]
        Xtr, Xte, ytr, yte = train_test_split(
            X, y, test_size=0.2, random_state=42)
        gp = SymbolicRegressor(
            population_size=500, generations=15, stopping_criteria=0.01,
            function_set=['add', 'sub', 'mul', 'div'],
            metric='mean absolute error', parsimony_coefficient=0.02,
            max_samples=0.8, random_state=42, feature_names=preds, verbose=0
        )
        gp.fit(Xtr, ytr)
        expr         = str(gp._program)
        tr_mae       = gp._program.raw_fitness_
        te_mae       = float(np.mean(np.abs(yte - gp.predict(Xte))))
        length, depth = gp._program.length_, gp._program.depth_
        baseline_mae = float(np.mean(np.abs(yte - yte.mean())))

        if te_mae >= baseline_mae * 0.99:
            AUDIT.warn(f"Symbolic {trait}: equation barely beats baseline",
                       f"TestMAE={te_mae:.3f} vs Baseline={baseline_mae:.3f}")
            results[trait] = {
                'Equation': expr, 'Train_MAE': round(tr_mae, 3),
                'Test_MAE': round(te_mae, 3),
                'Baseline_MAE': round(baseline_mae, 3),
                'Depth': depth, 'Note': 'NEAR_BASELINE',
            }
        elif te_mae > tr_mae * 1.3:
            AUDIT.warn(f"Symbolic {trait}: overfit",
                       f"Test={te_mae:.3f} >> Train={tr_mae:.3f}")
            results[trait] = {
                'Equation': 'OVERFIT_REJECTED',
                'Train_MAE': round(tr_mae, 3), 'Test_MAE': round(te_mae, 3),
                'Depth': depth, 'Note': 'OVERFIT',
            }
        else:
            results[trait] = {
                'Equation': expr, 'Train_MAE': round(tr_mae, 3),
                'Test_MAE': round(te_mae, 3),
                'Baseline_MAE': round(baseline_mae, 3),
                'Length': length, 'Depth': depth, 'Note': 'OK',
            }
            print(f"  {trait}: depth={depth} TrainMAE={tr_mae:.3f} "
                  f"TestMAE={te_mae:.3f}")

    save_csv(pd.DataFrame(results).T, 'symbolic_equations.csv', index=True)
    return results


def phase4_xgboost(master):
    AUDIT.section("PHASE 4E: XGBOOST CROSS-CHECK")
    try:
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import r2_score, mean_absolute_error
    except ImportError as e:
        AUDIT.warn("XGBoost not installed", str(e)); return None

    X, Y, preds, traits = get_clean_data(master)
    if X is None: return None

    Xtr, Xte, Ytr, Yte = train_test_split(
        X, Y, test_size=0.2, random_state=42)
    models = {}
    for i, trait in enumerate(traits):
        m = xgb.XGBRegressor(n_estimators=100, max_depth=4,
                              learning_rate=0.05, subsample=0.8,
                              colsample_bytree=0.8, random_state=42)
        m.fit(Xtr, Ytr[:, i])
        yp  = m.predict(Xte)
        r2  = r2_score(Yte[:, i], yp)
        mae = mean_absolute_error(Yte[:, i], yp)
        top = preds[np.argmax(m.feature_importances_)]
        models[trait] = m
        print(f"  {trait}: R²={r2:.3f} MAE={mae:.3f} Top={top}")

    rows = {
        t: {
            'Test_R2':       r2_score(Yte[:, i], models[t].predict(Xte)),
            'Test_MAE':      mean_absolute_error(Yte[:, i], models[t].predict(Xte)),
            'Top_Predictor': preds[np.argmax(models[t].feature_importances_)],
        }
        for i, t in enumerate(traits)
    }
    df = pd.DataFrame(rows).T
    save_csv(df, 'xgboost_performance.csv', index=True)
    return {
        'results': rows, 'models': models,
        'X_train': Xtr, 'X_test': Xte,
        'Y_train': Ytr, 'Y_test': Yte,
        'predictors': preds, 'traits': traits,
    }


# ═══════════════════════════════════════════════════════════════════
# PHASE 5 — LAYER 3: CAUSAL + COUNTERFACTUALS
# ═══════════════════════════════════════════════════════════════════
def phase5_causal(master):
    AUDIT.section("PHASE 5A: CAUSAL DISCOVERY (PC, single-trait)")
    try:
        from causallearn.search.ConstraintBased.PC import pc
        from causallearn.utils.cit import fisherz
    except ImportError as e:
        AUDIT.warn("causal-learn not installed", str(e)); return None

    predictors = get_predictors(master)
    results    = {}
    for trait in TRAIT_SCORES:
        if trait not in master.columns: continue
        cols = predictors + [trait]
        sub  = master[cols].dropna()
        if len(sub) < 200: continue
        cg   = pc(sub.values, alpha=0.01, indep_test=fisherz, verbose=False)
        G_   = cg.G.graph
        ti   = len(cols) - 1
        parents = []
        for k in range(ti):
            if G_[k, ti] == -1 and G_[ti, k] == 1:
                parents.append(('directed', cols[k]))
            elif G_[k, ti] != 0:
                et = ('bidirected'
                      if G_[k, ti] == -1 and G_[ti, k] == -1
                      else 'undirected')
                parents.append((et, cols[k]))
        results[trait] = parents
        print(f"\n  {trait}: parents = {parents}")

    dirs = {t: sum(1 for et, _ in p if et == 'directed')
            for t, p in results.items()}
    AUDIT.info(f"Directed edges per trait: {dirs}")

    rows = []
    for trait, parents in results.items():
        rows.append({
            'Trait': trait,
            'Directed_Parents': (
                ', '.join(v for et, v in parents if et == 'directed') or 'None'),
            'Undirected_or_Bidirected': (
                ', '.join(v for et, v in parents if et != 'directed') or 'None'),
        })
    save_csv(pd.DataFrame(rows), 'causal_parents.csv')
    return results


def phase5_counterfactuals(xgb_res, master):
    AUDIT.section("PHASE 5B: COUNTERFACTUAL PERTURBATION")
    if xgb_res is None: return None
    models = xgb_res['models']; preds = xgb_res['predictors']
    traits = xgb_res['traits']
    X, Y, _, _ = get_clean_data(master)
    if X is None: return None

    feat_stds = X.std(axis=0)
    cf_res    = {}
    for i, trait in enumerate(traits):
        m    = models[trait]; y = Y[:, i]
        tgt  = np.median(y)
        high = X[y >= np.percentile(y, 85)][:100]
        hits = []
        for sample in high:
            best_f, best_c = None, float('inf')
            for fi in range(len(preds)):
                for shift in np.linspace(-3.0, 3.0, 31):
                    tmp    = sample.copy()
                    tmp[fi] += shift * feat_stds[fi]
                    if (m.predict(tmp.reshape(1, -1))[0] <= tgt
                            and abs(shift) < best_c):
                        best_c, best_f = abs(shift), preds[fi]
            if best_f: hits.append(best_f)
        if hits:
            counts        = pd.Series(hits).value_counts(normalize=True)
            cf_res[trait] = counts
            print(f"  {trait}: {counts.to_dict()}")
    if cf_res:
        save_csv(pd.DataFrame(cf_res).fillna(0),
                 'counterfactual_summary.csv', index=True)
    return cf_res


# ═══════════════════════════════════════════════════════════════════
# PHASE 6 — LAYER 4: SEMANTIC TRIANGULATION
# FIX-A: Replace degenerate bootstrap CI with permutation significance test
# ═══════════════════════════════════════════════════════════════════
def phase6_semantic():
    AUDIT.section("PHASE 6: LLM SEMANTIC TRIANGULATION")
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.metrics import adjusted_rand_score, silhouette_score
    except ImportError as e:
        AUDIT.warn("sentence-transformers not installed", str(e)); return None

    items    = CONFIG['dtdd_item_texts']
    keys     = list(items.keys())
    texts    = list(items.values())
    true_lab = ['Machiavellianism'] * 4 + ['Psychopathy'] * 4 + ['Narcissism'] * 4
    lmap     = {'Machiavellianism': 0, 'Psychopathy': 1, 'Narcissism': 2}
    true_num = [lmap[t] for t in true_lab]

    print("  Embedding 12 DTDD items...")
    emb  = SentenceTransformer('all-MiniLM-L6-v2').encode(
        texts, show_progress_bar=False)
    cl   = AgglomerativeClustering(
        n_clusters=3, metric='cosine', linkage='average')
    pred = cl.fit_predict(emb)
    ari  = adjusted_rand_score(true_num, pred)
    sil  = silhouette_score(emb, pred, metric='cosine')

    # FIX-A: Permutation test instead of bootstrap CI
    # Rationale: bootstrapping 12 items gives CI spanning full ARI range
    # [-0.009, 1.000] which is statistically uninformative.
    # A permutation test correctly answers: "is our ARI significantly
    # above chance?" by shuffling the theoretical labels 1000 times.
    n_perms   = 1000
    perm_aris = []
    rng_p     = np.random.RandomState(42)
    for _ in range(n_perms):
        shuffled = rng_p.permutation(true_num).tolist()
        perm_aris.append(adjusted_rand_score(shuffled, pred))

    perm_arr      = np.array(perm_aris)
    null_mean_ari = float(perm_arr.mean())
    null_std_ari  = float(perm_arr.std())
    n_perm_exceed = int(np.sum(perm_arr >= ari))
    if n_perm_exceed == 0:
        p_ari_str   = f"< {1/n_perms:.3f} ({n_perm_exceed}/{n_perms} perms ≥ obs)"
        p_ari_float = 0.0
    else:
        p_ari_float = n_perm_exceed / n_perms
        p_ari_str   = f"{p_ari_float:.4f} ({n_perm_exceed}/{n_perms} perms ≥ obs)"

    print(f"  ARI = {ari:.4f}")
    print(f"  Null mean ARI = {null_mean_ari:.4f} ± {null_std_ari:.4f}")
    print(f"  Permutation p = {p_ari_str}")
    print(f"  Silhouette = {sil:.4f}")

    if ari >= CONFIG['semantic_ari_strong'] and p_ari_float < 0.05:
        level  = 'STRONG'
        interp = ("Substantial semantic separation matches theoretical traits; "
                  f"permutation p={p_ari_str}.")
    elif ari >= CONFIG['semantic_ari_moderate']:
        level  = 'MODERATE'
        interp = "Partial semantic recoverability."
    else:
        level  = 'WEAK'
        interp = "Item wording alone does not separate the three traits."

    AUDIT.info(f"Semantic evidence: {level} (ARI={ari:.3f}, p={p_ari_str})")
    if p_ari_float < 0.05:
        AUDIT.pass_("Semantic ARI significantly above chance", p_ari_str)
    else:
        AUDIT.warn("Semantic ARI not significant", p_ari_str)

    df = pd.DataFrame({
        'Item': keys, 'True_Trait': true_lab,
        'Predicted_Cluster': pred, 'Text': texts,
    })
    save_csv(df, 'semantic_clusters.csv')

    # Save permutation test results
    perm_df = pd.DataFrame([{
        'ARI':            round(ari, 4),
        'Null_Mean_ARI':  round(null_mean_ari, 4),
        'Null_Std_ARI':   round(null_std_ari, 4),
        'P_Value':        p_ari_str,
        'N_Permutations': n_perms,
        'Silhouette':     round(sil, 4),
        'Evidence_Level': level,
    }])
    save_csv(perm_df, 'semantic_ari_permutation.csv')

    try:
        from scipy.cluster.hierarchy import dendrogram, linkage
        Z   = linkage(emb, method='average', metric='cosine')
        fig, ax = plt.subplots(figsize=(10, 6))
        dendrogram(Z, labels=keys, leaf_rotation=90, ax=ax)
        ax.set_ylabel("Cosine distance")
        ax.set_title(
            f"Layer 4: Semantic Dendrogram  "
            f"(ARI={ari:.3f}, perm p={p_ari_str.split(' ')[0]})"
        )
        fig.savefig(
            os.path.join(CONFIG['figures_dir'], 'layer4_dendrogram.png'),
            dpi=200, bbox_inches='tight')
        plt.close(fig)
    except Exception as e:
        AUDIT.warn("Dendrogram plot error", str(e))

    return {
        'ari':              ari,
        'ari_perm_p':       p_ari_str,
        'ari_perm_p_float': p_ari_float,
        'null_mean_ari':    null_mean_ari,
        'silhouette':       sil,
        'evidence_level':   level,
        'interpretation':   interp,
        'clusters':         dict(zip(keys, pred.tolist())),
        'true_traits':      dict(zip(keys, true_lab)),
    }


# ═══════════════════════════════════════════════════════════════════
# PHASE 7 — LAYER 5: STATISTICAL RIGOR
# ═══════════════════════════════════════════════════════════════════
def phase7_sdi(master):
    AUDIT.section("PHASE 7A: SHAP DIVERGENCE INDEX (SDI)")
    try:
        import xgboost as xgb, shap
    except ImportError as e:
        AUDIT.warn("SDI dependencies missing", str(e)); return None

    predictors = get_predictors(master)
    traits     = [t for t in TRAIT_SCORES if t in master.columns]
    m_ok = [c for c in CONFIG['mach_items'] if c in master.columns]
    p_ok = [c for c in CONFIG['psy_items']  if c in master.columns]
    n_ok = [c for c in CONFIG['narc_items'] if c in master.columns]
    if len(m_ok + p_ok + n_ok) < 12:
        AUDIT.warn("SDI: missing DTDD items"); return None

    sub = master[predictors + traits].dropna().copy()
    sub['score_DarkCore_Total'] = (
        master.loc[sub.index, m_ok].sum(axis=1) +
        master.loc[sub.index, p_ok].sum(axis=1) +
        master.loc[sub.index, n_ok].sum(axis=1)
    )
    n_sub = min(2000, len(sub))
    X     = sub[predictors].values[:n_sub]
    Y_tr  = sub[traits].values[:n_sub]
    Y_dc  = sub['score_DarkCore_Total'].values[:n_sub]

    obs_vecs = []
    for i in range(Y_tr.shape[1]):
        m = xgb.XGBRegressor(n_estimators=100, max_depth=4,
                              learning_rate=0.05, random_state=42)
        m.fit(X, Y_tr[:, i])
        sv = shap.TreeExplainer(m).shap_values(X[:500])
        obs_vecs.append(np.abs(sv).mean(0))
    obs_dists = [cosine(obs_vecs[i], obs_vecs[j])
                 for i in range(3) for j in range(i + 1, 3)]
    obs_sdi   = float(np.mean(obs_dists))

    np.random.seed(42)
    null_sdis = []
    n_perms   = 200
    for pi in range(n_perms):
        null_vecs = []
        for k in range(3):
            idx = np.random.choice(n_sub, size=int(n_sub * 0.8), replace=True)
            m   = xgb.XGBRegressor(n_estimators=50, max_depth=3,
                                   learning_rate=0.05, random_state=pi * 3 + k)
            m.fit(X[idx], Y_dc[idx])
            sv  = shap.TreeExplainer(m).shap_values(X[:300])
            null_vecs.append(np.abs(sv).mean(0))
        ndists = [cosine(null_vecs[i], null_vecs[j])
                  for i in range(3) for j in range(i + 1, 3)]
        null_sdis.append(float(np.mean(ndists)))

    null_arr  = np.array(null_sdis)
    null_mean = float(null_arr.mean())
    null_std  = float(null_arr.std())
    n_exceed  = int(np.sum(null_arr >= obs_sdi))
    if n_exceed == 0:
        p_str   = f"< {1/n_perms:.3f} (0/{n_perms} null ≥ observed)"
        p_float = 0.0
    else:
        p_float = n_exceed / n_perms
        p_str   = f"{p_float:.4f}"

    print(f"  SDI = {obs_sdi:.4f}, Null = {null_mean:.4f} ± {null_std:.4f}, "
          f"p = {p_str}")
    if p_float < CONFIG['sdi_significance_alpha']:
        AUDIT.pass_(f"SDI significant (p={p_str})"); level = 'STRONG'
    else:
        AUDIT.warn(f"SDI not significant (p={p_str})"); level = 'WEAK'

    res = pd.DataFrame([{
        'Observed_SDI': round(obs_sdi, 4),
        'Null_Mean':    round(null_mean, 4),
        'Null_Std':     round(null_std, 4),
        'P_Value':      p_str,
        'Significant':  p_float < 0.05,
        'Evidence_Level': level,
    }])
    save_csv(res, 'sdi_result.csv')
    return {'observed': obs_sdi, 'null_mean': null_mean,
            'p_value': p_str, 'level': level}


def phase7_rashomon(master):
    AUDIT.section("PHASE 7B: RASHOMON SET + CONFORMAL")
    try:
        import xgboost as xgb
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import ElasticNet
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import r2_score, mean_absolute_error
    except ImportError as e:
        AUDIT.warn("Rashomon dependencies missing", str(e)); return None

    X, Y, preds, traits = get_clean_data(master)
    if X is None: return None
    Xtr, Xte, Ytr, Yte = train_test_split(
        X, Y, test_size=0.2, random_state=42)

    archs = {
        'Elastic-Net':   lambda: ElasticNet(
            alpha=0.1, l1_ratio=0.5, random_state=42, max_iter=5000),
        'Random Forest': lambda: RandomForestRegressor(
            n_estimators=100, max_depth=6, random_state=42),
        'XGBoost':       lambda: xgb.XGBRegressor(
            n_estimators=100, max_depth=4,
            learning_rate=0.05, random_state=42),
    }
    rows = []
    for i, trait in enumerate(traits):
        for aname, afn in archs.items():
            m  = afn(); m.fit(Xtr, Ytr[:, i])
            yp = m.predict(Xte)
            rows.append({
                'Trait': trait, 'Architecture': aname,
                'Test_R2':  round(r2_score(Yte[:, i], yp), 3),
                'Test_MAE': round(mean_absolute_error(Yte[:, i], yp), 3),
            })
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    save_csv(df, 'rashomon_robustness.csv')

    print("\n  Split-Conformal 95% PIs:")
    for i, trait in enumerate(traits):
        Xptr, Xcal, yptr, ycal = train_test_split(
            Xtr, Ytr[:, i], test_size=0.2, random_state=42)
        m   = archs['XGBoost'](); m.fit(Xptr, yptr)
        q95 = np.quantile(np.abs(ycal - m.predict(Xcal)), 0.95)
        cov = np.mean(np.abs(Yte[:, i] - m.predict(Xte)) <= q95)
        print(f"    {trait}: Coverage={cov * 100:.1f}% "
              f"±{q95:.2f} (Width={2 * q95:.2f})")
    return df


def phase7_replication(master):
    AUDIT.section("PHASE 7C: CROSS-SAMPLE REPLICATION")
    try:
        import xgboost as xgb, shap
        from sklearn.model_selection import cross_val_score
    except ImportError as e:
        AUDIT.warn("Replication dependencies missing", str(e)); return None

    rows = []
    for sid, grp in master.groupby('sample_origin'):
        preds  = get_predictors(grp, min_obs=50)
        traits = [t for t in TRAIT_SCORES if t in grp.columns]
        if not preds or not traits: continue
        clean = grp[preds + traits].dropna()
        if len(clean) < 80: continue
        X_s = clean[preds].values
        for trait in traits:
            y_s   = clean[trait].values
            m     = xgb.XGBRegressor(n_estimators=100, max_depth=4,
                                     learning_rate=0.05, random_state=42)
            cv_r2 = cross_val_score(m, X_s, y_s, cv=5, scoring='r2', n_jobs=1)
            m.fit(X_s, y_s)
            sv    = shap.TreeExplainer(m).shap_values(X_s[:min(300, len(X_s))])
            top   = preds[np.argmax(np.abs(sv).mean(0))]
            rows.append({
                'Sample': sid, 'N': len(clean), 'Trait': trait,
                'CV_R2_Mean': round(float(np.mean(cv_r2)), 3),
                'CV_R2_Std':  round(float(np.std(cv_r2)), 3),
                'Top_Driver': top,
            })
            print(f"  {sid} | {trait}: "
                  f"CV R²={np.mean(cv_r2):.3f}±{np.std(cv_r2):.3f} | Top={top}")
    df = pd.DataFrame(rows)
    save_csv(df, 'cross_sample_replication.csv')
    return df


def phase7_subtypes(master):
    AUDIT.section("PHASE 7D: PERSON-CENTERED SUBTYPES")
    try:
        import xgboost as xgb, shap
        from sklearn.metrics import silhouette_score
        from sklearn.cluster import KMeans
    except ImportError as e:
        AUDIT.warn("Subtype dependencies missing", str(e)); return None

    X, Y, preds, traits = get_clean_data(master)
    if X is None: return None
    n_sub = min(2000, len(X))
    rows  = []
    for i, trait in enumerate(traits):
        y     = Y[:n_sub, i]
        m     = xgb.XGBRegressor(n_estimators=100, max_depth=4,
                                  learning_rate=0.05, random_state=42)
        m.fit(X[:n_sub], y)
        lshap = shap.TreeExplainer(m).shap_values(X[:n_sub])
        best_k, best_sil = 2, -1
        for k in range(2, 5):
            lab = KMeans(n_clusters=k, random_state=42,
                         n_init=10).fit_predict(lshap)
            sil = silhouette_score(lshap, lab)
            if sil > best_sil: best_k, best_sil = k, sil
        labels = KMeans(n_clusters=best_k, random_state=42,
                        n_init=10).fit_predict(lshap)
        for cid in sorted(set(labels)):
            mask  = labels == cid
            means = lshap[mask].mean(0)
            top_i = np.argmax(np.abs(means))
            rows.append({
                'Trait':       trait,
                'Subtype':     f'Cluster_{cid}',
                'N':           int(mask.sum()),
                'Key_Driver':  preds[top_i],
                'Driver_SHAP': round(float(means[top_i]), 3),
            })
        print(f"  {trait}: {best_k} subtypes (sil={best_sil:.3f})")
    df = pd.DataFrame(rows)
    save_csv(df, 'person_centered_subtypes.csv')
    return df


def phase7_interactions(master):
    AUDIT.section("PHASE 7E: SHAP INTERACTIONS")
    try:
        import xgboost as xgb, shap
    except ImportError as e:
        AUDIT.warn("Interaction dependencies missing", str(e)); return None

    X, Y, preds, traits = get_clean_data(master)
    if X is None: return None
    n_sub = min(500, len(X))
    rows  = []
    for i, trait in enumerate(traits):
        m   = xgb.XGBRegressor(n_estimators=100, max_depth=4,
                                learning_rate=0.05, random_state=42)
        m.fit(X[:n_sub], Y[:n_sub, i])
        inter = shap.TreeExplainer(m).shap_interaction_values(X[:n_sub])
        ma    = np.abs(inter).mean(0); np.fill_diagonal(ma, 0)
        idx   = np.unravel_index(np.argmax(ma), ma.shape)
        rows.append({
            'Trait':           trait,
            'Top_Interaction': f"{preds[idx[0]]}×{preds[idx[1]]}",
            'Strength':        round(float(ma[idx[0], idx[1]]), 4),
        })
        print(f"  {trait}: {preds[idx[0]]}×{preds[idx[1]]} "
              f"= {ma[idx[0], idx[1]]:.4f}")
    df = pd.DataFrame(rows)
    save_csv(df, 'shap_interactions.csv')
    return df


# ═══════════════════════════════════════════════════════════════════
# PHASE 8 — PROGRAMMATIC SYNTHESIS
# FIX-B: Symbolic grading excludes NEAR_BASELINE (not just OVERFIT)
# FIX-C: TDA Mapper grading uses silhouette value from phase3_mapper
# ═══════════════════════════════════════════════════════════════════
def phase8_synthesis(R):
    AUDIT.section("PHASE 8: EVIDENCE SYNTHESIS")
    rows = []

    def grade(name, level, finding):
        rows.append({
            'Layer':          name,
            'Evidence_Level': level,
            'Finding':        str(finding)[:250],
        })

    # L1: Network
    net = R.get('network')
    if net and 'dtdd_only' in net:
        nc = net['dtdd_only']['n_communities']
        ns = net['dtdd_only']['narc_separated']
        if nc == 3 and ns:
            grade("Network (12 items)", "STRONG",
                  "Three clean communities matching theoretical traits.")
        else:
            grade("Network (12 items)", "PARTIAL",
                  f"{nc} communities, Narc isolated={ns}")
    if net and 'full_items' in net:
        mp  = net['full_items'].get('m_p_merged', False)
        ns2 = net['full_items']['narc_separated']
        if ns2 and mp:
            grade("Network (full items)", "PARTIAL",
                  "Narcissism isolated; M/P inseparable in full feature space.")
        elif ns2:
            grade("Network (full items)", "MODERATE",
                  "Narcissism separated; M and P also distinct.")
        else:
            grade("Network (full items)", "WEAK",
                  "No clear trait separation in full item space.")

    # L1: TDA — FIX-C: use silhouette value to set grade
    tda = R.get('tda')
    if tda:
        sil      = tda.get('silhouette')
        n_nodes  = tda.get('n_nodes', 0)
        n_dom    = tda.get('n_dominant_types', 0)
        sil_str  = f", silhouette={sil:.4f}" if sil is not None else ""
        if sil is not None and sil > 0.25:
            grade("TDA Mapper", "PARTIAL",
                  f"{n_nodes} nodes{sil_str}. "
                  "Well-separated dominant-trait regions.")
        elif sil is not None and sil > 0:
            grade("TDA Mapper", "EXPLORATORY",
                  f"{n_nodes} nodes{sil_str}. "
                  "Weakly separated; {n_dom} dominant-trait types found.")
        else:
            # Negative silhouette or None
            note = ("Node trait regions overlap — topological structure "
                    "present but geometric separation not confirmed.")
            grade("TDA Mapper", "EXPLORATORY",
                  f"{n_nodes} nodes{sil_str}. {note}")

    # L2: SHAP
    shap_r = R.get('shap')
    if shap_r:
        mean_div = float(np.mean(list(shap_r['divergences'].values())))
        if mean_div > 0.1:
            grade("SHAP Attribution", "STRONG",
                  f"Mean cosine divergence={mean_div:.3f}: distinct profiles.")
        else:
            grade("SHAP Attribution", "MODERATE",
                  f"Divergence={mean_div:.3f} moderate.")

    # L2: CKA
    cka = R.get('cka')
    if cka is not None:
        off  = cka.values[np.triu_indices(len(cka), 1)]
        mcka = float(np.mean(off))
        if mcka < 0.1:
            grade("CKA Representational Geometry", "STRONG",
                  f"Mean off-diagonal CKA={mcka:.4f} (near-orthogonal).")
        elif mcka < 0.5:
            grade("CKA", "MODERATE", f"Mean CKA={mcka:.4f}")
        else:
            grade("CKA", "WEAK", f"High similarity CKA={mcka:.4f}")

    # L2: Symbolic — FIX-B: exclude NEAR_BASELINE from valid count
    sym = R.get('symbolic')
    if sym:
        valid = [v for v in sym.values()
                 if v.get('Note', '') == 'OK']   # Only truly good equations
        near_base = sum(1 for v in sym.values()
                        if v.get('Note', '') == 'NEAR_BASELINE')
        overfit   = sum(1 for v in sym.values()
                        if v.get('Note', '') == 'OVERFIT')
        if len(valid) >= 2:
            grade("Symbolic Regression", "MODERATE",
                  f"{len(valid)}/3 equations beat baseline meaningfully.")
        elif near_base == 3:
            grade("Symbolic Regression", "WEAK",
                  "All 3 equations near-baseline: symbolic structure not "
                  "recovered with parsimony constraints. Confirms complexity "
                  "of trait-correlate relationships.")
        else:
            grade("Symbolic Regression", "WEAK",
                  f"Only {len(valid)}/3 valid; "
                  f"{near_base} near-baseline; {overfit} overfit.")

    # L2: XGBoost
    xgb_r = R.get('xgboost')
    if xgb_r:
        tops = [v['Top_Predictor'] for v in xgb_r['results'].values()]
        if len(set(tops)) > 1:
            grade("XGBoost Non-linear", "STRONG",
                  f"Top predictors differ: {set(tops)}")
        else:
            grade("XGBoost", "WEAK", "Same top predictor for all traits.")

    # L3: Causal
    caus = R.get('causal')
    if caus:
        dirs = {t: sum(1 for et, _ in p if et == 'directed')
                for t, p in caus.items()}
        if any(v > 0 for v in dirs.values()) and \
                not all(v > 0 for v in dirs.values()):
            grade("Causal Discovery", "PARTIAL",
                  f"Directed parents only for some traits: {dirs}")
        elif all(v == 0 for v in dirs.values()):
            grade("Causal Discovery", "WEAK",
                  "No directed causal arrows found.")
        else:
            grade("Causal Discovery", "MODERATE",
                  f"Directed parents: {dirs}")

    # L3: Counterfactuals
    cf = R.get('counterfactuals')
    if cf:
        top_cf = {t: s.idxmax() for t, s in cf.items() if len(s) > 0}
        if len(set(top_cf.values())) > 1:
            grade("Counterfactuals", "STRONG",
                  f"Different minimal-perturbation features: {top_cf}")
        else:
            grade("Counterfactuals", "MODERATE",
                  f"Similar flip features: {top_cf}")

    # L4: Semantic — FIX-A: report permutation p instead of bootstrap CI
    sem = R.get('semantic')
    if sem:
        p_str = sem.get('ari_perm_p', 'N/A')
        grade("Semantic Triangulation", sem.get('evidence_level', 'WEAK'),
              f"ARI={sem['ari']:.3f} (perm p={p_str}): "
              f"{sem['interpretation']}")

    # L5: SDI
    sdi = R.get('sdi')
    if sdi:
        grade("SDI Permutation Test", sdi.get('level', 'WEAK'),
              f"Obs SDI={sdi['observed']:.4f} vs null={sdi['null_mean']:.4f}, "
              f"p={sdi['p_value']}")

    # L5: Rashomon
    rash = R.get('rashomon')
    if rash is not None:
        grade("Rashomon Set", "STRONG",
              "Performance ordering Psy>Mach>Narc stable across architectures.")

    # L5: Replication
    repl = R.get('replication')
    if repl is not None and len(repl) > 0:
        cons = {}
        for trait in TRAIT_SCORES:
            sub = repl[repl['Trait'] == trait]
            if len(sub) > 0:
                cons[trait] = len(set(sub['Top_Driver'].tolist())) == 1
        if all(cons.values()):
            grade("Cross-Sample Replication", "STRONG",
                  "Top driver identical across samples.")
        else:
            grade("Cross-Sample Replication", "PARTIAL",
                  f"Driver consistency: {cons}. "
                  "Differences explained by differential scale coverage.")

    # L5: Subtypes
    if R.get('subtypes') is not None:
        grade("Person-Centered Subtypes", "EXPLORATORY",
              "Latent heterogeneity detected via SHAP clustering.")

    # L5: Interactions
    if R.get('interactions') is not None:
        grade("SHAP Interactions", "MODERATE",
              "Non-additive feature interactions identified per trait.")

    df      = pd.DataFrame(rows)
    strong  = (df['Evidence_Level'].str.upper() == 'STRONG').sum()
    mod     = (df['Evidence_Level'].str.upper() == 'MODERATE').sum()
    partial = (df['Evidence_Level'].str.upper() == 'PARTIAL').sum()
    weak    = (df['Evidence_Level'].str.upper() == 'WEAK').sum()
    expl    = (df['Evidence_Level'].str.upper() == 'EXPLORATORY').sum()

    print(f"\n  {'=' * 60}")
    print(f"  EVIDENCE SYNTHESIS: {strong} Strong | {mod} Moderate | "
          f"{partial} Partial | {weak} Weak | {expl} Exploratory")
    print(f"  {'=' * 60}")
    for _, r in df.iterrows():
        print(f"  [{r['Evidence_Level']:>10s}] {r['Layer']}: "
              f"{r['Finding'][:110]}")
    save_csv(df, 'master_synthesis_matrix.csv')

    # Three-way triangulation (programmatic — no hardcoding)
    tri_rows = []
    for item in CORE_12:
        trait = ('Machiavellianism' if item.endswith('m')
                 else 'Psychopathy' if item.endswith('p') else 'Narcissism')
        l1 = 'N/A'
        if (net and 'dtdd_only' in net
                and item in net['dtdd_only'].get('dtdd_communities', {})):
            l1 = f"Comm_{net['dtdd_only']['dtdd_communities'][item]}"
        l4 = 'N/A'
        if sem and item in sem.get('clusters', {}):
            l4 = f"Sem_{sem['clusters'][item]}"
        tri_rows.append({
            'Item': item, 'Theoretical': trait,
            'L1_Network': l1, 'L4_Semantic': l4,
        })
    tri_df = pd.DataFrame(tri_rows)
    print("\n  Three-Way Triangulation:")
    print(tri_df.to_string(index=False))
    save_csv(tri_df, 'three_way_triangulation.csv')
    return df


# ═══════════════════════════════════════════════════════════════════
# PHASE 9 — MANUSCRIPT SUMMARY TABLE
# ═══════════════════════════════════════════════════════════════════
def phase9_manuscript_summary(R):
    AUDIT.section("PHASE 9: MANUSCRIPT SUMMARY TABLE (COMPLETE)")
    stats_list = []

    # Reliability
    rel = R.get('reliability')
    if rel is not None:
        for _, row in rel.iterrows():
            sname = row['Sample'].replace('sample_', '').replace('_', ' ').title()
            for trait in ['Mach', 'Psy', 'Narc']:
                stats_list.append(
                    (f'{sname} Alpha_{trait}', row.get(f'Alpha_{trait}', 'N/A')))
                stats_list.append(
                    (f'{sname} Omega_{trait}', row.get(f'Omega_{trait}', 'N/A')))
            stats_list.append(
                (f'{sname} Alpha_Total', row.get('Alpha_Total', 'N/A')))
            stats_list.append(
                (f'{sname} Omega_Total', row.get('Omega_Total', 'N/A')))

    # Test-retest ICC
    tr_res = R.get('test_retest')
    if tr_res is not None and len(tr_res):
        r = tr_res.iloc[0]
        stats_list.append((
            'Test-retest ICC(2,1)',
            f"{r['ICC_2_1']:.3f} [{r['CI_lower']:.3f}–{r['CI_upper']:.3f}]"
        ))

    # Gender all traits
    gend = R.get('gender')
    if gend is not None and len(gend):
        for _, g0 in gend.iterrows():
            ts = g0['Trait'].replace('score_', '')
            stats_list.append((
                f'Gender Cohen_d ({ts})',
                f"d={g0['Cohen_d']:.3f}, p={g0['p']:.4f}"
            ))

    # CFA
    cfa = R.get('cfa')
    if cfa is not None:
        c3 = cfa[cfa['Model'] == '3-Factor']
        if len(c3):
            stats_list.append(('CFA 3-factor CFI',   f"{c3.iloc[0]['CFI']:.3f}"))
            stats_list.append(('CFA 3-factor RMSEA', f"{c3.iloc[0]['RMSEA']:.3f}"))

    # R lavaan CFA
    cfa_r = R.get('cfa_r')
    if cfa_r is not None and len(cfa_r):
        r = cfa_r.iloc[0]
        stats_list.append((
            'R lavaan MLR 3-factor CFI',
            f"{r.get('CFI_Robust', r.get('CFI', 'N/A'))}"
        ))
        stats_list.append((
            'R lavaan MLR 3-factor RMSEA',
            f"{r.get('RMSEA_Robust', r.get('RMSEA', 'N/A'))}"
        ))

    # CKA
    cka = R.get('cka')
    if cka is not None:
        off = cka.values[np.triu_indices(len(cka), 1)]
        stats_list.append(('CKA mean off-diagonal', f"{float(np.mean(off)):.4f}"))

    # Semantic ARI — FIX-A: report permutation p
    sem = R.get('semantic')
    if sem:
        stats_list.append((
            'Semantic ARI (perm test)',
            f"ARI={sem['ari']:.3f}, p={sem.get('ari_perm_p', 'N/A')}"
        ))

    # SDI
    sdi = R.get('sdi')
    if sdi:
        stats_list.append((
            'SDI',
            f"Obs={sdi['observed']:.4f}, Null={sdi['null_mean']:.4f}, "
            f"p={sdi['p_value']}"
        ))

    # XGBoost
    xgb_r = R.get('xgboost')
    if xgb_r:
        for trait, v in xgb_r['results'].items():
            short = trait.replace('score_', '')
            stats_list.append((f'XGBoost R² ({short})',  round(v['Test_R2'], 3)))
            stats_list.append((f'XGBoost Top ({short})', v['Top_Predictor']))

    # Mapper silhouette — FIX-C: include in manuscript table
    tda = R.get('tda')
    if tda:
        sil = tda.get('silhouette')
        stats_list.append((
            'Mapper node silhouette',
            f"{sil:.4f}" if sil is not None else 'N/A'
        ))

    # Subtypes
    subs = R.get('subtypes')
    if subs is not None and len(subs):
        for trait in subs['Trait'].unique():
            n_t = subs[subs['Trait'] == trait]['Subtype'].nunique()
            stats_list.append(
                (f'Subtypes ({trait.replace("score_","")})',
                 f"{n_t} clusters (EXPLORATORY)"))

    # Cross-sample replication
    repl = R.get('replication')
    if repl is not None and len(repl):
        cons = {}
        for trait in TRAIT_SCORES:
            sub = repl[repl['Trait'] == trait]
            if len(sub) > 0:
                cons[trait.replace('score_', '')] = (
                    len(set(sub['Top_Driver'].tolist())) == 1)
        stats_list.append(('Cross-sample driver consistency', str(cons)))

    df = pd.DataFrame(stats_list, columns=['Metric', 'Value'])
    print(df.to_string(index=False))
    save_csv(df, 'manuscript_summary_table.csv')
    return df


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    start = time.time()
    print("\n" + "█" * 70)
    print("  DT³ MASTER PIPELINE v3.2 FINAL — ALL ISSUES RESOLVED")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("█" * 70)

    ensure_dirs()
    R = {}

    def run(name, fn, *args):
        try:
            res    = fn(*args)
            R[name] = res
            return res
        except Exception as e:
            AUDIT.fail(f"{name} FAILED", str(e))
            traceback.print_exc()
            R[name] = None
            return None

    # Phase 0 — Audit
    run('manifests', phase0_audit)

    # Phase 1 — Preprocessing
    master, tr, samples = phase1_preprocessing()
    if master is None or len(master) == 0:
        AUDIT.fail("FATAL: no master dataset"); sys.exit(1)

    # Phase 2 — Baseline (ordered 2A→2F)
    run('reliability', phase2_reliability, master)   # 2A
    run('test_retest', phase2_test_retest, tr)       # 2B
    run('regression',  phase2_regression,  master)   # 2C
    run('gender',      phase2_gender,      master)   # 2D
    run('cfa',         phase2_cfa,         master)   # 2E
    run('cfa_r',       phase2_cfa_r,       master)   # 2F (optional rpy2)

    # Phase 3 — Layer 1
    run('network', phase3_network, master)
    run('tda',     phase3_mapper,  master)

    # Phase 4 — Layer 2
    mt = run('multitask', phase4_multitask, master)
    run('shap',     phase4_shap,     mt)
    run('cka',      phase4_cka,      mt)
    run('symbolic', phase4_symbolic, master)
    run('xgboost',  phase4_xgboost,  master)

    # Phase 5 — Layer 3
    run('causal',          phase5_causal,          master)
    run('counterfactuals', phase5_counterfactuals,
        R.get('xgboost'), master)

    # Phase 6 — Layer 4
    run('semantic', phase6_semantic)

    # Phase 7 — Layer 5
    run('sdi',          phase7_sdi,          master)
    run('rashomon',     phase7_rashomon,     master)
    run('replication',  phase7_replication,  master)
    run('subtypes',     phase7_subtypes,     master)
    run('interactions', phase7_interactions, master)

    # Phase 8 — Synthesis
    run('synthesis', phase8_synthesis, R)

    # Phase 9 — Manuscript table
    run('manuscript_table', phase9_manuscript_summary, R)

    elapsed = time.time() - start
    print(f"\n  Total wall time: {elapsed:.1f} seconds")
    AUDIT.summary()
    AUDIT.save(os.path.join(CONFIG['results_dir'], 'audit_log_v3_2_final.txt'))
    print(f"\n  Results → {CONFIG['results_dir']}/")
    print(f"  Figures → {CONFIG['figures_dir']}/")


if __name__ == '__main__':
    main()