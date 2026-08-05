# Confirm we're in the right place first
cat("Working directory is:", getwd(), "\n")

raw_dir <- "data/raw/osf_original/data"
cat("Looking in:", normalizePath(raw_dir, mustWork = FALSE), "\n")

rds_files <- list.files(raw_dir, pattern = "\\.Rds$", full.names = TRUE)
cat("Found", length(rds_files), "Rds files:\n")
print(rds_files)

if (length(rds_files) == 0) {
  stop("No .Rds files found — check your working directory and path before proceeding.")
}

data_list <- list()
for (f in rds_files) {
  cat("Reading:", f, "... ")
  result <- tryCatch({
    readRDS(f)
  }, error = function(e) {
    cat("FAILED:", conditionMessage(e), "\n")
    NULL
  })
  if (!is.null(result)) {
    cat("OK (", nrow(result), "rows,", ncol(result), "cols )\n")
    data_list[[basename(f)]] <- result
  }
}

cat("\nSuccessfully loaded", length(data_list), "of", length(rds_files), "files.\n")

dir.create("docs/validation_reports", showWarnings = FALSE, recursive = TRUE)

report_path <- "docs/validation_reports/01_raw_structure_report.txt"
sink(report_path)

for (nm in names(data_list)) {
  cat("\n\n========================================\n")
  cat("FILE:", nm, "\n")
  cat("========================================\n")
  d <- data_list[[nm]]
  cat("Class:", paste(class(d), collapse = ", "), "\n")
  cat("Dimensions:", paste(dim(d), collapse = " x "), "\n\n")
  cat("Column names:\n")
  print(names(d))
  cat("\nStructure (str):\n")
  str(d, list.len = ncol(d))
  cat("\nFirst 5 rows:\n")
  print(head(d, 5))
  cat("\nSummary:\n")
  print(summary(d))
}

sink()

# Verify the file actually has content before declaring success
file_size <- file.info(report_path)$size
cat("Report file size:", file_size, "bytes\n")
if (file_size < 100) {
  warning("Report file looks suspiciously small/empty — something went wrong.")
} else {
  cat("Report written successfully to", report_path, "\n")
}
