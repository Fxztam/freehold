import re
import os

def load_diag_specs(diag_path):
    codes = set()
    with open(diag_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("diag "):
                parts = line.split()
                if len(parts) >= 2:
                    codes.add(parts[1])
    return codes

def scan_sources(root_dirs):
    pattern = re.compile(r"FH-[A-Z0-9]+-[0-9]+")
    found = {}
    for r_dir in root_dirs:
        for root, dirs, files in os.walk(r_dir):
            # Skip virtual environments, git, etc.
            if any(p in root for p in [".git", ".venv", ".tmp"]):
                continue
            for file in files:
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            matches = pattern.findall(line)
                            for match in matches:
                                if match not in found:
                                    found[match] = []
                                found[match].append((path, line_no))
                except Exception:
                    pass
    return found

def main():
    diag_path = "spec/freehold.diag"
    spec_codes = load_diag_specs(diag_path)
    print(f"Loaded {len(spec_codes)} diagnostic codes from {diag_path}")
    
    source_dirs = ["go-frontend", "bootstrap", "freehold"]
    emitted_codes = scan_sources(source_dirs)
    print(f"Scanned compiler sources, found {len(emitted_codes)} unique diagnostic codes.")
    
    missing = []
    for code, occurrences in emitted_codes.items():
        if code not in spec_codes:
            missing.append((code, occurrences))
            
    if missing:
        print("\n--- Diagnostic Codes in Compiler Sources but MISSING from freehold.diag ---")
        for code, occurrences in sorted(missing):
            print(f"\nCode: {code}")
            for path, line in occurrences[:5]:
                print(f"  at {path}:{line}")
            if len(occurrences) > 5:
                print(f"  ... and {len(occurrences) - 5} more occurrences")
    else:
        print("\nAll diagnostic codes in compiler sources are present in freehold.diag!")

if __name__ == "__main__":
    main()
