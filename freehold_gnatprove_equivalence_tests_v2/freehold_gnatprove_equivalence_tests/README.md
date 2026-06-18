# Freehold GNATprove Equivalence Tests

Dieses Paket enthält Freehold POS/NEG-Tests, die aus den bereitgestellten GNATprove/SPARK-Demos abgeleitet wurden.

Ziel ist nicht Ada syntaktisch zu kopieren, sondern GNATprove-Prüfklassen in Freehold-Prüfklassen abzubilden:

| GNATprove / SPARK | Freehold |
|---|---|
| `Pre` | `requires` |
| `Post` | `ensures` |
| `pragma Assert` | `check` |
| `pragma Loop_Invariant` | `invariant` |
| Overflow proof | Integer range / overflow proof |
| Array range proof | Array index proof |
| Division-by-zero proof | `q != 0` proof |
| Range conversion proof | target-range proof |
| Termination argument | `variant` |

## Struktur

```text
tests/proof_equivalence/gnatprove_paired/
  01_contract_overflow/
  02_array_bounds/
  03_loop_invariant/
  04_runtime_checks/
  05_assertions/
  06_callsite_precondition/
  07_integer_underflow/
  08_array_lower_upper_bounds/
  09_record_updates/
  10_frame_aliasing_future/       # aktiv, fully verified
```

Jeder Ordner enthält:

- `pos_*.fh` — soll statisch erfolgreich verifiziert werden.
- `neg_*.fh` — soll statisch fehlschlagen.
- `expected.txt` — erwartete Diagnoseklasse.

## Wichtig

Die NEG-Tests sind absichtlich so formuliert, dass Freehold sie nicht erst zur Laufzeit, sondern bereits während der statischen Prüfung ablehnen sollte.

## Erweiterte Abdeckung

Dieses Paket enthält nun zusätzliche GNATprove-Äquivalenzklassen:

1. Call-site Precondition-Fail: Aufruf einer korrekt spezifizierten Funktion mit ungültigem Argument.
2. Integer.First Underflow und Call-site-Underflow.
3. Array Lower-Bound und Upper-Bound getrennt.
4. Record-Field-Update mit `old(...)`-Postcondition.
5. Record-Update mit unbeabsichtigter Änderung eines zweiten Feldes.
6. Frame-/Aliasing-Tests als Pending-Gruppe, weil dafür eine spätere Freehold-Semantik wie `modifies` / `assigns` erforderlich ist.

Weiterhin offen für eine spätere Runde:

- Result-/Error-Pfade für Freehold-spezifische sichere APIs.
- Quantifier-Negativtest mit falscher Bereichsgrenze.
- Frame-/Aliasing-Tests aktivieren, sobald die Syntax final ist.

## Runner

`run_expected.py` ist ein generisches Runner-Skelett. Passe den Befehl `FREEHOLD_CMD` an Deinen Compiler/Verifier an.

Beispiel:

```bash
python run_expected.py --cmd "freehold verify"
```

oder:

```bash
python run_expected.py --cmd "python -m freehold verify"
```
