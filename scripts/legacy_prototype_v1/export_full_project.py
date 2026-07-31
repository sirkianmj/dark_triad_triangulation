import os
import glob

print("="*60)
print("  DT3 PROJECT: BUNDLING ALL PROJECT FILES INTO SINGLE .TXT  ")
print("="*60)

output_filename = "DT3_FULL_PROJECT_DUMP.txt"

# Ensure output file is in .gitignore
gitignore_path = ".gitignore"
if os.path.exists(gitignore_path):
    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()
    if output_filename not in content:
        with open(gitignore_path, "a", encoding="utf-8") as f:
            f.write(f"\n# Exclude complete single-file dump\n{output_filename}\n")
        print(f" -> Added '{output_filename}' to .gitignore")

# Collect all project files
files_to_bundle = []

for doc_file in ["PROJECT_CHARTER.md", "README.md", "environment.yml", "data/data_dictionary.md"]:
    if os.path.exists(doc_file):
        files_to_bundle.append(doc_file)

script_files = sorted(glob.glob("scripts/*.py"))
files_to_bundle.extend(script_files)

result_files = sorted(glob.glob("results/*.csv"))
files_to_bundle.extend(result_files)

print(f"\nFound {len(files_to_bundle)} project files to bundle into '{output_filename}'...")

# Write Neat Consolidated Text File
with open(output_filename, "w", encoding="utf-8") as out:
    out.write("================================================================================\n")
    out.write("                     THE DARK TRIAD TRIANGULATION PROJECT (DT³)                  \n")
    out.write("                     COMPLETE NEAT PROJECT SOURCE CODE & RESULTS                 \n")
    out.write("================================================================================\n\n")
    
    for filepath in files_to_bundle:
        out.write("\n" + "#"*80 + "\n")
        out.write(f"### FILE: {filepath}\n")
        out.write("#"*80 + "\n\n")
        
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                out.write(f.read())
            out.write("\n\n")
            print(f"  [+] Bundled: {filepath}")
        except Exception as e:
            print(f"  [-] Error bundling {filepath}: {e}")

file_size_mb = os.path.getsize(output_filename) / (1024 * 1024)

print("\n" + "="*60)
print(f"SUCCESS! Created '{output_filename}' ({file_size_mb:.2f} MB)")
print("This file contains your entire project code, configs, and results.")
print("It is ignored by .gitignore and will NOT be uploaded to GitHub.")
print("="*60)
