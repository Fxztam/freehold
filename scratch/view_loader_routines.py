from pathlib import Path
path = Path("bootstrap/compiler_core_v1/Compiler/Core/Loader.fh")
lines = path.read_text(encoding="utf-8").splitlines()
for idx, line in enumerate(lines):
    if "load_project_graph" in line:
        print(f"Start {idx+1}: {line}")
        for j in range(idx, min(idx+30, len(lines))):
            print(f"  {j+1}: {lines[j]}")
