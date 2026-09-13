# shape101 · prueba de concepto (tarea para Jr. PROGRAMMER)

Objetivo: responder con números si shape101 va o no. Una o dos semanas. No es
la app; es la medición. Todo vive en `poc/`. Cada paso deja un número o un
sí/no en `poc/RESULTADOS.md`.

## Lo que ya se midió (chat draw101, 12-sep-2026, Linux, Python 3.12)

Instalación: `pip install build123d` → build123d 0.11.1 + cadquery-ocp
(OpenCascade). **La carpeta `OCP` pesa 160 MB** en disco.

Caso de taller (`poc/p0_kernel.py`): tablero 900×600×18 con barreno ⌀160, cajeado
cilíndrico (booleana) y redondeos de 20 en las aristas verticales:

- modelado (extruir + booleana + redondeo): **32 ms**
- STEP (38 KB) + STL (75 KB): **31 ms**
- teselado para Three.js: 1 556 vértices, 1 540 triángulos: **17 ms**
- vista 2D en planta con líneas ocultas (HLR): 10 aristas visibles, 10 ocultas: **1 ms**

Conclusión parcial: el kernel no es el problema ni en velocidad ni en salidas.
Falta medir el peso real en Windows dentro del instalador y, sobre todo, la
interfaz.

## P1 · Windows y peso empotrado

1. En Windows: `pip install build123d` en un Python 3.11 limpio. Anotar tamaño de
   `site-packages` antes/después y versión de cadquery-ocp.
2. Copiar ese Python al patrón `runtime/python` de draw101 y armar un instalador
   NSIS vacío (Electron con una ventana en blanco) que lo incluya. **Anotar MB del
   instalador.** Umbral: si pasa de 400 MB, buscar poda (OCP trae módulos que no
   se usan; medir cuánto se puede quitar sin romper build123d).
3. Tiempo de arranque del motor (importar build123d) en frío y en caliente.
   Umbral: < 3 s en caliente.

## P2 · Boceto de draw101 → sólido

1. Leer un `.t101x` de draw101 (rectángulo con un círculo dentro, dibujado en
   draw101 con cotas) con el código de `core/t101x.py` de draw101.
2. Convertir sus entidades a un `Sketch` de build123d (líneas, arcos, círculos,
   polilíneas cerradas con bulges). Extruir 18 mm. Exportar STEP.
3. Sí/no: el STEP abre en FreeCAD (o cualquier visor) con las medidas del boceto.

## P3 · Historial regenerable

1. Documento JSON: lista de operaciones `[{op:"boceto", plano, t101x},
   {op:"extruir", mm}, {op:"restar", …}, {op:"redondear", aristas, r},
   {op:"empujar_cara", cara, mm}]`.
2. Regenerar desde cero cambiando una cota del boceto de abajo. Medir tiempo con
   10, 30 y 60 operaciones. Umbral: < 1 s con 30.
3. Referencias estables: cómo se identifica una cara o arista para que sobreviva
   a un cambio de abajo (el índice topológico no sirve; probar centro + normal +
   área con tolerancia, o nombres persistentes). **Es el punto más difícil del
   proyecto; medirlo aquí.**

## P4 · Vista 3D y empujar cara

1. Página Three.js (copiar patrón de nest101): recibe del motor la malla
   teselada por cara (una geometría por cara, para poder seleccionarla) y las
   aristas.
2. Picking: raycast a la cara bajo el ratón, resaltado; clic en cara + arrastre
   en la normal = manda `empujar_cara` al motor y repinta. Medir ida y vuelta:
   arrastre → motor → malla nueva en pantalla. Umbral: < 100 ms con 50 caras.
3. Sí/no: con 500 caras (un mueble completo) sigue fluido (> 30 fps al orbitar).

## P5 · Salidas 2D a draw101

1. Del sólido: planta, alzado, lateral y un corte por un plano, con HLR (visibles
   y ocultas). Escribir cada vista como entidades de draw101 (`.t101x`), con la
   capa «ocultas» en línea discontinua.
2. Abrir el `.t101x` en draw101 y acotar. Sí/no: las cotas dan las medidas del
   sólido.

## P6 · Presentación

1. Exportar glTF del sólido teselado con materiales por cara. Abrirlo en un visor
   web (three.js) como lo haría peek101. Sí/no y MB del glTF.

## Reglas

- Todo con pruebas automáticas como en draw101 (`verificar.py`); cada paso mide,
  no opina.
- No se toca draw101: sólo se lee su formato `.t101x`.
- Resultado final: `poc/RESULTADOS.md` con la tabla de números y un veredicto por
  paso. Mike decide con eso.
