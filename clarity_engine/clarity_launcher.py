"""
ClarityOS Launcher v2 — Spawns Markoff Engine, Kernel, and Dispatcher
in separate console windows with full path verification.
"""
import os
import sys
import subprocess
import time


# ─── ROOT DETECTION ─────────────────────────────────────────────────
# Handles both .py execution and compiled .exe (PyInstaller --onefile)
if getattr(sys, 'frozen', False):
    # Compiled EXE: sys.executable = path to the .exe itself
    EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    # If EXE lives inside a 'dist' subfolder, go up one level to ROOT
    if os.path.basename(EXE_DIR).lower() == 'dist':
        ROOT = os.path.dirname(EXE_DIR)
    else:
        ROOT = EXE_DIR
else:
    # Running as .py script — ROOT = script's own directory
    ROOT = os.path.dirname(os.path.abspath(__file__))


# ─── ENGINE & VENV PATHS ───────────────────────────────────────────
ENGINE     = os.path.join(ROOT, "clarity_engine")
VENV       = os.path.join(ROOT, "clarityos_venv")
PYTHON     = os.path.join(VENV, "Scripts", "python.exe")
ACTIVATE   = os.path.join(VENV, "Scripts", "activate.bat")

MARKOFF    = os.path.join(ENGINE, "markoff_engine", "markoff_server.py")
KERNEL     = os.path.join(ENGINE, "kernel.py")
DISPATCHER = os.path.join(ENGINE, "dispatcher", "dispatcher_v1.py")


# ─── PATH VERIFICATION ─────────────────────────────────────────────
def verify_paths():
    """Halt with clear diagnostics if any engine target is missing."""
    checks = [
        ("ROOT directory",      ROOT),
        ("clarity_engine/",     ENGINE),
        ("Virtual env Python",  PYTHON),
        ("activate.bat",        ACTIVATE),
        ("markoff_server.py",   MARKOFF),
        ("kernel.py",           KERNEL),
        ("dispatcher_v1.py",    DISPATCHER),
    ]
    missing = [(label, path) for label, path in checks if not os.path.exists(path)]

    if missing:
        print("=" * 64)
        print("  ClarityOS Launcher — PATH ERRORS DETECTED")
        print("=" * 64)
        print(f"  Resolved ROOT: {ROOT}")
        print(f"  Frozen (EXE):  {getattr(sys, 'frozen', False)}")
        print()
        for label, path in missing:
            print(f"  MISSING  {label}")
            print(f"           {path}")
            print()
        print("  Fix the directory layout or re-check ROOT, then re-run.")
        print("=" * 64)
        input("\n  Press Enter to exit...")
        sys.exit(1)

    print(f"  [OK] All paths verified under:\n       {ROOT}\n")


# ─── SUBPROCESS LAUNCHER ───────────────────────────────────────────
def start_engine(title, script_path):
    """Open a new CMD window, activate the venv, and run the script."""
    cmd = (
        f'start "{title}" cmd /k '
        f'""{ACTIVATE}" && "{PYTHON}" "{script_path}""'
    )
    subprocess.Popen(cmd, shell=True, cwd=ROOT)


# ─── MAIN ───────────────────────────────────────────────────────────
def main():
    print()
    print("=" * 64)
    print("  ClarityOS Launcher v2")
    print("=" * 64)
    print(f"  ROOT:    {ROOT}")
    print(f"  ENGINE:  {ENGINE}")
    print(f"  PYTHON:  {PYTHON}")
    print("=" * 64)
    print()

    verify_paths()

    print("  [1/3] Markoff Engine...")
    start_engine("ClarityOS — Markoff Engine", MARKOFF)
    time.sleep(1.5)

    print("  [2/3] Kernel...")
    start_engine("ClarityOS — Kernel", KERNEL)
    time.sleep(1.5)

    print("  [3/3] Dispatcher...")
    start_engine("ClarityOS — Dispatcher", DISPATCHER)

    print()
    print("  [✓] All three engine windows launched.")
    print("      Close this window or press Ctrl+C to exit.\n")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n  Launcher closed.")


if __name__ == "__main__":
    main()


