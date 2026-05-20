# Freehold EBNF Checker

Local browser checker for Freehold EBNF files.

Run it from the repository root through a local HTTP server so the page can load the grammar with `fetch`:

```powershell
c:/python314/python.exe -m http.server 8000
```

Then open the checker:

```text
http://localhost:8000/tools/ebnf-checker/chk_ebnf.htm
```

Use **Load repo freehold.ebnf** to load `freehold/grammar/freehold.ebnf`, then **Parse**.

The generated railroad diagram page is available next to it:

```text
http://localhost:8000/tools/ebnf-checker/railroad.html
```
