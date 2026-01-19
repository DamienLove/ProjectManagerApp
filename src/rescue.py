import os
import shutil
import stat
import time

# --- CONFIG ---
SOURCE_DIR = r"C:\Projects"
BACKUP_DIR = r"G:\My Drive\projects"

def unlock_file(func, path, exc_info):
    """Force unlock read-only files (fixes WinError 5 Access Denied)"""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"   > FAILED to remove: {path} ({e})")

def rescue_projects():
    if not os.path.exists(SOURCE_DIR):
        print(f"Source directory {SOURCE_DIR} does not exist!")
        return

    if not os.path.exists(BACKUP_DIR):
        try:
            os.makedirs(BACKUP_DIR)
            print(f"Created backup directory: {BACKUP_DIR}")
        except Exception as e:
            print(f"CRITICAL: Cannot create backup directory {BACKUP_DIR}. Aborting. ({e})")
            return

    print(f"--- STARTING ROBUST RESCUE: {SOURCE_DIR} -> {BACKUP_DIR} ---")
    
    # Get all project folders
    projects = [f for f in os.listdir(SOURCE_DIR) if os.path.isdir(os.path.join(SOURCE_DIR, f))]
    
    for project in projects:
        # Skip the app itself if it is in that folder
        if project.lower() in ["projectmanagerapp", "omniprojectsync"]: 
            continue

        src_path = os.path.join(SOURCE_DIR, project)
        dst_path = os.path.join(BACKUP_DIR, project)
        
        print(f"\n[TRANSFERRING] {project}...")
        
        try:
            # 1. COPY (Robust copy across drives)
            if os.path.exists(dst_path):
                print(f"   > Destination already exists. Updating files...")
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            else:
                shutil.copytree(src_path, dst_path)
            
            # Verify copy successful before deleting
            if os.path.exists(dst_path):
                print(f"   > Backup verified at: {dst_path}")
                
                # 2. DELETE LOCAL (Force unlock)
                print(f"   > Cleaning local copy (Unlocking Git files)...")
                shutil.rmtree(src_path, onerror=unlock_file)
                print(f"   ✅ {project} Moved & Cleaned Successfully.")
            else:
                print(f"   ❌ Verification FAILED for {project}. Local files kept.")
            
        except Exception as e:
            print(f"   ❌ ERROR Moving {project}: {e}")
            print("   > Local files PRESERVED to prevent data loss.")

    print("\n--- RESCUE OPERATION COMPLETE ---")

if __name__ == "__main__":
    rescue_projects()
