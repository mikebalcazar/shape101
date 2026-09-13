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

- `comun.py` — el reporte, con `r.numero(...)` para lo medido. Lo usa también
  `app/verificar.py`: por eso vive aquí y no se mueve.
- El kernel que la PoC escribió (`historial`, `nombres`, `boceto`,
  `draw101_lector`, `vistas2d`, `malla`) **vive en `app/motor/`** desde el
  bloque 1: una sola copia, y las pruebas de aquí importan de ahí.
- `motor_http.py` y `vista/` — el motor y la página de la PoC (P4, P6).
- `muestras/` — bocetos de muestra hechos con draw101 (`.t101d`).
- `salida/` — lo que deja cada corrida (no se versiona).
