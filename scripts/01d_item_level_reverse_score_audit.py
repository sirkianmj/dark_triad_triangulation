import pandas as pd
import numpy as np

print("="*60)
print("  DT3 DIAGNOSTIC: ITEM-TOTAL CORRELATION AUDIT  ")
print("  (Finds exactly which items are still mis-keyed)")
print("="*60)

df = pd.read_csv('data/processed/dt3_master_dataset.csv', low_memory=False)

def audit_scale(df, prefix, scale_label):
    cols = [c for c in df.columns if c.startswith(prefix) and not c.endswith(('sum', 'Total', 'T1', 'T2', 'origin', 'quality'))]
    if not cols:
        print(f"\n[{scale_label}] No item columns found for prefix '{prefix}'")
        return

    item_df = df[cols].apply(pd.to_numeric, errors='coerce').dropna()
    total = item_df.sum(axis=1)

    print(f"\n--- {scale_label} ({len(cols)} items, N = {len(item_df)}) ---")
    flagged = []
    for col in cols:
        # Corrected item-total correlation: correlate item against total EXCLUDING itself
        rest_total = total - item_df[col]
        r = item_df[col].corr(rest_total)
        flag = "  <<< SUSPECT MIS-KEYED / UN-REVERSED" if r < 0.15 else ""
        if r < 0.15:
            flagged.append((col, round(r, 3)))
        print(f"  {col:12s}: corrected item-total r = {r:+.3f}{flag}")

    if flagged:
        print(f"\n  ==> ACTION REQUIRED: re-check reverse-scoring for: {flagged}")
    else:
        print(f"\n  ==> All items in {scale_label} show healthy positive item-total correlations.")

audit_scale(df, 'BFI_C_', 'Conscientiousness (BFI_C)')
audit_scale(df, 'BFI_N_', 'Neuroticism (BFI_N)')
audit_scale(df, 'BFI_A_', 'Agreeableness (BFI_A)')
audit_scale(df, 'RSES_', 'Self-Esteem (RSES)')
audit_scale(df, 'TEQ_', 'Empathy (TEQ)')

print("\n" + "="*60)
