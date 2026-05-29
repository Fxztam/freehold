# TODO: Freehold Source zu Go EXE

Dieses Dokument beschreibt den aktuellen, funktionierenden Weg von Freehold-Source (`.fh`) zu einer nativen Windows-EXE ueber den Go-Codegen.

Status: funktioniert fuer Entry-Module, die eine Freehold `procedure main()` enthalten. Library-artige Module ohne generierte `Main()`-Routine erzeugen weiterhin ein Go-Projekt, aber keine EXE.

## Ziel

Aus einer Freehold-Quelle soll reproduzierbar entstehen:

1. ein generiertes Go-Projekt,
2. ein Go-Wrapper unter `cmd/<exe-name>/main.go`,
3. ein `build.cmd`, das `go test ./...` und danach `go build` ausfuehrt,
4. eine native Windows-EXE unter `bin/<exe-name>.exe`,
5. ein Runtime-Test durch direktes Ausfuehren der EXE.

## Voraussetzungen

- Ausfuehrung aus dem Freehold-Repository-Root.
- Python-CLI ist verfuegbar: `python -m freehold ...`.
- Go ist installiert und im PATH.
- Das Freehold-Entry-Modul enthaelt eine `procedure main()`.

Pruefung des Repository-Roots:

```powershell
Get-Location
```

Erwarteter Root in dieser Workspace-Session:

```text
D:\works\Work-VeraFlow\freehold
```

## Befehlsschema

```powershell
python -m freehold go-codegen-project <entry.fh> --output-dir <out-dir> --json <out-dir>\_project.json --emit-executable --executable-name <exe-name>
```

Danach:

```powershell
Push-Location <out-dir>
.\build.cmd
.\bin\<exe-name>.exe
Pop-Location
```

## Was generiert wird

Bei einem Entry-Modul mit `procedure main()` entstehen unter dem Output-Verzeichnis typischerweise:

```text
<out-dir>/
  go.mod
  build.cmd
  _project.json
  cmd/<exe-name>/main.go
  bin/<exe-name>.exe
  ... generierte Go-Packages ...
```

Der generierte Wrapper sieht sinngemaess so aus:

```go
package main

import (
    app_main "freehold.local/app/main"
)

func main() {
    app_main.Main()
}
```

Das generierte `build.cmd` sieht sinngemaess so aus:

```cmd
@echo off
setlocal
go test ./...
if errorlevel 1 exit /b %errorlevel%
go build -trimpath -o bin\<exe-name>.exe .\cmd\<exe-name>
```

## Beispiel 1: Compiler-V1 Runtime Demo

Freehold Entry Source:

```text
examples/compiler_v1/15_result_abort_array_runtime_builtins/App/Main.fh
```

Importierte Module:

```text
examples/compiler_v1/15_result_abort_array_runtime_builtins/Domain/Inventory.fh
examples/compiler_v1/15_result_abort_array_runtime_builtins/Domain/Types.fh
```

Build und Run:

```powershell
Remove-Item -Recurse -Force .\.tmp\manual_exe -ErrorAction SilentlyContinue
python -m freehold go-codegen-project .\examples\compiler_v1\15_result_abort_array_runtime_builtins\App\Main.fh --output-dir .\.tmp\manual_exe --json .\.tmp\manual_exe\_project.json --emit-executable --executable-name freehold_runtime_demo
Push-Location .\.tmp\manual_exe
.\build.cmd
.\bin\freehold_runtime_demo.exe
Pop-Location
```

Erzeugte EXE:

```text
.tmp/manual_exe/bin/freehold_runtime_demo.exe
```

Erwartete Runtime-Ausgabe:

```text
summary = SKU001@north
json has sku = 8
max score = 4
total = 16
third = SKU-003
```

Dieses Beispiel testet mehrere Compiler-Flaechen zugleich:

- Imports ueber mehrere Module,
- Records,
- `Result<Array<...>, Error>`,
- Contract-Zugriff via `value[index].field`,
- `Json.stringify`,
- `String.*`,
- `Math.*`,
- `BigInteger`,
- direkte Runtime-Ausfuehrung als EXE.

## Beispiel 2: Feynman Demo

Freehold Entry Source:

```text
examples/ChudnovskyFeynmanPoint.fh
```

Build und Run:

```powershell
Remove-Item -Recurse -Force .\.tmp\feynman_exe -ErrorAction SilentlyContinue
python -m freehold go-codegen-project .\examples\ChudnovskyFeynmanPoint.fh --output-dir .\.tmp\feynman_exe --json .\.tmp\feynman_exe\_project.json --emit-executable --executable-name feynman_demo
Push-Location .\.tmp\feynman_exe
.\build.cmd
.\bin\feynman_demo.exe
Pop-Location
```

Erzeugte EXE:

```text
.tmp/feynman_exe/bin/feynman_demo.exe
```

Erwartete Runtime-Ausgabe:

```text
Feynman point at decimal digits 762..767 = 999999
```

## Automatisierter Smoke-Test

Der Compiler-Example-Smoke baut inzwischen fuer unterstuetzte Examples mit `procedure main()` echte EXEs und vergleicht fuer Log-Beispiele zusaetzlich die stdout-Ausgabe der EXE.

```powershell
.\verify-compiler-examples.cmd
```

Erwartetes Ergebnis:

```text
[OK] Compiler example smoke passed.
```

## Wichtiger Randfall: Module ohne main

Nicht jedes gueltige Freehold-Modul ist ein ausfuehrbares Programm. Beispiel: ein Modul kann nur Funktionen exportieren und keine `procedure main()` enthalten.

In diesem Fall gilt:

- `go-codegen-project` erzeugt weiterhin ein Go-Projekt,
- `build.cmd` fuehrt weiterhin `go test ./...` aus,
- es wird kein `cmd/<exe-name>/main.go` erzeugt,
- es wird keine EXE gebaut,
- die CLI meldet:

```text
[INFO] Go executable not emitted: entry module has no Main() routine
```

Probe-Beispiel:

```powershell
python -m freehold go-codegen-project .\examples\compiler_v1\04_result_abort\App\Main.fh --output-dir .\.tmp\no_main_probe --json .\.tmp\no_main_probe\_project.json --emit-executable --executable-name no_main_probe
```

## Aktueller Stand

Erfolgreich validiert:

- `freehold_runtime_demo.exe` aus `examples/compiler_v1/15_result_abort_array_runtime_builtins/App/Main.fh`,
- `feynman_demo.exe` aus `examples/ChudnovskyFeynmanPoint.fh`,
- `verify-compiler-examples.cmd` mit EXE-Build und Runtime-Log-Vergleich.
- **Automatische Generierung von Release-Builds:** Erfolgreiche Stage3-Builds werden automatisch aus dem `.tmp`-Verzeichnis nach `bin/` kopiert.
- **Natives Verzeichnis-Management:** Automatische Erstellung übergeordneter Ordnerstrukturen bei `File.write_string` über `os.MkdirAll` im Go-Codegen.
- **Dotted-Identifier Parsing:** Voll-natives Parsing von hierarchischen Modulpfaden (z. B. `examples.ChudnovskyFeynmanPoint`) und Importen in `Parser.fh` über `parse_dotted_identifier`.

Committed Code-Slice:

```text
593d9dc Add Go executable runtime smoke
```

Noch offen fuer spaetere Haertung:

- stabiler CLI-Komfortbefehl wie `freehold build-exe <entry.fh>`,
- Cross-Platform Build-Skripte neben Windows `build.cmd`,
- optionale Aufnahme von EXE-Builds in weitere Gates.
