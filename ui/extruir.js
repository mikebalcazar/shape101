/* Extruir interactivo  ·  0.10.0
 *
 * Mike: «cuando das el comando extruir, debería dibujar como fantasma el
 * preview de hasta dónde arrastras el mouse, o poder ingresar el valor».
 *
 * Das EXTRUIR con un contorno seleccionado y desde ese momento el fantasma
 * sigue al ratón: el contorno levantado a la altura que llevas, los cantos
 * punteados y la cota. Clic confirma esa altura. Enter pide el número exacto
 * con la cajita de siempre. Escape cancela.
 *
 * La altura se mide **sobre la dirección en que se levanta la pieza** (hoy,
 * hacia arriba), proyectada en la pantalla de la ventana activa: en planta esa
 * dirección no se ve —apunta al ojo— y entonces se usa la vertical de la
 * pantalla, que es lo que la mano espera.
 *
 * Nada de esto pide la pieza al motor hasta confirmar: el fantasma es una
 * promesa barata y el motor la cumple una sola vez.
 */

const Extrusion = (() => {
  let activa = null;      // { ids, contornos, mm, px, py, px0, py0 }

  function lienzo() { return document.getElementById("lienzo"); }

  /** Los contornos de las entidades seleccionadas, sacados de los trazos que
   *  ya tiene la pantalla: no hace falta pedirle nada al motor. */
  function contornosDe(ids) {
    const quiero = new Set(ids);
    const out = [];
    for (const t of (typeof estado !== "undefined" && estado.trazos) || []) {
      if (!quiero.has(t.id) || !t.puntos || t.puntos.length < 2) continue;
      out.push({ plano: t.plano || "XY", pts: t.puntos.map((p) => [p[0], p[1]]) });
    }
    return out;
  }

  function empezar(ids) {
    const contornos = contornosDe(ids);
    if (!contornos.length) {
      Comandos.eco("No encuentro el contorno seleccionado en la pantalla.", "malo");
      return false;
    }
    activa = { ids, contornos, mm: 0, px0: null, py0: null };
    Comandos.eco("Arrastra para levantar la pieza · clic confirma · Enter teclea el valor · Escape cancela");
    const el = lienzo();
    el.style.cursor = "ns-resize";
    window.addEventListener("mousemove", alMover, true);
    window.addEventListener("mousedown", alBajar, true);
    window.addEventListener("keydown", alTecla, true);
    return true;
  }

  function terminar() {
    const el = lienzo();
    if (el) el.style.cursor = "";
    window.removeEventListener("mousemove", alMover, true);
    window.removeEventListener("mousedown", alBajar, true);
    window.removeEventListener("keydown", alTecla, true);
    activa = null;
    if (window.pintar) window.pintar();
  }

  /** Cuántos milímetros son el arrastre, medidos sobre la dirección en que se
   *  levanta la pieza. En planta esa dirección apunta al ojo y no se proyecta:
   *  se usa la vertical de la pantalla. */
  function mmDe(px, py) {
    const a = activa;
    if (a.px0 === null) { a.px0 = px; a.py0 = py; return 0; }
    const n = Planos.normal(a.contornos[0].plano);
    const q0 = window.aPX(0, 0, 0), q1 = window.aPX(n[0], n[1], n[2]);
    let dir = [q1[0] - q0[0], q1[1] - q0[1]];
    let largo = Math.hypot(dir[0], dir[1]);
    if (largo < 1e-6) { dir = [0, -1]; largo = 1; }
    const proy = ((px - a.px0) * dir[0] + (py - a.py0) * dir[1]) / largo;
    // Con la dirección proyectada, `largo` píxeles son un milímetro.
    const porMM = Math.hypot(q1[0] - q0[0], q1[1] - q0[1]) || estado.vista.escala;
    return Math.round((proy / porMM) * 100) / 100;
  }

  function alMover(e) {
    if (!activa) return;
    const r = lienzo().getBoundingClientRect();
    activa.mm = mmDe(e.clientX - r.left, e.clientY - r.top);
    activa.px = e.clientX - r.left;
    activa.py = e.clientY - r.top;
    if (window.pintar) window.pintar();
  }

  function alBajar(e) {
    if (!activa || e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const mm = activa.mm;
    if (Math.abs(mm) < 0.5) { Comandos.eco("Arrastra un poco antes de confirmar, o Enter para teclear el valor."); return; }
    confirmar(mm);
  }

  async function alTecla(e) {
    if (!activa) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); terminar(); Comandos.eco("extruir cancelado"); return; }
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      const ids = activa.ids;
      const sugerido = Math.abs(activa.mm) >= 0.5 ? activa.mm : 18;
      terminar();
      if (typeof Entrada === "undefined" || !Entrada.pedirNumero) return;
      const mm = await Entrada.pedirNumero({ mensaje: "Espesor (en las unidades del dibujo)", valor: sugerido, clave: "extruir-espesor" });
      if (isFinite(mm) && mm !== 0) await levantar(ids, mm);
    }
  }

  async function confirmar(mm) {
    const ids = activa.ids;
    terminar();
    await levantar(ids, mm);
  }

  async function levantar(ids, mm) {
    try {
      const m = await fetch("/api/cuerpo/extruir", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, mm }),
      }).then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || r.status); return j; });
      await Cuerpos.refrescar();
      Comandos.eco(`pieza de ${m.caja[0]} × ${m.caja[1]} × ${m.caja[2]} · ${(m.volumen_mm3 / 1000).toFixed(1)} cm³`
        + (m.ms !== undefined ? ` · el motor tardó ${m.ms} ms` : ""));
    } catch (e) { Comandos.eco("No se pudo extruir: " + e.message, "malo"); }
  }

  /** El fantasma. Lo llama la capa de encima de cada ventana, con su cámara. */
  function pintar(c) {
    const a = activa;
    if (!a || !window.aPX || Math.abs(a.mm) < 0.01) return;
    c.save();
    c.strokeStyle = "rgba(255,211,90,0.95)";
    c.fillStyle = "rgba(255,211,90,0.18)";
    c.lineWidth = 1.5;
    for (const { plano, pts } of a.contornos) {
      c.setLineDash([6, 4]);
      c.beginPath();
      pts.forEach((p, i) => { const m = Planos.aMundo(plano, p[0], p[1], a.mm); const q = window.aPX(m[0], m[1], m[2]); i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]); });
      c.closePath();
      c.fill();
      c.stroke();
      c.setLineDash([2, 3]);
      for (const p of pts) {
        const m0 = Planos.aMundo(plano, p[0], p[1], 0), m1 = Planos.aMundo(plano, p[0], p[1], a.mm);
        const q0 = window.aPX(m0[0], m0[1], m0[2]), q1 = window.aPX(m1[0], m1[1], m1[2]);
        c.beginPath(); c.moveTo(q0[0], q0[1]); c.lineTo(q1[0], q1[1]); c.stroke();
      }
    }
    c.setLineDash([]);
    if (a.px !== undefined) {
      const texto = `${a.mm > 0 ? "+" : ""}${a.mm.toFixed(2)}`;
      c.font = "bold 13px system-ui, sans-serif";
      const an = c.measureText(texto).width + 12;
      c.fillStyle = "rgba(0,0,0,0.72)";
      c.fillRect(a.px + 14, a.py - 26, an, 20);
      c.fillStyle = "#ffd35a";
      c.fillText(texto, a.px + 20, a.py - 12);
    }
    c.restore();
  }

  return { empezar, terminar, pintar, activa: () => !!activa };
})();

window.Extrusion = Extrusion;
