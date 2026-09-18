/* Los planos de trabajo  ·  XY, XZ, YZ  ·  0.11.0
 *
 * Cada línea del dibujo sabe en qué plano vive, y cada ventana tiene el suyo:
 * la Superior dibuja sobre XY (el suelo), la Frontal sobre XZ, la Lateral
 * sobre YZ. Un contorno guarda dos coordenadas —(u, v) en su plano— y esto
 * las lleva al mundo de tres.
 *
 * Los tres mapeos son **rotaciones** de verdad, no espejos: extruir hacia
 * afuera del plano da una pieza que se puede fabricar, no una volteada.
 *
 *   XY: (u, v, w) → (u, v, w)       hacia arriba
 *   XZ: (u, v, w) → (u, −w, v)      hacia quien mira la Frontal
 *   YZ: (u, v, w) → (w, u, v)       hacia +X
 *
 * `w` es la altura sobre el plano: cero para el dibujo, el espesor para una
 * pieza. Lo usan el visor, el hule, la selección y el fantasma de extruir.
 * El motor hace exactamente la misma cuenta en Python (core/solido/rutas.py):
 * si un día cambia una, tiene que cambiar la otra.
 */

const Planos = (() => {
  function aMundo(plano, u, v, w) {
    w = w || 0;
    if (plano === "XZ") return [u, -w, v];
    if (plano === "YZ") return [w, u, v];
    return [u, v, w];
  }

  /** Hacia dónde se levanta una pieza dibujada en ese plano. */
  function normal(plano) {
    if (plano === "XZ") return [0, -1, 0];
    if (plano === "YZ") return [1, 0, 0];
    return [0, 0, 1];
  }

  return { aMundo, normal };
})();

if (typeof window !== "undefined") window.Planos = Planos;
if (typeof module !== "undefined") module.exports = Planos;
