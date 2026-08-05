#!/usr/bin/env python3
"""
===============================================================================
DT³ Phase 11: Master Dossier Compiler (Remediated)
===============================================================================
Aggregates all execution scripts, logs, and CSV outputs into a unified Markdown
document for rigorous methodological auditing and manuscript preparation.

Updates:
- Ignores macOS '._' hidden metadata files and .DS_Store.
- Prevents duplicate entries from overlapping target directories.
- Includes all remediated scripts (01–09) and results tables.
===============================================================================
"""

import os
import datetime

PROJECT_ROOT = os.getcwd()  # Assumes script is run from project root
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "DT3_Complete_Project_Dossier.md")

# Directories to scan; 'results' includes 'results/tables', so no duplicate needed
TARGET_DIRS = [
    "scripts/python",
    "results"
]

# Only include text-based files; skip images, HTML, binary
VALID_EXTENSIONS = [".py", ".csv", ".log"]

def compile_dossier():
    print("--- Compiling DT³ Project Dossier ---")
    
    compiled_content = []
    
    # 1. Header
    compiled_content.append("# THE DARK TRIAD TRIANGULATION (DT³) PROJECT DOSSIER")
    compiled_content.append(f"Compiled on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    compiled_content.append("This document contains the complete execution codebase and resulting tabular outputs for the DT³ project. It is intended for rigorous scientific auditing.\n")
    
    # Use a set to prevent duplicate file entries if paths overlap
    unique_files = set()
    
    # 2. Gather files
    for d in TARGET_DIRS:
        dir_path = os.path.join(PROJECT_ROOT, d)
        if not os.path.exists(dir_path):
            continue
            
        for root, _, files in os.walk(dir_path):
            # Skip figures subdirectory (we can't embed them in markdown easily)
            if "figures" in root:
                continue
                
            for file in files:
                # Ignore macOS hidden metadata files and DS_Store
                if file.startswith("._") or file == ".DS_Store":
                    continue
                    
                if any(file.endswith(ext) for ext in VALID_EXTENSIONS):
                    unique_files.add(os.path.abspath(os.path.join(root, file)))
                    
    # Sort files so scripts appear chronologically, then results
    all_files = sorted(list(unique_files))
    
    # 3. Extract and append contents
    files_processed = 0
    for filepath in all_files:
        rel_path = os.path.relpath(filepath, PROJECT_ROOT)
        
        compiled_content.append("="*80)
        compiled_content.append(f"FILE: {rel_path}")
        compiled_content.append("="*80)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # For massive CSVs, truncate to prevent token overflow
            if filepath.endswith(".csv") and len(content.splitlines()) > 1000:
                lines = content.splitlines()
                compiled_content.append("\n".join(lines[:100]))
                compiled_content.append("\n... [DATA TRUNCATED FOR LENGTH: SHOWING FIRST 100 ROWS] ...\n")
            else:
                compiled_content.append(content)
                
            compiled_content.append("\n\n")
            files_processed += 1
            print(f"[SUCCESS] Ingested: {rel_path}")
            
        except Exception as e:
            print(f"[ERROR] Failed to read {rel_path}: {e}")
            compiled_content.append(f"[ERROR READING FILE: {e}]\n\n")
            
    # 4. Write to output file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(compiled_content))
        
    print(f"\n--- Compilation Complete ---")
    print(f"Total files ingested: {files_processed}")
    print(f"Dossier saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    compile_dossier()