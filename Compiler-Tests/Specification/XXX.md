Phase 1: Die verbleibenden nativen Verifizierungs-Ports 
         (aus TODO-PORTING-GO-NATIVE.md):
         Feldpfad-Abhängigkeitsanalyse (Field-Level Dependency Tracking):

Ziel: Die Abbildung von verschachtelten Records (z. B. acc.balance Modifikationen) in den depends Klauseln des Selbst-Hosters prüfen.
Aufgabe: Parser.fh und Ast.fh müssen Feldpfade innerhalb von depends verarbeiten und die Hilfsfunktion collect_mutated_vars in Verifier.fh muss diese Pfade (Trennung am Punkt .) korrekt erfassen.


Nativer WhyML Translation Layer (WhyMLCodeGen.fh):

Ziel: Übersetzung des hierarchischen Freehold-ASTs in die Why3-Spezifikationssprache zur Übergabe an fortgeschrittene Theoremprover (Coq, Alt-Ergo).
Aufgabe: Implementierung von WhyMLCodeGen.fh im Compiler-Kern mit Support für OCaml-Modulstrukturen, Referenzzellen (ref/!) und rekursiven Ausnahmebehandlungsblöcken.

Formale Nebenläufigkeits-Verifikation (Concurrency Verification):

Ziel: Statische Sicherheit von nebenläufigen Prozessen.
-------------------------------------------------------
Aufgabe:
Live-Prüfung von Channel-Invarianten: Bei channel_send muss bewiesen werden, dass das gesendete Objekt die Invariante des Kanals erfüllt (CallExpr.Invariant in Verifier.fh).
Task-Preconditions an Spawn-Points: Der Verifier muss statisch prüfen, ob übergebene Argumente an spawn-Aufrufen die Vorbedingungen (requires) der Zielroutine erfüllen.

Transitive Kontext-Propagierung in geschachtelten Blöcken:
----------------------------------------------------------
Ziel: Vollständige Weitergabe geladener Import- und Moduldefinitionen durch tief geschachtelte Schleifen, Verzweigungen und Case-Bedingungen im symbolischen Solver des Compiler-Kerns.


Phase 2: Weiterführende V2-Verifizierungsziele (aus TODO-FH-NATIVE-V2.md):
Exhaustiveness-Analyse (Vollständigkeitsprüfung) bei choice-Pattern-Matching:
-----------------------------------------------------------------------------
Ziel: Z3 soll mathematisch beweisen, dass alle deklarierten Varianten eines algebraischen Summentyps (choice) in einer case-Anweisung abgedeckt sind, sodass kein unvollständiger Zustand zur Laufzeit eintreten kann.

Endlichkeit und Termination von Map-/Assoziativ-Iterationen:
------------------------------------------------------------
Ziel: Beweisbarkeit der Schleifen-Termination bei der Iteration über dynamisch registrierte Schlüssel-Wert-Strukturen (Map<Knotationen) in SMT-LIB v2.



~~~~~~~~~~~~~~~~~~~~~~~~~~

2. Status der weiteren Meilensteine

A. Nativer WhyML Translation Layer (WhyMLCodeGen.fh)
Architektur: Der Übersetzer transformiert Freehold-ASTs in Why3-Syntax, um formale Beweise für fortgeschrittene Theorem Prover (wie Alt-Ergo, Coq) bereitzustellen.

Fortschritt: Derzeit ist die Struktur deklariert. In Stage 5 wird die vollständige Generierung von OCaml-kompatibler WhyML-Syntax portiert, einschließlich veränderlicher Referenzen (ref / !), Ausnahme-Rückgabeblocks für vorzeitiges Beenden (return) sowie Übersetzung von Schleifenvarianten und -invarianten.

B. Formale Nebenläufigkeits-Verifikation
Channel Invarianten: Statische Prüfung an channel_send-Punkten unter Einbeziehung von Z3, um sicherzustellen, dass die versendeten Nachrichten die Kanalinvariante erfüllen.
Spawn Preconditions & transitive Frame-Prüfungen: Validierung, dass die beim Thread-Spawn (spawn) übergebenen Argumente die Vorbedingungen (requires) der aufgerufenen Thread-Routine vollständig erfüllen.

C. Exhaustiveness-Analyse bei algebraischen choice Summentypen (V2-Ziel)
Ziel: Mathematischer Beweis durch Z3, dass bei einem case-Mustervergleich alle deklarierten Varianten eines algebraischen Summentyps (choice) abgedeckt sind, wodurch unvollständige Laufzeit-Abstürze ausgeschlossen werden.

D. Endlichkeit und Termination von Map-Iterationen (V2-Ziel)
Ziel: Automatische Generierung von Schleifenvarianten für Maps in SMT-LIB v2, um zu beweisen, dass die Iteration bezogen auf verbleibende Elemente in der Map nach endlichen Schritten terminiert.
