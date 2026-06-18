import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "expected" / "manifest.json").read_text(encoding="utf-8"))

for group in manifest["groups"]:
    print(f"\n{group['group']}")
    for test in group["tests"]:
        diag = f" [{test['diagnostic']}]" if "diagnostic" in test else ""
        print(f"  {test['expected']:11} {test['file']}{diag}")
