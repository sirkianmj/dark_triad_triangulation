#!/usr/bin/env python3
"""
Phase 2.5 (additive, reviewer item 3): OLS with train/test split matching ML layers.
Predictors = Big Five + TEQ + Age (identical to XGBoost, Elastic-Net, RF).
Trains on community complete cases, evaluates on representative complete cases.
SAFETY: writes only baseline_11_* and baseline_12_* CSVs.
"""
import os, sys, logging
import numpy as np, pandas as pd
import statsmodels.api as sm
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_squared_error

PROCESSED, TABLES = "data/processed", "results/tables"
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(os.path.join(TABLES,"execution_audit.log"),mode='a'),
              logging.StreamHandler(sys.stdout)], force=True)

PREDS = ['BFI_A_sum','BFI_C_sum','BFI_E_sum','BFI_N_sum','BFI_O_sum','TEQ_sum','age']
TARGETS = ['score_Machiavellianism','score_Psychopathy','score_Narcissism']

def main():
    logging.info("="*63); logging.info(" PHASE 2.5: OLS age-aligned (matching ML split)"); logging.info("="*63)
    df = pd.read_csv(os.path.join(PROCESSED,"dt3_master_dataset.csv"), low_memory=False)

    train = df[df['sample_origin']=='sample_1_community'].dropna(subset=PREDS+TARGETS).copy()
    test  = df[df['sample_origin']=='sample_3_representative'].dropna(subset=PREDS+TARGETS).copy()
    logging.info(f"Train N={len(train)}  Test N={len(test)}")
    logging.info(f"Predictors: {PREDS}")

    Xtr = StandardScaler().fit_transform(train[PREDS].astype(float))
    # Use SAME scaler on test for consistency with ML layers
    sc = StandardScaler().fit(train[PREDS].astype(float))
    Xtr = sc.transform(train[PREDS].astype(float))
    Xte = sc.transform(test[PREDS].astype(float))
    ytr = train[TARGETS].values.astype(float)
    yte = test[TARGETS].values.astype(float)

    coef_rows, perf_rows = [], []
    for i, target in enumerate(TARGETS):
        # In-sample standardized betas: z-score y too
        ytr_z = (ytr[:, i] - ytr[:, i].mean()) / ytr[:, i].std(ddof=1)
        m = sm.OLS(ytr_z, sm.add_constant(Xtr)).fit(cov_type='HC3')
        for j, pred in enumerate(PREDS):
            coef_rows.append({
                'Target': target.replace('score_',''),
                'Predictor': pred,
                'Beta_std': round(m.params[j+1], 4),
                'SE': round(m.bse[j+1], 4),
                't': round(m.tvalues[j+1], 4),
                'p': m.pvalues[j+1],
            })
        # Out-of-sample R2 using raw-y fit
        m_raw = sm.OLS(ytr[:, i], sm.add_constant(Xtr)).fit()
        pred_te = m_raw.predict(sm.add_constant(Xte))
        r2_test = r2_score(yte[:, i], pred_te)
        mse_test = mean_squared_error(yte[:, i], pred_te)
        perf_rows.append({
            'Target': target.replace('score_',''),
            'N_train': len(train), 'N_test': len(test),
            'R2_train_insample': round(m_raw.rsquared, 3),
            'R2_test_outsample': round(r2_test, 3),
            'MSE_test': round(mse_test, 3),
        })

    pd.DataFrame(coef_rows).to_csv(os.path.join(TABLES,"baseline_11_ols_age_coefficients.csv"), index=False)
    pd.DataFrame(perf_rows).to_csv(os.path.join(TABLES,"baseline_12_ols_age_performance.csv"), index=False)
    logging.info("Wrote baseline_11_ols_age_coefficients.csv and baseline_12_ols_age_performance.csv")

    print("\n" + "="*63); print(" OLS AGE-ALIGNED RESULT"); print("="*63)
    for r in perf_rows:
        print(f"  {r['Target']:20s}: train R²={r['R2_train_insample']:.3f}  "
              f"test R²={r['R2_test_outsample']:.3f}  MSE={r['MSE_test']:.3f}")
    try:
        xgb = pd.read_csv(os.path.join(TABLES,"layer2_xgboost_performance.csv"))
        print("\n  vs XGBoost (out-of-sample test R²):")
        for _, r in xgb.iterrows():
            t = r['Trait']
            xgb_r2 = r['XGB_Test_R2']
            ols_r2 = next((p['R2_test_outsample'] for p in perf_rows if p['Target']==t), None)
            if ols_r2 is not None:
                delta = ols_r2 - xgb_r2
                print(f"    {t:20s}: OLS={ols_r2:.3f}  XGB={xgb_r2:.3f}  Δ={delta:+.3f}")
    except Exception as e:
        logging.warning(f"XGBoost comparison failed: {e}")
    print("="*63)

if __name__ == "__main__":
    main()
