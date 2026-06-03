from pathlib import Path


def main() -> None:
    source = Path("bootstrap/compiler_core_v1/Compiler/Core/Loader.fh")
    if not source.exists():
        raise SystemExit(f"missing loader source: {source}")
    print(f"Loader.fh is maintained directly: {source}")


if __name__ == "__main__":
    main()
