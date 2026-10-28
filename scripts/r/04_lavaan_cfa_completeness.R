#!/usr/bin/env Rscript
# Phase 2.8: CFA completeness reporting (SRMR, RMSEA 90% CI, FD) + WLSMV sensitivity
# Reads dt3_master_dataset.csv, fits all 7 models, writes two CSVs.

suppressPackageStartupMessages({
  library(lavaan)
  library(readr)
  library(dplyr)
})

TABLES <- "results/tables"
dir.create(TABLES, showWarnings = FALSE, recursive = TRUE)

# ---- Data ----
df <- read_csv("data/processed/dt3_master_dataset.csv", show_col_types = FALSE)
items_m <- paste0("DTDD_", 1:4, "m")
items_p <- paste0("DTDD_", 1:4, "p")
items_n <- paste0("DTDD_", 1:4, "n")
items_all <- c(items_m, items_p, items_n)

sub <- df[df$sample_origin == "sample_1_community", items_all]
sub <- sub[complete.cases(sub), ]
for (v in items_all) sub[[v]] <- as.numeric(sub[[v]])
N <- nrow(sub)
cat(sprintf("Community sample (12 DTDD items only): N = %d\n", N))

# ---- Model specs ----
spec_1f <- sprintf("DarkCore =~ %s", paste(items_all, collapse = " + "))
spec_2f_mp <- sprintf("MP =~ %s\nNarc =~ %s",
                     paste(c(items_m, items_p), collapse = " + "),
                     paste(items_n, collapse = " + "))
spec_2f_mn <- sprintf("MN =~ %s\nPsy =~ %s",
                     paste(c(items_m, items_n), collapse = " + "),
                     paste(items_p, collapse = " + "))
spec_3f <- sprintf("Mach =~ %s\nPsy =~ %s\nNarc =~ %s",
                  paste(items_m, collapse = " + "),
                  paste(items_p, collapse = " + "),
                  paste(items_n, collapse = " + "))
spec_bf_sym <- sprintf(
" D  =~ %s
  Ms =~ %s
  Ps =~ %s
  Ns =~ %s
  D ~~ 0*Ms
  D ~~ 0*Ps
  D ~~ 0*Ns
  Ms ~~ 0*Ps
  Ms ~~ 0*Ns
  Ps ~~ 0*Ns",
  paste(items_all, collapse = " + "),
  paste(items_m, collapse = " + "),
  paste(items_p, collapse = " + "),
  paste(items_n, collapse = " + "))
spec_bf_s1 <- sprintf(
" D  =~ %s
  Ps =~ %s
  Ns =~ %s
  D ~~ 0*Ps
  D ~~ 0*Ns
  Ps ~~ Ns",
  paste(items_all, collapse = " + "),
  paste(items_p, collapse = " + "),
  paste(items_n, collapse = " + "))
spec_bf_si1 <- sprintf(
" D  =~ %s
  Ms =~ DTDD_1m + DTDD_2m + DTDD_3m
  Ps =~ %s
  Ns =~ %s
  D ~~ 0*Ms
  D ~~ 0*Ps
  D ~~ 0*Ns
  Ms ~~ 0*Ps
  Ms ~~ 0*Ns
  Ps ~~ Ns",
  paste(items_all, collapse = " + "),
  paste(items_p, collapse = " + "),
  paste(items_n, collapse = " + "))

models <- list(
  "1-factor"            = list(spec = spec_1f,     factors = list(DarkCore = items_all)),
  "2-factor M+P"        = list(spec = spec_2f_mp,  factors = list(MP = c(items_m, items_p), Narc = items_n)),
  "2-factor M+N"        = list(spec = spec_2f_mn,  factors = list(MN = c(items_m, items_n), Psy = items_p)),
  "3-factor"            = list(spec = spec_3f,     factors = list(Mach = items_m, Psy = items_p, Narc = items_n)),
  "Bifactor symmetric"  = list(spec = spec_bf_sym, factors = list(D = items_all, Ms = items_m, Ps = items_p, Ns = items_n)),
  "Bifactor-(S-1)"      = list(spec = spec_bf_s1,  factors = list(D = items_all, Ps = items_p, Ns = items_n)),
  "Bifactor-(S.I-1)"    = list(spec = spec_bf_si1, factors = list(D = items_all, Ms = items_m[1:3], Ps = items_p, Ns = items_n))
)

# ---- Factor Determinacy from standardized loadings ----
compute_fd <- function(loadings) {
  l <- abs(loadings[abs(loadings) > 1e-6])
  if (length(l) == 0) return(NA_real_)
  (sum(l)^2) / (sum(l)^2 + sum(1 - l^2))
}

