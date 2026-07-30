import os
import pandas as pd
import numpy as np

def clean_edu_category(val):
    val = str(val).strip()
    if 'Basic' in val or val == '1': return 'Basic'
    if 'Vocational' in val or val == '2': return 'Vocational'
    if 'High' in val or val == '3': return 'HighSchool'
    if 'Higher' in val or val == '4': return 'HigherVocational'
    if 'Bachelor' in val or val == '5': return 'Bachelor'
    if 'Master' in val or val == '6': return 'Master'
    if 'Dr' in val or 'Ph' in val or val == '7': return 'Doctorate'
    return 'Other'

def build_feature_set(df):
    """Single source of truth for the external correlate feature set.
    Includes age, gender, clean education covariates, and correlate composite scores."""
    df = df.copy()

    predictors = ['age']

    # 1. Gender Covariates
    if 'gender' in df.columns:
        df['gender_clean'] = df['gender'].astype(str).str.strip().str.split('.').str[0]
        gender_dummies = pd.get_dummies(df['gender_clean'], prefix='gender', drop_first=True).astype(int)
        df = pd.concat([df, gender_dummies], axis=1)
        predictors += list(gender_dummies.columns)

    # 2. Education Clean Covariates
    if 'education' in df.columns:
        df['edu_clean'] = df['education'].apply(clean_edu_category)
        edu_dummies = pd.get_dummies(df['edu_clean'], prefix='edu', drop_first=True).astype(int)
        df = pd.concat([df, edu_dummies], axis=1)
        predictors += list(edu_dummies.columns)

    # 3. Composite Correlate Scores
    for prefix in ['BFI_A_', 'BFI_C_', 'BFI_N_', 'RSES_']:
        cols = [c for c in df.columns if c.startswith(prefix) and not c.endswith(('sum', 'Total'))]
        if cols:
            colname = f'{prefix}sum'
            df[colname] = df[cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
            predictors.append(colname)

    # Explicit 7-item TEQ Empathy selection (matching paper line 412)
    valid_teq_items = ['TEQ_1', 'TEQ_CON_2', 'TEQ_3', 'TEQ_CON_4', 'TEQ_5', 'TEQ_CON_14', 'TEQ_16']
    teq_present = [c for c in valid_teq_items if c in df.columns]
    if teq_present:
        df['TEQ_sum'] = df[teq_present].apply(pd.to_numeric, errors='coerce').sum(axis=1)
        predictors.append('TEQ_sum')

    predictors = list(dict.fromkeys(predictors))
    return df, predictors

if __name__ == '__main__':
    master_path = 'data/processed/dt3_master_dataset.csv'
    if os.path.exists(master_path):
        test_df = pd.read_csv(master_path, low_memory=False)
        test_df, test_preds = build_feature_set(test_df)
        print("="*60)
        print("  UTILS_FEATURES: CLEAN CATEGORICAL FEATURE BUILD TEST  ")
        print("="*60)
        print(f" -> Built {len(test_preds)} clean predictors: {test_preds}")
        print("="*60)
