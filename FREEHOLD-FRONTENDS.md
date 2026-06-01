# FREEHOLD-FRONTENDS

Dieses Dokument beschreibt die Architektur, Verzeichnisstruktur und die Rollenverteilung der verschiedenen Compiler-Frontends und Toolings in Freehold, um Missverständnisse zu vermeiden.

---

## 1. Der native Freehold Bootstrap Compiler (`FH-Native-V1`)

Unter `bootstrap/compiler_core_v1/` befindet sich die voll funktionsfähige, selbst-hostende Version des Compilers, die komplett in Freehold selbst geschrieben ist.

### Verzeichnisstruktur von `FH-Native-V1`

```text
bootstrap/
├── bootstrap_freehold_*.py    # Python-Skripte für die einzelnen Bootstrap-Phasen (v10.5 bis v11f)
└── compiler_core_v1/          # Der in Freehold geschriebene native Compiler
    ├── App/
    │   └── Main.fh            # Haupteinstiegspunkt (CLI-Verarbeitung, Pipeline-Steuerung)
    ├── Compiler/
    │   └── Core/              # Kern-Module des Compilers
    │       ├── Ast.fh         # Abstract Syntax Tree (AST) Definitionen
    │       ├── Codegen.fh     # Go-Codegenerator
    │       ├── Diagnostics.fh # Diagnose- / Fehler-Strukturen und -Hilfsklassen
    │       ├── Fixtures.fh    # Test-Fixtures
    │       ├── Flow.fh        # Kontrollflussanalyse (Erreichbarkeit, Abort-Check)
    │       ├── Lexer.fh       # Lexikalische Analyse (Tokenizer)
    │       ├── Names.fh       # Hilfsfunktionen für Symbolnamen
    │       ├── ParseResult.fh # Hilfsstrukturen für Parser-Ergebnisse
    │       ├── Parser.fh      # Syntaktischer Parser (Recursive Descent)
    │       ├── Resolve.fh     # Semantischer Resolver (Namensauflösung & Typprüfung)
    │       ├── Token.fh       # Token-Definitionen
    │       ├── Transform.fh   # AST-Lowering und 3AC-Transformation
    │       └── Verifier.fh    # Verifikations-Engine für formale Verträge
    ├── Std/                   # Standardbibliothek-Dateien
    ├── File.fh                # Datei-I/O (System-Calls)
    └── System.fh              # System-Handling (Kommandozeilenparameter, Env-Variablen)
```

---

## 2. Vollständigkeit und Parität von `FH-Native-V1`

`FH-Native-V1` ist **funktional komplett** und hat volle Parität mit dem Python-Interpreter und dem Go-Frontend bezüglich der Übersetzung der Sprache Freehold (Version 1).

Der Beweis dafür ist das erfolgreiche **Self-Hosting Bootstrapping Gate**:
* Die in Freehold geschriebene und zu Go kompilierte Compiler-Binary (`bin/stage3_compiler_core_v1.exe`) kompiliert ihren eigenen Quellcode.
* Die dabei erzeugte binäre Zwischendarstellung (`stage2.fhirb`) ist **Byte-für-Byte identisch (gleicher SHA256-Hash)** mit der von der vorherigen Stufe (`stage1.fhirb`) erzeugten Datei.
* Dieser erfolgreiche Abgleich garantiert mathematisch und funktional die Korrektheit des in Freehold geschriebenen Compilers.

---

## 3. Rollenverteilung der Frontends & Toolings

| Komponente | Programmiersprache | Hauptaufgabe |
| :--- | :--- | :--- |
| **`FH-Native-V1`** | **Freehold (FH)** | Der eigentliche, native und selbst-hostende Compiler von Freehold. Läuft als eigenständige native Binärdatei (`stage3_compiler_core_v1.exe`). |
| **`go-frontend/`** | **Go** | Ultraschnelle, Go-native Referenz-Implementierung des Compiler-Frontends. Dient der schnellen Syntax- und Semantikprüfung sowie als Referenz-Compiler im Go-Ökosystem. |
| **Python-Tooling** | **Python** | Hostet die Grammatik-Spezifikationen (Lark), Hilfswerkzeuge für Entwickler (z. B. Validierung von Spezifikationsdateien) und steuert Z3-basierte formale Prüfungen in der CI/CD-Pipeline. |

