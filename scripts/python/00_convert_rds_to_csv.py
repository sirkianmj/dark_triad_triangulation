#!/usr/bin/env python3

import pyreadr
import pandas as pd
import glob
import os

def convert_all_rds():
    raw_dir = "data/raw/osf_original/data"
    processed_dir = "data/processed"
    
    # Ensure processed directory exists
    os.makedirs(processed_dir, exist_ok=True)

    # Grab all OSF Rds files
    rds_files = glob.glob(f"{raw_dir}/*.Rds")
    
    if not rds_files:
        print("Error: No .Rds files found. Check your paths.")
        return

    for file in rds_files:
        print(f"Reading: {file}...")
        
        # pyreadr reads the Rds file directly into a Python dictionary
        result = pyreadr.read_r(file)
        
        # Extract the pandas DataFrame
        df = list(result.values())[0]
        
        # Generate the new CSV filename
        base_name = os.path.basename(file).replace(".Rds", ".csv")
        csv_path = os.path.join(processed_dir, base_name)
        
        # Save as a clean, UTF-8 CSV with no row indices
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"Success: {df.shape[0]} rows x {df.shape[1]} columns saved to {csv_path}\n")

    print("ALL FILES CONVERTED. RStudio is no longer required for this project.")

if __name__ == "__main__":
    convert_all_rds()