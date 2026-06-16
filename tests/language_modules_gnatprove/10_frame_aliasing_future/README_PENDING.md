# 10 Frame / Aliasing Future Tests

Diese Tests sind absichtlich als `.pending.fh` abgelegt, damit der aktuelle Runner sie nicht ausführt.
Sie werden aktiv, sobald Freehold eine explizite Frame-Semantik wie `modifies` / `assigns`
und eine Aliasing-Regel für mutable Parameter besitzt.

Aktivierung:

1. Syntax finalisieren, z. B. `modifies acc.balance` oder `assigns acc.balance`.
2. Dateien von `.pending.fh` nach `.fh` umbenennen.
3. Runner ausführen.
