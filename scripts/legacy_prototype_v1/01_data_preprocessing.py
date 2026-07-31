import os
import pyreadr
import pandas as pd
import numpy as np

print("="*60)
print("  DT3 PROJECT: EXACT PAPER-MATCHED PREPROCESSING PIPELINE  ")
print("="*60)

raw_dir = "data/raw/data"
processed_dir = "data/processed"
os.makedirs(processed_dir, exist_ok=True)

# Load Main Samples
s1_path = os.path.join(raw_dir, "imported_data_expro_filtred.Rds")
s2_path = os.path.join(raw_dir, "imported_data_filtred_2.Rds")
s3_path = os.path.join(raw_dir, "imported_data_filtred_3.Rds")

df1 = list(pyreadr.read_r(s1_path).values())[0]
df2 = list(pyreadr.read_r(s2_path).values())[0]
df3 = list(pyreadr.read_r(s3_path).values())[0]

def full_qc_pipeline(df, sample_name, min_minutes=15, is_sample_1=False):
    df = df.copy()
    n0 = len(df)
    log = [f"Sample: {sample_name} | Start N = {n0}"]

    # 1. Speeder check
    if 'questionnaire_duration' in df.columns:
        df['duration_min'] = pd.to_numeric(df['questionnaire_duration'], errors='coerce') / 60.0
        before = len(df)
        df = df[df['duration_min'] >= min_minutes]
        log.append(f"Speeder check (<{min_minutes} min removed): {before} -> {len(df)}")

    # 2. Bio/Physical consistency
    if 'height.qualit' in df.columns:
        before = len(df)
        df = df[df['height.qualit'] != False]
        log.append(f"Height consistency check: {before} -> {len(df)}")
        
    if 'weigh.qual' in df.columns:
        before = len(df)
        df = df[df['weigh.qual'] != False]
        log.append(f"Weight consistency check: {before} -> {len(df)}")

    # 3. Demographics & Age >= 18
    if 'Age' in df.columns: df['age'] = pd.to_numeric(df['Age'], errors='coerce')
    elif 'age' in df.columns: df['age'] = pd.to_numeric(df['age'], errors='coerce')

    if 'Gender' in df.columns: df['gender'] = df['Gender'].astype(str)
    elif 'sex' in df.columns: df['gender'] = df['sex'].astype(str)

    if 'Education' in df.columns: df['education'] = df['Education'].astype(str)
    elif 'education' in df.columns: df['education'] = df['education'].astype(str)

    before = len(df)
    df = df[df['age'] >= 18]
    log.append(f"Age >= 18 filter: {before} -> {len(df)}")

    # 4. Complete-case DTDD
    dtdd_cols = [c for c in df.columns if c.startswith('DTDD_')]
    for c in dtdd_cols: df[c] = pd.to_numeric(df[c], errors='coerce')
    before = len(df)
    df = df.dropna(subset=['DTDD_1m', 'DTDD_1p', 'DTDD_1n'])
    log.append(f"Complete-case DTDD filter: {before} -> {len(df)}")

    # 5. Attentional quality checks
    if 'low_q_res_std' in df.columns:
        before = len(df)
        df = df[df['low_q_res_std'] == 'HQ']
        log.append(f"Attentional quality (low_q_res_std == HQ): {before} -> {len(df)}")

    if 'low_q_res' in df.columns:
        before = len(df)
        df = df[df['low_q_res'] == 'HQ']
        log.append(f"Overall quality (low_q_res == HQ): {before} -> {len(df)}")

    # 6. Student interviewer duplicate submission filter (Sample 1 specific, line 350 RMD)
    if is_sample_1 and 'Personal_source' in df.columns and 'user_agent' in df.columns:
        before = len(df)
        non_zero = df[df['Personal_source'].astype(str) != '0']
        counts = non_zero.groupby(['user_agent', 'Personal_source'])['code'].transform('count')
        faker_codes = set(non_zero[counts > 1]['code'])
        df = df[~df['code'].isin(faker_codes)]
        log.append(f"Interviewer duplicate submission filter (potential_fakers): {before} -> {len(df)}")

    # 7. MAD Outlier Screening (threshold = 2.5)
    m_cols = ['DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m']
    p_cols = ['DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p']
    n_cols = ['DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n']

    if all(c in df.columns for c in m_cols + p_cols + n_cols):
        df['score_Machiavellianism'] = df[m_cols].sum(axis=1)
        df['score_Psychopathy'] = df[p_cols].sum(axis=1)
        df['score_Narcissism'] = df[n_cols].sum(axis=1)
        df['score_DarkCore_Total'] = df[m_cols + p_cols + n_cols].sum(axis=1)

        composite = df['score_DarkCore_Total']
        median = composite.median()
        mad = 1.4826 * np.median(np.abs(composite - median))
        if mad > 0:
            modified_z = np.abs(composite - median) / mad
            before = len(df)
            df = df[modified_z <= 2.5]
            log.append(f"MAD outlier screening (threshold <= 2.5): {before} -> {len(df)}")

    print("\n".join(log))
    print(f" -> FINAL {sample_name}: N = {len(df)} (Removed {n0 - len(df)} total, {(n0-len(df))/n0*100:.1f}%)\n")
    return df

print("\n[1/3] Applying full QC pipeline...")
df1_clean = full_qc_pipeline(df1, "Sample 1 (Community)", min_minutes=26, is_sample_1=True)
df1_clean['sample_origin'] = 'sample_1_community'

df2_clean = full_qc_pipeline(df2, "Sample 2 (Student)", min_minutes=15)
df2_clean['sample_origin'] = 'sample_2_student'

df3_clean = full_qc_pipeline(df3, "Sample 3 (Representative)", min_minutes=15)
df3_clean['sample_origin'] = 'sample_3_representative'

master_df = pd.concat([df1_clean, df2_clean, df3_clean], ignore_index=True)
master_df.to_csv(os.path.join(processed_dir, "dt3_master_dataset.csv"), index=False)

# Sample 4 (Test-Retest)
pretest_path = os.path.join(raw_dir, "data_DTDD_pretest.Rds")
retest_path  = os.path.join(raw_dir, "data_DTDD_retest.Rds")

df_pre  = list(pyreadr.read_r(pretest_path).values())[0]
df_post = list(pyreadr.read_r(retest_path).values())[0]

df_pre_clean  = df_pre.drop_duplicates(subset=['code', 'question_name'])
df_post_clean = df_post.drop_duplicates(subset=['code', 'question_name'])

df_pre_wide  = df_pre_clean.pivot(index='code', columns='question_name', values='value').reset_index()
df_post_wide = df_post_clean.pivot(index='code', columns='question_name', values='value').reset_index()

test_retest_df = pd.merge(df_pre_wide, df_post_wide, on='code', suffixes=('_T1', '_T2'))
test_retest_df.to_csv(os.path.join(processed_dir, "dt3_test_retest_dataset.csv"), index=False)

print(f"PREPROCESSING COMPLETE! Master Dataset N = {len(master_df)} | Test-Retest N = {len(test_retest_df)}")
print("COMPARE against paper targets: S1 = 3524, S2 = 1915, S3 = 1244.")
print("="*60)