# ---- Fit + extract ----
results <- list()
for (name in names(models)) {
  cat(sprintf("\n=== %s ===\n", name))
  fit <- tryCatch(cfa(models[[name]]$spec, data = sub, estimator = "ML"),
                  error = function(e) { cat("  FAILED:", conditionMessage(e), "\n"); NULL })
  if (is.null(fit)) next

  fm <- fitMeasures(fit, c("chisq", "df", "cfi", "tli", "rmsea",
                            "rmsea.ci.lower", "rmsea.ci.upper", "srmr"))
  cat(sprintf("  chisq=%.2f df=%d CFI=%.3f TLI=%.3f RMSEA=%.3f [%.3f, %.3f] SRMR=%.3f\n",
              fm["chisq"], fm["df"], fm["cfi"], fm["tli"],
              fm["rmsea"], fm["rmsea.ci.lower"], fm["rmsea.ci.upper"], fm["srmr"]))

  row <- data.frame(
    Model = name,
    Chi2 = round(fm["chisq"], 2),
    df = as.integer(fm["df"]),
    CFI = round(fm["cfi"], 3),
    TLI = round(fm["tli"], 3),
    RMSEA = round(fm["rmsea"], 3),
    RMSEA_CI_lo = round(fm["rmsea.ci.lower"], 3),
    RMSEA_CI_hi = round(fm["rmsea.ci.upper"], 3),
    SRMR = round(fm["srmr"], 3),
    N = N,
    stringsAsFactors = FALSE
  )

  # Per-factor FD
  for (fname in names(models[[name]]$factors)) {
    item_set <- models[[name]]$factors[[fname]]
    loadings <- tryCatch(lavInspect(fit, "std")$lambda[item_set, fname],
                          error = function(e) numeric(0))
    fd_val <- if (length(loadings) > 0) round(compute_fd(loadings), 3) else NA_real_
    row[[paste0("FD_", fname)]] <- fd_val
  }

  results[[name]] <- row
}

out <- dplyr::bind_rows(results)
write_csv(out, file.path(TABLES, "baseline_15_lavaan_cfa_completeness.csv"))
cat(sprintf("\n✓ Wrote %s\n", file.path(TABLES, "baseline_15_lavaan_cfa_completeness.csv")))

# ============================================================================
# WLSMV ordinal sensitivity check (3-factor only — the baseline model)
# ============================================================================
cat("\n=== WLSMV ordinal sensitivity (3-factor) ===\n")
fit_wlsmv <- tryCatch(
  cfa(spec_3f, data = sub, ordered = items_all, estimator = "WLSMV"),
  error = function(e) { cat("  WLSMV FAILED:", conditionMessage(e), "\n"); NULL }
)
if (!is.null(fit_wlsmv)) {
  fm <- fitMeasures(fit_wlsmv, c("chisq.scaled", "df.scaled", "cfi.scaled", "tli.scaled",
                                  "rmsea.scaled", "rmsea.ci.lower.scaled",
                                  "rmsea.ci.upper.scaled", "srmr"))
  cat(sprintf("  chisq=%.2f df=%d CFI=%.3f TLI=%.3f RMSEA=%.3f [%.3f, %.3f] SRMR=%.3f\n",
              fm["chisq.scaled"], fm["df.scaled"], fm["cfi.scaled"], fm["tli.scaled"],
              fm["rmsea.scaled"], fm["rmsea.ci.lower.scaled"], fm["rmsea.ci.upper.scaled"], fm["srmr"]))

  wlsmv_row <- data.frame(
    Model = "3-factor (WLSMV ordinal)",
    Chi2 = round(fm["chisq.scaled"], 2),
    df = as.integer(fm["df.scaled"]),
    CFI = round(fm["cfi.scaled"], 3),
    TLI = round(fm["tli.scaled"], 3),
    RMSEA = round(fm["rmsea.scaled"], 3),
    RMSEA_CI_lo = round(fm["rmsea.ci.lower.scaled"], 3),
    RMSEA_CI_hi = round(fm["rmsea.ci.upper.scaled"], 3),
    SRMR = round(fm["srmr"], 3),
    N = N,
    stringsAsFactors = FALSE
  )
  write_csv(wlsmv_row, file.path(TABLES, "baseline_16_wlsmv_ordinal_sensitivity.csv"))
  cat(sprintf("✓ Wrote %s\n", file.path(TABLES, "baseline_16_wlsmv_ordinal_sensitivity.csv")))
}
