# Open: Generics und Templates in Freehold

Stand: 2026-05-24

Status: V1b abgeschlossen; Bounds, Inference, qualifizierte generische Calls und Codegen-Monomorphisierung fuer V2/V3 geparkt

Dieses Dokument haelt die erste Entscheidung zur Aufnahme von Generics in Freehold fest. V1b Record- und Function-Generics sind implementiert und conformance-geprueft. Bounds, Inference, qualifizierte generische Calls, monomorphisierte Codegen-Artefakte und generische IDL-Monomorphisierung bleiben V2/V3.

## Ausgangsfragen

Koennen wir Generics auch mit Templates abbilden?

Wollen wir Generics in Freehold?

## Kurzantwort

Ja. Freehold sollte Generics bekommen. Die beste erste Umsetzung ist:

```text
Sprachfeature:
  Generics / Type Parameters

Compiler-Implementierung:
  Template-Instanziierung / Monomorphisierung
```

Generics sind also das sichtbare Sprachmodell. Templates sind die interne Technik, mit der der Compiler konkrete Instanzen erzeugt.

## Grundsatzentscheidung

Freehold soll nach aussen Generics anbieten:

```fh
type Box<T> is record
    item: T
end

function identity<T>(x: T) returns T
is
    return x
end identity
```

Intern erzeugt der Compiler konkrete Instanzen:

```text
Box<Integer>
Box<String>
identity<Integer>
identity<String>
```

Das ist aehnlich wie bei Rust oder C++: Zur Compile-Zeit entstehen konkrete Versionen fuer die verwendeten Typen.

## Warum Generics fuer Freehold sinnvoll sind

Freehold hat bereits eingebaute generische Typformen:

```fh
Array<Integer, 3>
Result<String, NotFound>
```

User-Generics sind die natuerliche Fortsetzung davon.

Generics helfen besonders bei:

- wiederverwendbaren Record-Typen wie `Box<T>` oder `Page<T>`
- wiederverwendbaren Funktionen wie `identity<T>` oder `unwrap<T>`
- Runtime-Typen wie `Task<T>`, `JoinHandle<T>` und `Channel<T>`
- gRPC/IDL-Modellen wie `Response<T>` oder `Page<T>`
- spaeterem Go-Codegen und finalem Freehold Image Builder

## Warum Monomorphisierung als Umsetzung passt

Monomorphisierung bedeutet: Jede verwendete generische Instanz wird zu einem konkreten Typ oder einer konkreten Routine ausgearbeitet.

Beispiel:

```fh
let int_box: Box<Integer> = Box<Integer> { item: 1 }
let text_box: Box<String> = Box<String> { item: "hi" }
```

Compiler-intern entstehen:

```text
Box__Integer
Box__String
```

Vorteile:

- keine Type-Erasure-Komplexitaet
- keine Runtime-Typmagie fuer V1
- gute statische Fehler
- guter Fit fuer native Performance
- einfacher Vergleich zwischen Interpreter, Go-Compiler und spaeterem Image Builder
- klare Codegen-Ziele fuer Go und spaeter Native Code

## Begriffsklaerung

Freehold sollte das Feature nicht als "C++ Templates" verkaufen, wenn kein C++-Template-Metaprogramming gewollt ist.

Empfohlene Formulierung:

```text
Parametrische Generics mit Template-Monomorphisierung.
```

Nicht gemeint ist:

- beliebige Compile-Time-Programmierung
- partielle Spezialisierung in V1
- Overload-Metaprogramming
- SFINAE- oder C++-Template-artige Fehlerkaskaden

## Generics V1

Der erste Slice sollte klein bleiben.

Umfang:

- Type Parameters auf Records
- Type Parameters auf Functions
- explizite Type Arguments
- Monomorphisierung verwendeter Instanzen
- stabile Diagnostics fuer einfache Generic-Fehler
- keine Bounds
- keine Variance
- keine Specialization
- keine Type Erasure

Beispiel:

```fh
type Box<T> is record
    item: T
end

function unwrap<T>(box: Box<T>) returns T
is
    return box.item
end unwrap

procedure main()
is
    let b: Box<Integer> = Box<Integer> { item: 1 }
    let x: Integer = unwrap<Integer>(b)
end main
```

## Syntax-Vorschlag

Record-Generics:

```fh
type Box<T> is record
    item: T
end
```

Function-Generics:

