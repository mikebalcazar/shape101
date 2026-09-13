# shape101 · resultados de la prueba de concepto

Una fila por medición. Se llena con números, no con adjetivos. Veredicto por paso
al final de cada bloque: **pasa / no pasa / pasa con poda**.

## P0 · Kernel (medido por el chat draw101, 12-sep-2026, Linux)

| Medición | Valor | Umbral | Veredicto |
|---|---|---|---|
| build123d / cadquery-ocp instalan con pip | sí (0.11.1) | sí | pasa |
| Peso de `OCP` en disco | 160 MB | — (se mide empotrado en P1) | pendiente |
| Extruir + booleana + redondeo (tablero 900×600×18) | 32 ms | < 500 ms | pasa |
| STEP + STL | 31 ms | < 1 s | pasa |
| Teselado (1 556 vértices) | 17 ms | < 100 ms | pasa |
| Vista 2D planta con ocultas (HLR) | 1 ms | < 500 ms | pasa |

## P1 · Windows y peso empotrado

| Medición | Valor | Umbral | Veredicto |
|---|---|---|---|
| `site-packages` antes / después de build123d | | — | |
| Versión cadquery-ocp en Windows | | — | |
| MB del instalador NSIS vacío con el Python | | < 400 MB | |
| Arranque del motor en caliente | | < 3 s | |
| Arranque del motor en frío | | — | |

## P2 · Boceto de draw101 → sólido

| Medición | Valor | Umbral | Veredicto |
|---|---|---|---|
| `.t101x` leído con `core/t101x.py` | | sí | |
| Entidades convertidas (línea, arco, círculo, polilínea con bulge) | | las 4 | |
| STEP abre con las medidas del boceto | | sí | |

## P3 · Historial regenerable

| Medición | Valor | Umbral | Veredicto |
|---|---|---|---|
| Regenerar 10 operaciones | | — | |
| Regenerar 30 operaciones | | < 1 s | |
| Regenerar 60 operaciones | | — | |
| Referencias a caras sobreviven a cambiar una cota de abajo | | sí | |
| Método de referencia estable elegido | | — | |

## P4 · Vista 3D y empujar cara

| Medición | Valor | Umbral | Veredicto |
|---|---|---|---|
| Ida y vuelta arrastre → motor → pantalla (50 caras) | | < 100 ms | |
| fps al orbitar con 500 caras | | > 30 | |

## P5 · Salidas 2D a draw101

| Medición | Valor | Umbral | Veredicto |
|---|---|---|---|
| Planta, alzado, lateral y corte como `.t101x` | | sí | |
| Cotas en draw101 dan las medidas del sólido | | sí | |

## P6 · Presentación

| Medición | Valor | Umbral | Veredicto |
|---|---|---|---|
| glTF abre en visor web | | sí | |
| MB del glTF (mueble completo) | | < 10 MB | |

## Veredicto final

_(lo escribe Mike)_
