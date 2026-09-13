# shape101 · resultados de la prueba de concepto

*Generado por `python poc/verificar.py --resultados` el 2026-09-13. Los números son de esa corrida; el veredicto de cada paso está escrito a mano en `poc/veredictos.json` después de mirarlos.*

## P0 · Kernel (medido por el chat draw101, 12-sep-2026, Linux)

| Medición | Valor | Umbral | Veredicto |
|---|---|---|---|
| build123d / cadquery-ocp instalan con pip | sí (0.11.1) | sí | pasa |
| Peso de `OCP` en disco | 160 MB | — (se mide empotrado en P1) | pendiente |
| Extruir + booleana + redondeo (tablero 900×600×18) | 32 ms | < 500 ms | pasa |
| STEP + STL | 31 ms | < 1 s | pasa |
| Teselado (1 556 vértices) | 17 ms | < 100 ms | pasa |
| Vista 2D planta con ocultas (HLR) | 1 ms | < 500 ms | pasa |

*Guion: `poc/p0_kernel.py`. Lo de abajo lo midió Jr. el 13-sep con `poc/verificar.py`.*

## P1 · Windows y peso empotrado

**Veredicto: sí en peso; el arranque en caliente queda en el límite del umbral.** Medido en un Windows de GitHub (windows-2025, Python 3.11.9) por el flujo `.github/workflows/p1-peso-windows.yml` (runs 3 y 4, commits 6fe9854 y 68901fc); el instalador quedó como artefacto del run 14 días por si Mike quiere instalarlo. **Aviso 1:** el arranque en frío del motor es de 10 s, y en caliente dio 2,89 s en una corrida y 3,31 s en la siguiente, en el mismo tipo de corredor: el umbral de 3 s no se cumple con margen, depende de la máquina. La primera apertura del día va a tardar y hay que esconderlo con una pantalla de arranque, como hace draw101; y si el arranque importa, la poda de lo que build123d arrastra (aviso 2) también acorta el import. **Aviso 2:** build123d arrastra 607 MB de site-packages (IPython, sympy, ezdxf, fontTools…) que el instalador comprime a 236 MB; hay poda posible (el paquete OpenCascade en sí, `OCP`, son 84 MB en Windows) y no hizo falta para cumplir el umbral. El paquete de OpenCascade se llama `cadquery-ocp-novtk` (7.9.3.1.1), no `cadquery-ocp`.

| Qué | Valor | Umbral | Cumple |
|---|---:|---|---|
| P1 site-packages antes / después de `pip install build123d` | 25 MB / 607 MB |  |  |
| P1 carpeta `OCP` en Windows | 84 MB |  |  |
| P1 versión de OpenCascade para Python | cadquery-ocp-novtk 7.9.3.1.1 (+ cadquery-ocp-proxy) |  |  |
| P1 Python empotrado (embed 3.11.9 + site-packages), sin comprimir | 627 MB |  |  |
| P1 instalador NSIS con Electron vacío y ese Python | 236 MB | < 400 MB | sí |
| P1 `import build123d` en frío (runs 3 y 4) | 10,00 s / 10,23 s |  |  |
| P1 `import build123d` en caliente (runs 3 y 4) | 2,89 s / 3,31 s | < 3 s | en el límite: sí / NO |
| P1 el Python empotrado importa build123d | sí | sí/no | sí |
| P1 modelado + STEP del tablero en Windows (incluye el import en caliente) | 2 920 ms |  |  |

## P2 · Boceto de draw101 → sólido

**Veredicto: sí.** Los bocetos se dibujaron con el motor de draw101 (con cotas) y se leen con él, sin tocarlo. Líneas, arcos, círculos y polilíneas con bulge se convierten en una cara exacta; el tablero recto y el redondeado dan área y volumen de fórmula, y el STEP reabre con las mismas medidas. Ojo: el documento decía «.t101x»; en draw101 eso es el proyecto de Taller 101, el dibujo es el «.t101d». FreeCAD no está en esta máquina: el STEP se reabrió con OpenCascade; los STEP los deja cada corrida en `poc/salida/` por si alguien quiere abrirlos en otro visor.