```fh
function identity<T>(x: T) returns T
is
    return x
end identity
```

Explicit Type Arguments:

```fh
let x: Integer = identity<Integer>(1)
```

Generic Record Literal:

```fh
let b: Box<Integer> = Box<Integer> { item: 1 }
```

## Umgesetzt: Generics V1a

Der erste gruene Slice ist umgesetzt:

- generische Record-Deklarationen: `type Box<T> is record ... end record`
- konkrete generische Typverwendungen: `Box<Integer>`
- generische Record-Literals: `Box<Integer> { item: 1 }`
- rekursive Typargumente in Type-Refs
- Template-Instanziierung im Python-Verifier fuer verwendete Record-Instanzen
- Go-Frontend-Parsing und DHParser-Conformance fuer Record-Generics
- stabile Diagnostics:
  - `FH-GEN-5002 duplicate_type_parameter`
  - `FH-GEN-5010 missing_type_argument`
  - `FH-GEN-5011 too_many_type_arguments`
  - `FH-GEN-5012 non_generic_type_used_with_type_arguments`

Noch nicht umgesetzt in V1a:

- generische Funktionen
- Type-Inference
- Bounds oder Traits
- explizite Monomorphisierungsartefakte fuer Codegen
- `FH-GEN-5001`, `FH-GEN-5003`, `FH-GEN-5020`, `FH-GEN-5021`

## Umgesetzt: Generics V1b

Der zweite Slice ergaenzt generische Funktionen:

- generische Function-Deklarationen: `function identity<T>(x: T) returns T`
- explizite unqualifizierte Function-Calls: `identity<Integer>(1)`
- generische Signatur-Substitution am Call-Site
- generische Funktionskoerper-Pruefung mit Type-Parameter-Kontext
- generische Funktionen ueber generischen Records, z. B. `unwrap<T>(box: Box<T>) returns T`
- Go-Frontend-Parsing und DHParser-Conformance fuer Function-Generics
- stabile Diagnostics:
  - `FH-GEN-5030 missing_routine_type_argument`
  - `FH-GEN-5031 wrong_routine_type_argument_count`
  - `FH-GEN-5032 non_generic_routine_used_with_type_arguments`

Bewusste V1b-Grenze:

- generische Function-Calls sind zunaechst unqualifiziert: `identity<Integer>(1)`
- qualifizierte generische Calls wie `Pkg.identity<Integer>(1)` bleiben spaeter
- Type-Inference bleibt aus; Type-Args sind explizit
- keine Bounds, Traits oder Specialization

Validierter Stand fuer V1b:

- `python -m freehold.tests.language_runner --module 22_generics`: `10/10`
- Semantic-Diagnostics: `76/76`
- Spec-Diagnostics: `99/99`, `0` Failures
- Parser-Conformance: passed
- AST-Shape: `248/248`
- Semantic-AST: `248/248`
- Go-Frontend-Tests: passed

AST-Artefakte zeigen generische Funktionen in V1b vor Monomorphisierung. Die Monomorphisierung ist aktuell eine Verifier-/Signatur-Substitution am Call-Site; explizite Codegen-Artefakte fuer konkret erzeugte Funktionsinstanzen bleiben ein spaeterer Slice.

## Type Inference

Type inference sollte in V1 konservativ sein.

Empfehlung fuer V1:

```text
Explicit type arguments are required for generic functions and generic record literals.
```

Optional spaeter:

```text
Infer type parameters only from function arguments, not from return type.
```

Beispiel spaeterer V2-Komfort:

```fh
let x: Integer = identity(1)
```

V1 darf aber zunaechst verlangen:

```fh
let x: Integer = identity<Integer>(1)
```

## Bounds und Traits

Bounds bleiben ausserhalb von V1.

Spaeter moeglich:

```fh
function contains<T: Eq>(items: Array<T, 10>, needle: T) returns Boolean
is
    ...
end contains
```

V1 soll keine Trait- oder Interface-Bounds einfuehren. Dadurch bleibt die erste Monomorphisierung deutlich einfacher.

## Nicht Teil von Generics V1

- Variance-Regeln wie `in` / `out`
- Trait Bounds
- Interfaces oder Traits
- Associated Types
- Const Generics
- Higher-ranked Bounds
- Specialization
- Trait Objects
- Type Erasure
- impl Trait / Existential Types
- generische Module
- Template-Metaprogramming

## Diagnostics V1

Erwartete erste Diagnostics:

