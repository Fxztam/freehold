# Freehold IR Source Map

Stand: 2026-06-12

## Ziel

FH-IR bleibt die kanonische semantische Zwischendarstellung. Daneben fuehren wir ein separates Source-Map-/Source-Shape-JSON ein. Dieses Sidecar bewahrt die Informationen, die im kanonischen IR absichtlich nicht dominieren sollen: Moduldateien, Source-Reihenfolge, Source-Hash, Quellzeilen, stabile AST-Pfade und Start-Spans.

Das Ziel ist:

```text
FH-IR + Source-Map => rekonstruierbarer Freehold Source
```

Langfristig soll derselbe Gedanke auch fuer native Rueckwege gelten:

```text
LLVM/native metadata + Source-Map-kompatible Beschreibung => Freehold Source Skeleton
```

## Warum Nicht Im IR Selbst?

Compare-IR und FH-IR haben andere Aufgaben:

- Compare-IR ist ein Paritaets- und Coverage-Artefakt.
- FH-IR ist die ausfuehrbare, semantische Compiler-IR.
- Source-Map ist ein verlustarmer Rekonstruktions-Sidecar.

Damit koennen semantische Gates stabil bleiben, ohne Formatierungs-, Reihenfolge- oder Trivia-Fragen in jeden IR-Vergleich hineinzuziehen.

## LLVM-freundliche IR-Regeln

Damit wir uns spaeter beim nativen LLVM-Backend nicht selbst blockieren, soll FH-IR bewusst niedrig genug fuer Codegen sein, aber hoch genug fuer Freehold-Semantik bleiben:

- **Typed SSA/Block-Form als Zielrichtung:** Routinen werden mittelfristig in Basic Blocks mit expliziten Terminatoren (`return`, `branch`, `cond_branch`, `abort`) und typisierten temporaries abgesenkt.
- **Explizite Speicheroperationen:** Mutable lokale Werte, Records und Arrays werden ueber klare `alloca`/`load`/`store`/`field_addr`/`index_addr`-artige Operationen modelliert, statt Source-Zuweisungen im Backend neu erraten zu muessen.
- **Semantische Operationen vor Backend-Details:** Freehold-Konzepte wie `Result`, `Abort`, Contracts, Channels und Records bleiben als IR-Operationen oder Metadaten sichtbar, bis ein Lowering-Pass sie gezielt fuer LLVM absenkt.
- **Stabile Symbol- und Node-IDs:** IR-Knoten, Blocks, Temporaries und Source-Map-Knoten bekommen deterministische IDs. Diese IDs sind die Bruecke fuer Debug-Info, Re-Source und spaetere Native-Rueckabbildung.
- **Keine Source-Trivia im IR-Kern:** Kommentare, Originalreihenfolge, Zeilentexte und Formatierungsdetails bleiben im Source-Map-Sidecar. Das LLVM-Backend muss nur stabile IDs und Spans durchreichen.
- **Keine Go-spezifische IR:** FH-IR darf weder Go-Package-Strukturen noch Go-Namenssanitisierung als kanonische Semantik tragen. Go- und LLVM-Backends sind zwei Lowering-Ziele derselben Freehold-IR.
- **Lowering in Phasen:** AST/Verified Program -> Source-Shape + Semantic FH-IR -> executable Block IR -> backend-specific Go/LLVM. Jeder Schritt soll ein eigenes JSON-/Gate-Artefakt bekommen koennen.

Praktisch heisst das: Der jetzige `fh-source-map-v0` Export ist kein Ersatz fuer die ausfuehrbare IR, sondern die Rueckverfolgbarkeits-Schicht, die spaeter neben Block-IR und LLVM-Debug-Metadaten liegt.

## Aktueller Backend-Fluss

Der operative Native-Pfad bedient aktuell das Go-Backend:

```text
Freehold Source
  -> Parser / AST
  -> Verifier / Semantic Model
  -> FH-IR / Compare-IR / Source-Map Artefakte
  -> Go-Codegen
  -> Go build
  -> Native EXE
```

Das bedeutet: Go ist der erste produktive Backend-Konsument der Compiler-Pipeline. Demos, FFI-Shims und native Executables laufen heute ueber diesen Weg.

Die Architekturregel bleibt aber: **FH-IR darf nicht Go-IR werden.** Go ist ein Lowering-Ziel, nicht die kanonische Form der Freehold-Semantik. Dieselbe IR soll spaeter weitere Ziele bedienen koennen:

