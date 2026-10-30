# Rumbo del modelado: de la base 2D a sólidos al nivel de Rhino

*Decidido por Mike el 30-oct-2026: «hay que repasar desde la base (dibujo 2D) y
seguir hasta que los sólidos se modelen correctamente, pudiendo competir con
las capacidades de Rhino».*

## La regla de fondo, sacada de cómo trabaja Rhino

No se copia nada de Rhino: su código es cerrado y su licencia no deja
descompilarlo. Lo que se toma son **estrategias públicas**, las que trae
cualquier libro de modelado geométrico y las que Rhino explica en su propia
documentación:

1. **Una curva libre es su NURBS.** Grado, nudos, pesos y puntos de control.
   Lo que se pinta, a lo que se engancha el osnap y lo que va al archivo salen
   de esos cuatro datos, nunca de una copia aproximada.
2. **Geometría exacta, malla sólo para ver.** Rhino distingue la geometría
   (exacta) de la malla de pantalla (aproximada). Aquí: `core/nurbs.py` y el
   kernel B-rep son la verdad; `teselar()` y la malla del 3D son para pintar.
3. **Una sola tolerancia absoluta por documento.** Unir, recortar, intersecar y
   las booleanas usan la misma. Hoy hay tolerancias sueltas por módulo.
4. **Operaciones sobre curvas, no sobre polilíneas.** Recortar, extender,
   desfasar, intersecar y las regiones (booleanas 2D) se hacen sobre la curva
   exacta.
5. **El sólido sale del kernel B-rep**, que ya es OpenCASCADE (vía build123d):
   el mismo tipo de núcleo que el de Rhino. Lo que falta es darle curvas
   exactas en vez de polilíneas, y las operaciones que Rhino expone.

## Fases

| Fase | Qué | Estado |
|---|---|---|
| **A1** | NURBS exacta en la spline: nudos y pesos, pintado y osnap sobre la curva, DXF con la curva completa; elipse exacta en el osnap | hecha (t043) |
| **A2** | Intersección exacta curva-curva (spline, elipse, arco, recta) en el osnap y en recortar/extender; cercano y perpendicular exactos | hecha (t044) |
| **A3** | Tolerancia absoluta única del documento (0.05 mm por omisión, comando TOLERANCIA), usada por unir, recortar, extender y al coser el boceto de un sólido | hecha (t045) |
| **A4** | Importar SPLINE de un DXF como nativa cuando trae nudos (exacta, sin moverla un pelo); la de sólo ajuste se queda conservada | hecha (t046) |
| B1 | Recortar y extender sobre splines y elipses (partir la NURBS por inserción de nudos) | pendiente |
| B2 | Regiones: booleanas 2D de contornos cerrados (unión, resta, intersección) y rayado picando dentro, con islas | pendiente |
| B3 | Desfase exacto de curvas libres (aproximado a la tolerancia, como Rhino) | pendiente |
| C1 | Boceto 3D con varios contornos e islas (caras con huecos) | pendiente |
| C2 | Splines y elipses entran al kernel como curvas B-spline, no como polilíneas | pendiente |
| C3 | Mover puntos de curvas en un sólido; empalme y chaflán robustos | pendiente |
| D | Superficies libres: loft, barrido por dos rieles, red de curvas, edición por puntos de control, análisis de curvatura | pendiente |

Cada fase va en su propia rama y su propio PR, con su prueba (`t0NN`) y la
suite completa en verde antes de fusionar. Publicar una versión es aparte y lo
decide Mike.

## Lo que se aprendió en A1

- **La spline de antes eran tres curvas.** Pantalla (Catmull-Rom), osnap
  (poligonal de los puntos) y DXF (lo que cada programa interpolara) se
  separaban hasta 63 unidades en una curva de un metro.
- **Para los puntos de ajuste se usa el método de AutoCAD**, no el de libro:
  con los mismos puntos se separan 55 unidades, y el DXF de 0.21.9 llevaba sólo
  los puntos, así que en AutoCAD esas splines siempre se vieron así.
- **El punto más cercano es difícil de verdad.** Tres trampas, las tres en
  `t043`: muestras uniformes en el parámetro dejan huecos donde la curva
  acelera; la curva que casi se toca a sí misma engaña al segmento más
  cercano; y junto a una cúspide Newton se atasca si la segunda derivada sale
  de restar diferencias. Se resolvió con derivadas exactas (hodógrafa),
  candidatos dentro de la flecha y Gauss-Newton con búsqueda lineal.
- **Nudos negativos**: la interpolación cerrada los produce y hay lectores de
  DXF que no los esperan. Se corren a cero.

## Lo que se aprendió en A2