```text
FH-GEN-5001 undeclared_type_parameter
FH-GEN-5002 duplicate_type_parameter
FH-GEN-5003 type_parameter_shadowing
FH-GEN-5010 missing_type_argument
FH-GEN-5011 too_many_type_arguments
FH-GEN-5012 non_generic_type_used_with_type_arguments
FH-GEN-5013 generic_type_requires_type_arguments
FH-GEN-5020 cannot_instantiate_generic
FH-GEN-5021 recursive_monomorphization_limit
```

Spaetere Diagnostics fuer Bounds und Inference:

```text
FH-GEN-5101 type_bound_not_satisfied
FH-GEN-5102 cannot_infer_type_parameter
FH-GEN-5103 ambiguous_generic_instantiation
```

## Compiler-Pipeline fuer Generics

Empfohlene spaetere Struktur:

```text
1. SymbolTableBuilder
   sammelt generische Signaturen und Typ-Parameter

2. NameResolver
   loest normale Namen und Type-Parameter-Namen auf

3. TypeChecker
   prueft generische Deklarationen unter Type-Parameter-Kontext

4. GenericInstantiator / TemplateInstantiator
   erzeugt konkrete Instanzen fuer verwendete Typargumente

5. PostMonomorphTypeChecker
   prueft konkrete Instanzen final

6. Codegen
   erzeugt Go-Code oder spaeter Native/Image-Code aus konkreten Instanzen
```

Der bestehende `Verifier` kann V1 vorbereiten, aber langfristig sollte Generics ein Anlass sein, die Semantik in klarere Phasen aufzuteilen.

## Interaktion mit bestehenden Typformen

Bestehende eingebaute Generic-Formen bleiben gueltig:

```fh
Array<Integer, 3>
Result<String, NotFound>
```

Offene Designfrage: Werden `Array<T, N>` und `Result<T, E>` langfristig echte generische Standardtypen oder bleiben sie eingebaute Sonderformen?

Empfehlung:

```text
Kurzfristig:
  eingebaute Sonderformen beibehalten

Langfristig:
  in Richtung Standardbibliothek / Core Generic Types migrieren
```

## Interaktion mit Runtime Tasks

Generics sind wichtig fuer die geplante Runtime:

```fh
type Task<T> is opaque
type JoinHandle<T> is opaque
type Channel<T> is opaque
```

Moegliche APIs:

```fh
function spawn<T>(work: Function<T>) returns JoinHandle<T>
function await<T>(handle: JoinHandle<T>) returns T
function channel<T>(capacity: Integer) returns Channel<T>
```

Diese APIs brauchen Generics, bevor sie sauber in Freehold selbst modelliert werden koennen.

## Interaktion mit gRPC/IDL

Generics koennen spaeter IDL-Modelle kompakter machen:

```fh
type Page<T> is record
    items: Array<T, 100>
    total: Integer
end

type Response<T> is record
    item: T
end
```

Offen bleibt, ob generische Records direkt als Protobuf Messages erlaubt sind. Protobuf selbst kennt keine generischen Messages. Daher muesste Freehold generische IDL-Typen vor `.proto`-Generation monomorphisieren.

Beispiel:

```text
Page<UserReply> -> Page_UserReply message
Response<UserReply> -> Response_UserReply message
```

## Offene Fragen

1. Werden Type Arguments in V1 immer explizit verlangt?
2. Welche Syntax nutzt Freehold fuer generische Record-Literals: `Box<Integer> { ... }`?
3. Werden Type Parameters in Diagnostics als normale Namen mit Reservierungsregeln behandelt?
4. Wie werden monomorphisierte Namen intern stabil gebildet?
5. Gibt es eine harte Monomorphisierungsgrenze pro Build?
6. Werden generische Funktionen in AST-Artefakten vor oder nach Monomorphisierung sichtbar?
7. Wann werden Bounds und Traits eingefuehrt?

## Empfehlung

Freehold sollte Generics bekommen, aber in kleinen Slices:

```text
Generics V1:
  records + functions + explicit type arguments + monomorphization

Generics V2:
  einfache Inference aus Funktionsargumenten

Generics V3:
  Trait/Interface Bounds

Generics V4:
  Runtime/Task/Channel APIs mit generischen Typen

Generics V5:
  gRPC/IDL Monomorphisierung fuer generische Messages
```

Klares Votum: Generics ja. Templates nur als interne Umsetzung.
