import os
import pyreadr
import pandas as pd
import numpy as np

print("="*60)
print("  DT3 PROJECT: VALIDATED DATA PREPROCESSING PIPELINE (S1-S4)  ")
print("="*60)

raw_dir = "data/raw/data"
processed_dir = "data/processed"
os.makedirs(processed_dir, exist_ok=True)

# 1. Load Main Samples (S1, S2, S3)
s1_path = os.path.join(raw_dir, "imported_data_expro_filtred.Rds")
s2_path = os.path.join(raw_dir, "imported_data_filtred_2.Rds")
s3_path = os.path.join(raw_dir, "imported_data_filtred_3.Rds")

print("\n[1/4] Loading RDS sample files...")
df1 = list(pyreadr.read_r(s1_path).values())[0]
df2 = list(pyreadr.read_r(s2_path).values())[0]
df3 = list(pyreadr.read_r(s3_path).values())[0]

def clean_and_filter(df, sample_name):
    df = df.copy()
    initial_n = len(df)
    
    if 'Age' in df.columns: df['age'] = pd.to_numeric(df['Age'], errors='coerce')
    elif 'age' in df.columns: df['age'] = pd.to_numeric(df['age'], errors='coerce')

    if 'Gender' in df.columns: df['gender'] = df['Gender'].astype(str)
    elif 'sex' in df.columns: df['gender'] = df['sex'].astype(str)

    if 'Education' in df.columns: df['education'] = df['Education'].astype(str)
    elif 'education' in df.columns: df['education'] = df['education'].astype(str)

    dtdd_cols = [c for c in df.columns if c.startswith('DTDD_')]
    for c in dtdd_cols: df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['DTDD_1m', 'DTDD_1p', 'DTDD_1n'])

    if 'speeder' in df.columns: df = df[df['speeder'] == False]
    if 'low_q_res_std' in df.columns: df = df[df['low_q_res_std'] == 'HQ']
    if 'low_q_res' in df.columns: df = df[df['low_q_res'] == 'HQ']
    df = df[df['age'] >= 18]

    m_cols = ['DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m']
    p_cols = ['DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p']
    n_cols = ['DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n']

    if all(c in df.columns for c in m_cols): df['score_Machiavellianism'] = df[m_cols].sum(axis=1)
    if all(c in df.columns for c in p_cols): df['score_Psychopathy'] = df[p_cols].sum(axis=1)
    if all(c in df.columns for c in n_cols): df['score_Narcissism'] = df[n_cols].sum(axis=1)
    if all(c in df.columns for c in m_cols + p_cols + n_cols): df['score_DarkCore_Total'] = df[m_cols + p_cols + n_cols].sum(axis=1)

    print(f" -> {sample_name}: Cleaned N = {len(df)} (Removed {initial_n - len(df)} low-quality/incomplete cases)")
    return df

print("\n[2/4] Filtering main samples S1, S2, S3...")
df1_clean = clean_and_filter(df1, "Sample 1 (Community)")
df1_clean['sample_origin'] = 'sample_1_community'

df2_clean = clean_and_filter(df2, "Sample 2 (Student)")
df2_clean['sample_origin'] = 'sample_2_student'

df3_clean = clean_and_filter(df3, "Sample 3 (Representative)")
df3_clean['sample_origin'] = 'sample_3_representative'

master_df = pd.concat([df1_clean, df2_clean, df3_clean], ignore_index=True)
master_csv = os.path.join(processed_dir, "dt3_master_dataset.csv")
master_df.to_csv(master_csv, index=False)

# 2. Load & Process Sample 4 (Test-Retest)
print("\n[3/4] Processing Sample 4 (Test-Retest Pretest & Retest)...")
pretest_path = os.path.join(raw_dir, "data_DTDD_pretest.Rds")
retest_path  = os.path.join(raw_dir, "data_DTDD_retest.Rds")

df_pre  = list(pyreadr.read_r(pretest_path).values())[0]
df_post = list(pyreadr.read_r(retest_path).values())[0]

# Deduplicate before pivoting
df_pre_clean  = df_pre.drop_duplicates(subset=['code', 'question_name'])
df_post_clean = df_post.drop_duplicates(subset=['code', 'question_name'])

df_pre_wide  = df_pre_clean.pivot(index='code', columns='question_name', values='value').reset_index()
df_post_wide = df_post_clean.pivot(index='code', columns='question_name', values='value').reset_index()

test_retest_df = pd.merge(df_pre_wide, df_post_wide, on='code', suffixes=('_T1', '_T2'))
test_retest_csv = os.path.join(processed_dir, "dt3_test_retest_dataset.csv")
test_retest_df.to_csv(test_retest_csv, index=False)

print(f" -> Sample 4 (Test-Retest Paired): N = {len(test_retest_df)} matched pairs saved to '{test_retest_csv}'")

print("\n[4/4] PREPROCESSING COMPLETE!")
print(f" -> Master Dataset Shape: {master_df.shape} | N = {len(master_df)}")
print(f" -> Test-Retest Dataset Shape: {test_retest_df.shape} | N = {len(test_retest_df)}")
print("="*60)