| Qué | Valor | Umbral | Cumple |
|---|---:|---|---|
| P2: formato leído | .t101d (documento de draw101; «.t101x» es el proyecto de Taller 101) |  |  |
| P2 tablero: leer .t101d + cara + extruir | 22.4 ms |  |  |
| P2 tablero: exportar STEP | 7.9 ms |  |  |
| P2 tablero: STEP | 19078 bytes |  |  |
| P2 tablero: reabrir el STEP y medir | 8.0 ms |  |  |
| P2 tablero-redondeado: leer .t101d + cara + extruir | 11.2 ms |  |  |
| P2 tablero-redondeado: exportar STEP | 5.9 ms |  |  |
| P2 tablero-redondeado: STEP | 33580 bytes |  |  |
| P2 tablero-redondeado: reabrir el STEP y medir | 11.9 ms |  |  |
| P2: el STEP abre con las medidas del boceto | sí (reabierto con OpenCascade; FreeCAD no está en esta máquina) | sí/no | sí |

## P3 · Historial regenerable y referencias estables

**Veredicto: sí, con un límite medido.** El historial JSON regenera desde cero y da las medidas de fórmula. Las referencias por nombre derivado («arriba», «lado[1]», «lado[0]|lado[1]», «redondeo[3]/…», «restar[2]/…») sobreviven a cambiar una cota del boceto de abajo; la huella geométrica (centro + normal + área) que el documento sugería como alternativa NO sobrevive (0 de 2 caras). Tiempo desde cero: 30 operaciones en menos de 1 s (cumple); con 60 se dispara a ~10 s porque cada booleana sobre un sólido con más caras cuesta más (la operación más lenta, un empuje, pasa de 17 ms a 840 ms): la app necesita la caché por operación que el marco ya prevé. Hallazgo del kernel: tras empujar la cara de arriba, UnifySameDomain no funde las tiras cilíndricas nuevas con los redondeos y quedan 4 caras extra con la misma superficie; se nombran como continuación («…~2») y no rompen nada.

| Qué | Valor | Umbral | Cumple |
|---|---:|---|---|
| P3 caras extra tras empujar «arriba» (misma superficie que un redondeo, el kernel no las funde) | 4 |  |  |
| P3 regenerar 5 operaciones | 121.0 ms |  |  |
| P3 nombres por derivación sobreviven a cambiar una cota de abajo | sí | sí/no | sí |
| P3 huella geométrica (centro+normal+área) sobrevive al cambio | no (0 de 2 caras) | sí/no |  |
| P3 regenerar 10 operaciones (6 barrenos, 2 empujes) | 87 ms |  |  |
| P3 la operación más lenta con 10 | 7:empujar_cara 14 ms |  |  |
| P3 regenerar 30 operaciones (19 barrenos, 9 empujes) | 721 ms | < 1 s | sí |
| P3 la operación más lenta con 30 | 28:empujar_cara 93 ms |  |  |
| P3 regenerar 60 operaciones (39 barrenos, 19 empujes) | 9926 ms |  |  |
| P3 la operación más lenta con 60 | 58:empujar_cara 889 ms |  |  |

## P4 · Vista 3D y empujar cara

**Veredicto: sí en lo que se pudo medir; los fps no se pueden medir aquí.** Una geometría por cara en Three.js: el raycast devuelve el nombre de la cara y la resalta; clic + arrastre en la normal manda empujar_cara al motor y la malla se repinta. Con 50 caras y caché por operación: empujar la pared de un cajeado (cambian 9 caras) 78 ms de ida y vuelta (cumple < 100 ms); empujar «arriba» (crecen las 50 paredes: se regenera y retesela todo) 159 ms (no cumple); regenerando las 13 operaciones sin caché, ~580 ms. El motor es ~40–90 ms de eso: la booleana de fusión y la unificación de caras; un empuje como operación local del kernel (BRepFeat) sería el siguiente ahorro. Los fps NO son medibles en esta máquina: el Chromium pinta por software y da 10–11 fps con la escena VACÍA; 504 caras dan lo mismo. Hay que medirlos en una máquina con GPU (el corredor de Windows o la de Mike).

