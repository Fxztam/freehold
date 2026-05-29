# TODO Conformance Baseline Tests

> [!IMPORTANT]
> **Grammatik & Parser Source of Truth:**
> - `freehold/grammar/freehold.lark` ist die exakt auszuführende Parser-Grammatik (Lark) und die primäre Source of Truth für den Parser.
> - `freehold/core/grammar_inline.py` (enthält `FREEHOLD_GRAMMAR`) enthält die exakt gespiegelte Inline-Variante der Lark-Grammatik und muss bei jeder Grammatikänderung absolut synchron gehalten werden.
> - Die verschiedenen EBNF-Dateien in `freehold/grammar/freehold*.ebnf` dienen primär der Spezifikation, Dokumentation oder Visualisierung (z. B. Syntax-Highlighting, Railroad-Diagramme) und dürfen **nicht** mit der aktiven Lark-Grammatik verwechselt werden.

## Ziel
Die Conformance-Baseline darf nicht beiläufig im normalen Verify-Lauf ueberschrieben werden.
Baseline-Updates sind ein bewusster, reviewter Vorgang.

## Entscheidungsregel: Wann Baseline regenerieren?
Nur regenerieren, wenn sich erwartetes Verhalten fachlich absichtlich geaendert hat.

Regeneration ist erlaubt, wenn mindestens einer dieser Punkte zutrifft:
- Parser-/Semantik-Verhalten wurde absichtlich geaendert (z. B. zuvor FAIL, jetzt parse_ok).
- Diagnostik-Inhalt, -Positionen oder -Struktur wurde absichtlich angepasst.
- AST-/IR-Shape wurde absichtlich geaendert (inkl. FH-IR Strukturveraenderungen).
- Neue Sprachfeatures oder neue gueltige/ungueltige Muster beeinflussen bestehende Erwartungsartefakte.

Keine Regeneration bei:
- reinem Refactoring ohne beabsichtigte Verhaltensaenderung,
- sporadischer Nicht-Deterministik,
- normalen lokalen Checks/CI-Checks,
- ungeklaerten Abweichungen ohne fachliche Freigabe.

## Entscheidungsregel: Go-Aenderung vs. Python-Semantikpfad
Wenn eine Go-seitige Aenderung das Sprachverhalten beeinflusst, muss der Python-Semantikpfad mitgezogen werden.

Verbindlich gilt:
- Parser-/Syntax-Aenderung ohne Semantik-Effekt:
   - Go-Parser anpassen,
   - ggf. DHParser-Grammatik/Parser-Artefakte nachziehen,
   - Python-Semantik nur anpassen, wenn Compare-Gates fachliche Drift zeigen.
- Semantik-/Diagnostik-/FH-IR-Aenderung:
   - Go und Python konsistent anpassen (insb. Verifier/FH-IR Export),
   - zugehoerige Baselines und Compare-Artefakte synchron aktualisieren.
- Reiner Go-Implementierungsfix ohne fachliche Verhaltensaenderung:
   - Python bleibt unveraendert,
   - alle Compare-/Conformance-Gates muessen weiterhin gruen bleiben.

Abschlusskriterium:
- Eine Go-Aenderung gilt erst als integriert, wenn der Full-Run ohne ungeklaerte Compare- oder Frozen-Gate-Abweichungen durchlaeuft.

## Verbindlicher Ablauf
1. Normalen Verify-Lauf ausfuehren (nicht-mutierend):
   - `cmd /c verify-parser-conformance.cmd`
    - V1-Gate ist standardmaessig aktiv.
    - Escape-Flag zum Deaktivieren:
       - `cmd /c verify-parser-conformance.cmd --disable-fhir-v1-gate`
2. Abweichungen pruefen:
   - Sind sie deterministisch?
   - Sind sie fachlich gewollt?
3. Nur bei "ja" Baseline-Update gezielt ausfuehren:
   - `cmd /c verify-parser-conformance.cmd --update-go-baseline`
   - `cmd /c verify-parser-conformance.cmd --update-python-baseline`
   - Bei kombinierten Updates:
     - `cmd /c verify-parser-conformance.cmd --update-go-baseline --update-python-baseline`
    - Bei V1-Baseline-Updates zusaetzlich (optional, wenn V1-Gate aktiv verwendet wird):
       - `python .\tools\compare_fhir.py --mode project-v1 --expected .\artifacts\fhir-v1 --update`
       - oder kurz: `cmd /c compare-fhir-v1-update.cmd`
   - Bei FH-IR-Aenderungen zusaetzlich:
     - `python .\tools\compare_fhir.py --update`
4. Baseline-Diff separat reviewen.
5. Baseline-Aktualisierung separat committen (bevorzugt eigener Commit).

Hinweis:
- Nach einem beabsichtigten Baseline-Update meldet Schritt 21 (Frozen/Additive-Guard) lokal weiterhin Veraenderungen,
  solange diese noch nicht reviewt und committed sind. Das ist erwartetes Schutzverhalten.

## CI-/Team-Policy
- Standard-Job: immer ohne Baseline-Update-Flag.
- Baseline-Update: nur manuell oder in explizitem Maintenance-Job mit Review-Pflicht.

## Review-Checkliste fuer Baseline-Updates
- [ ] Aenderungen sind reproduzierbar (zweiter Lauf identisch).
- [ ] Fachliche Ursache dokumentiert (PR-Beschreibung / Issue).
- [ ] Kein unbeabsichtigter Drift ausserhalb der erwarteten Bereiche.
- [ ] Compare-Reports plausibel.
- [ ] Additive/Frozen-Regeln weiterhin konsistent.
- [ ] Bei FH-IR-Updates: `python .\tools\compare_fhir.py` liefert `Mismatching FH-IR: 0`.
- [ ] Bei FH-IR-V1-Checks: `cmd /c compare-fhir-v1.cmd` liefert `Mismatching FH-IR: 0`.
- [ ] Verify-Standardlauf enthaelt das V1-Gate; nur bei Bedarf mit `--disable-fhir-v1-gate` abschalten.

## Implementierte Features & Schutzmechanismen
- **Explizites Baseline-Pflegeskript (`verify-parser-conformance-update-baseline.cmd`):**
  - Ein dediziertes Skript wurde angelegt, um die Go- und Python-Baselines kontrolliert zu aktualisieren. Es delegiert an `verify-parser-conformance.cmd` mit den entsprechenden Update-Flags.
- **CI-Guard-Integration:**
  - In `verify-parser-conformance.cmd` wurde eine Sperre integriert, die die Verwendung von Update-Flags in Standard-Pipelines verbietet. Ein Update wird verweigert, es sei denn, die Umgebungsvariable `FREEHOLD_ALLOW_BASELINE_UPDATE=1` ist explizit gesetzt.
- **Dirty-Repository-Schutz & `--force` Flag:**
  - Um unbeabsichtigten Drift oder unsaubere Baselines im Git-Repository zu verhindern, blockieren Updates standardmäßig, wenn nicht-committete oder untrackte Dateien im Repository vorhanden sind.
  - Dieser Block kann bewusst mit dem `--force` Parameter (oder der Umgebungsvariable `FORCE_BASELINE_UPDATE=1`) überschrieben werden.
- **Bypass des Additive-Test-Line-Checks:**
  - Der `verify_additive_test_line.py`-Check wird bei aktiven Baseline-Updates automatisch übersprungen, um Fehlalarme bei der bewussten Pflege der Artefakte zu vermeiden.

