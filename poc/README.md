# poc · la prueba de concepto de shape101

No es la app: es la medición que decide si shape101 va. Sigue paso a paso el
documento «shape101 · prueba de concepto» (Drive, 12-sep-2026). Cada paso es
una prueba `pN_*.py` que deja números o un sí/no; `RESULTADOS.md` es la tabla
con la que Mike decide.

```bash
python3.11 -m venv .venv && .venv/bin/pip install build123d playwright
DRAW101=../draw101 .venv/bin/python poc/verificar.py             # todas
.venv/bin/python poc/verificar.py p2 p3                             # sólo ésas
.venv/bin/python poc/verificar.py --resultados                      # y reescribe RESULTADOS.md
```

- `comun.py` — el reporte, con `r.numero(...)` para lo medido.
- `draw101_lector.py` — lee y escribe `.t101d` **con el motor de draw101**, sin
  tocarlo (variable `DRAW101` o carpeta hermana).
- `boceto.py` — entidades de draw101 → cara → sólido (build123d / OpenCascade).
- `muestras/` — bocetos de muestra hechos con draw101 y los STEP que salen.
- `salida/` — lo que deja cada corrida (no se versiona).
