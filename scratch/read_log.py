from pathlib import Path

log_path = Path("d:/works/Work-VeraFlow/freehold/verify_stage3.log")
if log_path.exists():
    try:
        content = log_path.read_text(encoding="utf-16le")
    except Exception:
        content = log_path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "02_records_functions" in line:
            print(f"--- Occurrence at line {i} ---")
            for j in range(max(0, i-2), min(len(lines), i+25)):
                print(f"{j}: {lines[j]}")
else:
    print("Log file not found.")
