from pathlib import Path
path = Path("bootstrap/compiler_core_v1/Compiler/Core/Loader.fh")
lines = path.read_text(encoding="utf-8").splitlines()
for idx, line in enumerate(lines):
    if "set_routine" in line or "set_block" in line or "set_instruction" in line:
        if "function" in line or "procedure" in line or "is" in line:
            print(f"Start {idx+1}: {line}")
            for j in range(idx, min(idx+20, len(lines))):
                print(f"  {j+1}: {lines[j]}")
