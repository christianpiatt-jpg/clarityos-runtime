import sys, os

print("WORKING DIR:", os.getcwd())
print("\nSYS.PATH:")
for p in sys.path:
    print("   ", p)
