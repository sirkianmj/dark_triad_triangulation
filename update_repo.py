import os
import shutil

def reorganize():
    print("🛠️  DT3 REPOSITORY REFACTOR: UPGRADING TO v3 PRODUCTION STANDARDS")

    # 1. Create the Legacy directory
    legacy_dir = "scripts/legacy_prototype_v1"
    if not os.path.exists(legacy_dir):
        os.makedirs(legacy_dir)
        print(f"  [+] Created {legacy_dir}")

    # 2. Move all existing .py files in scripts/ into legacy (except the new one)
    all_scripts = [f for f in os.listdir("scripts") if f.endswith(".py") and f != "utils_features.py"]
    for script in all_scripts:
        old_path = os.path.join("scripts", script)
        new_path = os.path.join(legacy_dir, script)
        shutil.move(old_path, new_path)
        print(f"  [archive] {script} -> {legacy_dir}")

    # 3. Clean the Results folder (to remove old, incorrect CSVs/PNGs)
    # We want a fresh start with v3 results
    if os.path.exists("results"):
        print("  [clean] Purging old results to make room for v3 verified data...")
        for item in os.listdir("results"):
            item_path = os.path.join("results", item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path) and item != "figures":
                shutil.rmtree(item_path)

    # 4. Finalise v3 script as the primary driver
    if os.path.exists("DT3_MASTER_PIPELINE3.py"):
        shutil.copy("DT3_MASTER_PIPELINE3.py", "run_pipeline.py")
        print("  [master] DT3_MASTER_PIPELINE3.py -> run_pipeline.py (Main Entry Point)")
    
    print("\n✅ REFACTOR COMPLETE.")
    print("Next Steps:")
    print("1. Run: python run_pipeline.py")
    print("2. git add .")
    print("3. git commit -m 'UPGRADE: Refactored repository to v3 Master Pipeline standards'")
    print("4. git push origin main")

if __name__ == "__main__":
    reorganize()