| Qué | Valor | Umbral | Cumple |
|---|---:|---|---|
| P4 caras que el kernel no fundió tras empujar «arriba» (misma superficie que un redondeo) | 8 |  |  |
| P4 ida y vuelta empujar cara, 11 caras (con caché por operación) | 76 ms |  |  |
| P4 arrastre → motor → malla nueva, 11 caras | 65 ms |  |  |
| P4 ida y vuelta empujar la pared de un cajeado, 50 caras, con caché | 88 ms | < 100 ms | sí |
| P4   de eso, motor (regenerar + teselar) | 42.9 + 29.1 ms |  |  |
| P4   caras reteseladas de 50 al empujar una pared | 9 |  |  |
| P4 ida y vuelta empujar «arriba» (cambian las 50 caras), 50 caras, con caché por operación | 170 ms | < 100 ms | NO |
| P4   de eso, motor (regenerar + teselar) | 89.3 + 63.4 ms |  |  |
| P4   caras reteseladas de 50 al empujar «arriba» (crecen todas las paredes) | 49 |  |  |
| P4 ida y vuelta empujar cara, 50 caras, regenerando las 13 operaciones | 543 ms |  |  |
| P4 fps con la escena VACÍA (el suelo del Chromium por software, sin GPU) | 10 fps |  |  |
| P4 fps orbitando 50 caras (Chromium por software, sin GPU) | 21 fps |  |  |
| P4 fps orbitando 504 caras (Chromium por software, sin GPU) | 10 fps | > 30 fps: NO MEDIBLE aquí, el suelo sin GPU es menor que el umbral |  |

## P5 · Salidas 2D a draw101

**Veredicto: sí.** Planta, alzado, lateral y un corte por el barreno con líneas ocultas (HLR de OpenCascade) se escriben como líneas, arcos y círculos exactos de draw101 (ninguna arista quedó como polilínea), las ocultas en la capa T101-OCULTO del catálogo (discontinua). El .t101d se reabre con el motor de draw101 y las cotas puestas con su motor de cotas dan las medidas del sólido: 900 de ancho, ⌀160 el barreno, 28 el espesor con la cara empujada. Queda en `poc/muestras/vistas-tablero.t101d` para abrirlo en draw101. Lo que no se probó: acotar con la interfaz de draw101 (no hay pantalla aquí); el motor es el mismo que usa la pantalla.

| Qué | Valor | Umbral | Cumple |
|---|---:|---|---|
| P5 generar 3 vistas + corte con HLR y escribirlas como entidades | 120 ms |  |  |
| P5 planta: aristas visibles / ocultas | 9 / 13 |  |  |
| P5 alzado: aristas visibles / ocultas | 10 / 23 |  |  |
| P5 lateral: aristas visibles / ocultas | 13 / 26 |  |  |
| P5 corte: aristas visibles / ocultas | 8 / 0 |  |  |
| P5 aristas que no se pudieron escribir como línea, arco o círculo (quedaron como polilínea) | 0 |  |  |
| P5 las cotas puestas en draw101 dan las medidas del sólido | sí (900, ⌀160, 28) | sí/no | sí |

## P6 · Presentación (glTF)

**Veredicto: sí.** El motor exporta glTF binario y la misma página lo carga con GLTFLoader de three.js, como lo haría peek101 en el navegador del cliente. Tamaños en la tabla.

| Qué | Valor | Umbral | Cumple |
|---|---:|---|---|
| P6 glTF del tablero (11 caras): tamaño | 21.3 KB |  |  |
| P6 exportar glTF | 6 ms |  |  |
| P6 glTF del mueble de 504 caras: tamaño | 241.7 KB |  |  |
| P6 cargar el glTF en three.js (GLTFLoader) | 33 ms |  |  |
| P6 el glTF abre en un visor web | sí | sí/no | sí |