```text
FH-IR / Block-IR
  -> Go Backend
  -> LLVM Backend
  -> Interpreter / VM
  -> WhyML / SMT
```

Konsequenz: Go-spezifische Details wie Package-Pfade, Imports, Namenssanitisierung, Error-Wrapping oder Runtime-Helfer bleiben im Go-Lowering. FH-IR beschreibt stabile Freehold-Semantik, Typen, Kontrollfluss, Effekte und Source-IDs.

## Schema V0

Der erste Slice heisst `fh-source-map-v0` und enthaelt projektweit:

- `entry_module`
- `module_order`
- pro Modul:
  - `source_file`
  - `source_sha256`
  - `source_lines`
  - AST-Baum mit stabilen `id`-Pfaden
  - `parent_id`, `role`, `index`
  - `kind`, Name-/Typ-/Operator-Kurzinfos
  - Start-Span mit `line`, `column`, `line_text`

V0 ist bewusst ein Sidecar aus dem Python-Frontend. Der naechste Portierungsschritt ist ein kompatibler Export im Go-Frontend/FH-Native Compiler-Core.

Der kompatible Go-Frontend-Exporter liegt unter `go-frontend/cmd/go-source-map` und nutzt dasselbe Schema `fh-source-map-v0`. Damit kann der Source-Map-Sidecar nun aus beiden Frontends erzeugt und im naechsten Schritt per Paritaetsgate verglichen werden.

## CLI

```powershell
$env:PYTHONPATH="."
py -m freehold source-map .\examples\compiler_v1\44_go_ora_ffi_demo\App\Main.fh --output .\.tmp\demo44.source-map.json
```

Go-Frontend:

```powershell
Push-Location .\go-frontend
go run .\cmd\go-source-map --out ..\.tmp\sample01.go.source-map.json ..\examples\compiler_v1\01_minimal_app\App\Main.fh
Pop-Location
```

Aktueller Smoke-Stand:

- `01_minimal_app`: Python und Go liefern `fh-source-map-v0`, Entry `App.Main`, Root `Program` und denselben normalisierten `source_sha256`.
- `03_cross_module_calls`: Python und Go liefern dieselbe Modulordnung `App.Main, Domain.Rules`.
- `compare-source-map-compiler-v1.cmd`: 18 aktive Compiler-V1-Samples liefern Python/Go-Paritaet in der Source-Map-Contract-Projektion; die frueheren Stage-1-IR-Skips `19_async_scope_runtime`, `20_grpc_binding` und der heutige Generics-Pfad `26_generic_function` sind im Source-Map-eigenen Manifest aktiv.
- `compare-source-map-compiler-v1-stage2.cmd`: 6 aktive Stage-2-Enrichment-Samples (`16` bis `21`) liefern Python/Go-Paritaet in derselben Source-Map-Contract-Projektion; das Gate ist check-only und baselinefrei.
- `bootstrap/compiler_core_v1/Compiler/Core/SourceMap.fh`: FH-Native Compiler-Core enthaelt den V0-Strukturkern als eigene Records/Helper (`SourceMapSpan`, `SourceMapNode`, `SourceMapModule`, `SourceMapDocument`), ist im Stage3-Golden-Gate verdrahtet und laesst sich per `python -m freehold source-map` exportieren.
- `verify-stage3-compiler-core-v1.cmd`: Stage3 Compiler-Core-Gate ist gruen mit generiertem `compiler/core/sourcemap/sourcemap.go`; das Gate setzt ohne expliziten Override `FREEHOLD_PROVER=none`, weil es Codegen/Runtime-Golden prueft und nicht den tiefen SMT-Proverpfad von `Compiler.Core.Lowering`.
- `44_go_ora_ffi_demo`: Python und Go exportieren erfolgreich; die Go-Frontend-Kanten fuer Result-Feldzugriffe (`.ok`, `.value`, `.error`) und FFI/JSON-Annotationen sind geschlossen.

## Naechste Slices

1. Optionales Pair-Artefakt im IR-Command: `--source-map <file>`.
2. Re-Source-Prototyp: normalisierten Freehold-Source aus `FH-IR + Source-Map` erzeugen.
3. Spaeter: LLVM-Debug-/Metadata-Mapping auf dieselbe Source-Shape-Struktur abbilden.
