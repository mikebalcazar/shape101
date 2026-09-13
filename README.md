# shape101

Modelador 3D de sólidos de **Taller 101** (suite101). Sólidos libres —booleanas,
curvas, cualquier forma— trabajados de dos maneras a la vez: bocetos 2D
paramétricos con historial editable (tipo Fusion/Onshape) y empujar/jalar caras
(tipo SketchUp). El historial manda; empujar una cara es una operación más.

**Estado: prueba de concepto.** Nada de lo que hay aquí es la app todavía. La
decisión completa está en Drive (`suite101/shape101/shape101-decision-2026-09-12`);
lo que se mide y cómo, en `poc/PLAN.md`; los números, en `poc/RESULTADOS.md`.
Mike decide con esa tabla si shape101 va o no.

## Arquitectura propuesta

| Pieza | Con qué | Por qué |
|---|---|---|
| Motor | Python + OpenCascade vía **build123d** | Geometría exacta (B-rep), booleanas, redondeos, STEP; vistas 2D con ocultas y secciones salen del kernel. Mismo patrón que el motor de draw101. |
| Documento | Árbol de operaciones regenerable, con caché por operación | Historial editable; empujar cara se registra como operación. |
| Bocetos | **draw101** (`.t101x` sobre un plano o una cara) | Snap, cotas, comandos y pruebas ya existen. |
| Vista 3D | Three.js (como nest101) | Malla teselada + aristas por cara; selección y arrastre. |
| Cascarón | El de draw101: Electron, línea de comandos, instalador, actualizador, publicación | Cero trabajo nuevo. |

**Salidas:** planos 2D al taller (vistas, cortes, cotas) como documentos de
draw101; STEP/STL para CNC e impresión 3D; presentación al cliente (vistas 3D,
medidas, capturas; glTF para peek101). Sin renders fotorrealistas.

## Reglas de la casa

- Todo con pruebas automáticas (`verificar.py`, como draw101). Cada paso mide, no opina.
- No se toca draw101: sólo se lee su formato `.t101x`.
- Quien publica shape101 es su chat, con el mismo flujo que draw101
  (`armar-y-publicar.yml` en Windows → `descargas`).
- CONTEXTO.md de la suite manda; el muro de `suite101-api` es donde se avisa.
