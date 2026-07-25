import os
import pyreadr
import pandas as pd
import numpy as np

print("="*60)
print("  DT3 PROJECT: MASTER DATA PREPROCESSING PIPELINE  ")
print("="*60)

raw_dir = "data/raw/data"
processed_dir = "data/processed"
os.makedirs(processed_dir, exist_ok=True)

# 1. Load Samples
s1_path = os.path.join(raw_dir, "imported_data_expro_filtred.Rds")
s2_path = os.path.join(raw_dir, "imported_data_filtred_2.Rds")
s3_path = os.path.join(raw_dir, "imported_data_filtred_3.Rds")

print("\n[1/4] Loading RDS sample files...")
df1 = list(pyreadr.read_r(s1_path).values())[0]
df2 = list(pyreadr.read_r(s2_path).values())[0]
df3 = list(pyreadr.read_r(s3_path).values())[0]

df1['sample_origin'] = 'sample_1_community'
df2['sample_origin'] = 'sample_2_student'
df3['sample_origin'] = 'sample_3_representative'

print(f" -> Sample 1 (Community): {df1.shape}")
print(f" -> Sample 2 (Student): {df2.shape}")
print(f" -> Sample 3 (Representative): {df3.shape}")

# Function to standardise key column names across samples
def standardize_sample(df, sample_label):
    df = df.copy()
    
    # Age & Gender standardization
    if 'Age' in df.columns:
        df['age'] = pd.to_numeric(df['Age'], errors='coerce')
    elif 'age' in df.columns:
        df['age'] = pd.to_numeric(df['age'], errors='coerce')
        
    if 'Gender' in df.columns:
        df['gender'] = df['Gender'].astype(str)
    elif 'sex' in df.columns:
        df['gender'] = df['sex'].astype(str)
        
    if 'Education' in df.columns:
        df['education'] = df['Education'].astype(str)
    elif 'education' in df.columns:
        df['education'] = df['education'].astype(str)

    # Convert DTDD item columns to numeric
    dtdd_cols = [c for c in df.columns if c.startswith('DTDD_')]
    for c in dtdd_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
        
    # Calculate subscale sums if 12 core items are present
    m_cols = ['DTDD_1m', 'DTDD_2m', 'DTDD_3m', 'DTDD_4m']
    p_cols = ['DTDD_1p', 'DTDD_2p', 'DTDD_3p', 'DTDD_4p']
    n_cols = ['DTDD_1n', 'DTDD_2n', 'DTDD_3n', 'DTDD_4n']
    
    if all(col in df.columns for col in m_cols):
        df['score_Machiavellianism'] = df[m_cols].sum(axis=1)
    if all(col in df.columns for col in p_cols):
        df['score_Psychopathy'] = df[p_cols].sum(axis=1)
    if all(col in df.columns for col in n_cols):
        df['score_Narcissism'] = df[n_cols].sum(axis=1)
        
    if all(c in df.columns for c in m_cols + p_cols + n_cols):
        df['score_DarkCore_Total'] = df[m_cols + p_cols + n_cols].sum(axis=1)

    return df

print("\n[2/4] Standardizing and calculating trait composite scores...")
df1_clean = standardize_sample(df1, 'Sample 1')
df2_clean = standardize_sample(df2, 'Sample 2')
df3_clean = standardize_sample(df3, 'Sample 3')

# 3. Concatenate Master Working Dataset
print("\n[3/4] Aligning columns and concatenating into unified master dataset...")
master_df = pd.concat([df1_clean, df2_clean, df3_clean], ignore_index=True)

# 4. Save Output
out_csv = os.path.join(processed_dir, "dt3_master_dataset.csv")
master_df.to_csv(out_csv, index=False)

print("\n[4/4] PREPROCESSING COMPLETE!")
print(f" -> Master Dataset Shape: {master_df.shape}")
print(f" -> Saved to: {out_csv}")
print("="*60)