- **Mike decidió seguir con A2 antes de publicar** (30-oct-2026): A1 y A2 salen
  juntas en la próxima versión.
- **Los trozos dicen dónde buscar, la curva dice qué hay.** Cada trozo viaja
  con la definición exacta de su curva (`def`) y su tramo de parámetro; el
  navegador refina sobre ella (ui/curvas.js). Por eso los trozos pasaron de
  una flecha de 0.01 a 0.1: menos peso para el navegador y respuesta exacta.
- **Con una recta o un arco, la raíz no se adivina**: los extremos de cada
  trozo están sobre la curva, así que el cambio de signo la encierra y la
  bisección con secante no puede fallar. El cruce de las cuerdas puede caer
  en un trozo y el de la curva en el vecino: se busca también ahí.
- **Antes vs después** (t044 con el refinado apagado): cruces hasta 0.08
  fuera de la curva, pies de perpendicular a 13 unidades; RECORTAR dejaba la
  punta 0.009 fuera de la spline. Ahora, menos de una millonésima.
- Una curva vista desde otro plano (Frontal, Lateral) pierde su `def` al
  llevarse: ahí se usa la cuerda, que ya está dentro de la flecha.

## Lo que se aprendió en A3

- **Mike pidió seguir con A3 antes de publicar** (30-oct-2026): A1, A2 y A3
  salen juntas en la próxima versión.
- **El caso que lo justifica**: un rectángulo de cuatro líneas con huecos de
  0.02 mm (lo normal en un DXF de AutoCAD o de Revit) se unía con UNIR pero
  **no se podía extruir**: OpenCASCADE cose a unas micras. Ahora el boceto
  suelda las puntas sueltas a la tolerancia del documento antes de coser.
- **0.05 mm por omisión**, la que UNIR ya usaba (t015): no cambia nada de lo
  que el taller ya conoce. Va en mm aunque el dibujo esté en cm o en m.
- **Coser no es tapar errores**: con huecos de medio milímetro el contorno
  sigue sin cerrar. Y la tolerancia manda de verdad: con 0.01 mm el mismo
  boceto de 0.02 ya no cierra (también fuera de caché: la tolerancia entra a
  la huella del cuerpo).
- RECORTAR y EXTENDER no cortan en un cruce pegado a la punta (a menos de la
  tolerancia): antes dejaban un pedacito de centésimas suelto.
- En la línea de comando el espacio es Enter: un comando que necesita un
  valor lo **pide**, no lo recibe pegado al nombre.
- Las guardas numéricas (`1e-9`, `1e-12`) no son tolerancia de modelado y se
  quedaron como estaban.

## Lo que se aprendió en A4

- **Mike dejó REA y Rhino para después** (30-oct-2026): REA no se instaló ni
  se usó; las técnicas de estas fases son de libro (Piegl y Tiller) y de la
  documentación pública de Rhino. Para estudiar Rhino lo útil son archivos
  que él exporte (.3dm, DXF, STEP); Remote Control sólo conecta Mac o Linux.
- **Promover las splines casi tumba el rendimiento.** Un plano de 3 000
  splines: abrir 9.6 s, pintar 9.2 s, primitivas 20 s y 107 MB (en `main`,
  conservadas: 1.0, 0.2, 1.3 s y 38 MB). Lo que lo arregló:
  - teselar por **segmentos de Bézier** (descomposición A5.6 de una pasada) y
    muestrear parejo con numpy, con la **cota exacta** de la flecha
    p(p-1)/8·max|Δ²P|/m²: los vértices siguen sobre la curva y la flecha se
    cumple con garantía;
  - la caja por los **puntos de control** (envolvente convexa), sin teselar;
  - la `def` **una vez por curva** (en su primer trozo), no en cada trozo;
  - pintar a 0.1 (la finura de siempre para splines ajenas) y trozos del
    osnap a 0.25 (el refinado exacto los hace sólo una pista).
  Quedó: abrir 0.6 s, pintar 0.9 s, primitivas 2.0 s, 54 MB. Abrir más pintar
  empata con `main`; el total es ~35 % más en un plano hecho sólo de splines,
  a cambio de que todas sean exactas y editables.
- **Splines dentro de bloques**: al llevar las primitivas a la inserción se
  perdían las marcas (`curva`, `aprox`) y el osnap daba extremos falsos y
  nodos en los puntos de control. Ahora las marcas viajan y los grips de
  definición no.
- **Una NURBS con un nudo interior repetido más que el grado no es una curva**
  que un CAD dibuje: se rechaza, y si viene de un DXF se queda conservada.
- Una spline importada se jala por sus **puntos de control** (como en Rhino);
  al mover uno, los puntos de ajuste que traía se vacían porque ya no están
  sobre la curva.
