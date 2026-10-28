# Multi-group CFA invariance testing across community/student/representative
# Fits 3-factor and bifactor models, tests configural / metric / scalar invariance
suppressPackageStartupMessages({ library(lavaan); library(readr); library(dplyr); library(tidyr) })

df <- read_csv("data/processed/dt3_master_dataset.csv", show_col_types = FALSE)
items <- c(paste0("DTDD_", 1:4, "m"), paste0("DTDD_", 1:4, "p"), paste0("DTDD_", 1:4, "n"))
df <- df %>% filter(sample_origin %in% c("sample_1_community","sample_2_student","sample_3_representative")) %>%
             select(sample_origin, all_of(items)) %>% drop_na()
df$sample_origin <- factor(df$sample_origin,
                           levels = c("sample_1_community","sample_2_student","sample_3_representative"))

# 3-factor CFA spec
spec_3f <- '
  Mach =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m
  Psy  =~ DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p
  Narc =~ DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n
'
# Bifactor spec (symmetric orthogonal)
spec_bf <- '
  D    =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m + DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p + DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n
  Ms   =~ DTDD_1m + DTDD_2m + DTDD_3m + DTDD_4m
  Ps   =~ DTDD_1p + DTDD_2p + DTDD_3p + DTDD_4p
  Ns   =~ DTDD_1n + DTDD_2n + DTDD_3n + DTDD_4n
  D ~~ 0*Ms; D ~~ 0*Ps; D ~~ 0*Ns
  Ms ~~ 0*Ps; Ms ~~ 0*Ns; Ps ~~ 0*Ns
'

extract_fit <- function(fit, label) {
  fm <- fitMeasures(fit, c("chisq.scaled","df.scaled","cfi.scaled","rmsea.scaled"))
  data.frame(Model = label, Chi2 = round(fm[1],2), df = as.integer(fm[2]),
             CFI = round(fm[3],3), RMSEA = round(fm[4],3))
}

run_invariance <- function(spec, spec_label, group_label) {
  cat("\n=========", spec_label, "|", group_label, "=========\n")
  rows <- list()
  # Configural
  cfg <- tryCatch(cfa(spec, data = df, group = "sample_origin", estimator = "MLR"),
                  error = function(e){ cat("Configural failed:", conditionMessage(e), "\n"); NULL })
  if (is.null(cfg)) return(NULL)
  rows[[1]] <- extract_fit(cfg, paste0(spec_label, " | configural (", group_label, ")"))
  rows[[1]]$delta_CFI <- NA; rows[[1]]$delta_RMSEA <- NA
  # Metric (loadings equal)
  met <- tryCatch(cfa(spec, data = df, group = "sample_origin", estimator = "MLR",
                       group.equal = "loadings"),
                  error = function(e){ cat("Metric failed:", conditionMessage(e), "\n"); NULL })
  if (!is.null(met)) {
    r <- extract_fit(met, paste0(spec_label, " | metric (", group_label, ")"))
    r$delta_CFI <- round(r$CFI - rows[[1]]$CFI, 3)
    r$delta_RMSEA <- round(r$RMSEA - rows[[1]]$RMSEA, 3)
    rows[[2]] <- r
  }
  # Scalar (loadings + intercepts equal)
  sca <- tryCatch(cfa(spec, data = df, group = "sample_origin", estimator = "MLR",
                       group.equal = c("loadings","intercepts")),
                  error = function(e){ cat("Scalar failed:", conditionMessage(e), "\n"); NULL })
  if (!is.null(sca)) {
    r <- extract_fit(sca, paste0(spec_label, " | scalar (", group_label, ")"))
    ref <- if (length(rows) >= 2) rows[[2]] else rows[[1]]
    r$delta_CFI <- round(r$CFI - ref$CFI, 3)
    r$delta_RMSEA <- round(r$RMSEA - ref$RMSEA, 3)
    rows[[3]] <- r
  }
  do.call(rbind, rows)
}

result <- rbind(
  run_invariance(spec_3f, "3-factor", "3 samples"),
  run_invariance(spec_bf, "Bifactor", "3 samples")
)
write_csv(result, "results/tables/baseline_13_multigroup_invariance.csv")
cat("\n=== Multi-group invariance summary ===\n"); print(result, row.names = FALSE)
cat("\nInterpretation guide:\n")
cat("  Configural→Metric ΔCFI < .01 = loadings invariant\n")
cat("  Metric→Scalar  ΔCFI < .01 = intercepts invariant\n")
