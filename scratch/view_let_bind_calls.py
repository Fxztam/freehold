from pathlib import Path
path = Path("freehold/core/symbolic.py")
lines = path.read_text(encoding="utf-8").splitlines()
start = -1
for idx, line in enumerate(lines):
    if "def let_bind_calls" in line:
        start = idx
        break
if start != -1:
    print("\n".join(lines[start:start+100]))
else:
    print("Not found")
