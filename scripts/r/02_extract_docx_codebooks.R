library(officer)
library(purrr)

docx_files <- c(
  "data/raw/osf_original/Adjusting_variables.docx",
  "data/raw/osf_original/supplementary material/Sup.1.docx",
  "data/raw/osf_original/supplementary material/Sup.2.docx",
  "data/raw/osf_original/supplementary material/Sup.3.docx",
  "data/raw/osf_original/supplementary material/Sup.4.docx"
)

dir.create("docs/codebook", showWarnings = FALSE, recursive = TRUE)

for (f in docx_files) {
  doc <- read_docx(f)
  txt <- docx_summary(doc)
  out_name <- file.path("docs/codebook", paste0(tools::file_path_sans_ext(basename(f)), ".txt"))
  writeLines(txt$text, out_name)
  cat("Extracted:", f, "->", out_name, "\n")
}

