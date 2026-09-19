/* Los tiradores de una pieza  ·  vértices y medios de arista  ·  0.13.0
 *
 * Mike, el 18-sep: *«ve pensando en ya agregar los modificadores de los
 * endpoints o vértices. Y las aristas deben tener también el handle en el
 * midpoint para poder arrastrarlo»*.
 *
 * Una pieza de shape101 no es una malla: es **un contorno levantado**, y lo
 * que se guarda es cómo se hizo. Por eso aquí no se deforman triángulos. Un
 * tirador dice qué punto del contorno mueve, el motor rehace la pieza desde el
 * contorno nuevo, y todo lo que se hizo después —un barreno, una cara jalada—
 * se vuelve a aplicar solo. Es la misma promesa de `mover-punto`, ahora con
 * algo de dónde agarrarla.
 *
 * **Dónde se pintan.** Un contorno levantado tiene el mismo punto abajo y
 * arriba, y una arista vertical entre los dos. Así que cada punto del contorno
 * da tres tiradores —abajo, a media altura, arriba— y los tres jalan el mismo
 * punto: mover una esquina es mover *la* esquina, la mires desde donde la
 * mires. Cada tramo recto da dos, uno abajo y otro arriba, y ésos corren el
 * tramo entero sin doblarlo.
 *
 * **Cómo se convierte el arrastre.** El tirador se mueve sobre el plano de la
 * pieza, no sobre la pantalla. Al empezar el gesto se mide en píxeles cuánto
 * vale un paso en u y un paso en v; con eso, el arrastre en pantalla se
 * resuelve como un sistema de dos por dos. En las tres ventanas ortogonales
 * eso es exacto. En la Perspectiva es una aproximación —la escala cambia con
 * la profundidad—, y por eso los números finos se hacen en una ortogonal.
 *
 * Si el plano de la pieza se ve **de canto**, el sistema no tiene solución y
 * no hay forma honesta de saber a dónde quiere ir el ratón. Entonces se avisa
 * y no se mueve nada, igual que al jalar una cara vista de canto.
 */

const Tiradores = (() => {
  const cache = new Map();          // id → {plano, altura, vertices, segmentos}
  let arrastre = null;
  let pidiendo = new Set();

  const RADIO = 7;                  // radio de agarre, en píxeles

  function lienzo() { return document.getElementById("lienzo"); }

  function coords(e) {
    const r = lienzo().getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  // --- traer y olvidar -----------------------------------------------------

  async function cargar(id) {
    if (!id || cache.has(id) || pidiendo.has(id)) return;
    pidiendo.add(id);
    try {
      const r = await fetch(`/api/cuerpo/${id}/tiradores`);
      const j = await r.json();
      if (r.ok) cache.set(id, j);
    } catch (e) { /* sin tiradores se sigue pudiendo jalar caras */ }
    finally { pidiendo.delete(id); }
    if (window.invalidarPlano) window.invalidarPlano();
    if (window.pintar) window.pintar();
  }

  function olvidar(id) {
    if (id === undefined) cache.clear(); else cache.delete(id);
  }

  /** De qué pieza se enseñan los tiradores: la que está señalada. Se señala al
   *  picar una de sus caras, que es como se elige una pieza. */
  function idActivo() {
    if (typeof Cuerpos === "undefined") return null;
    const s = Cuerpos.senalada;
    return s ? s.id : null;
  }

  // --- de coordenadas del boceto al mundo ----------------------------------

  /** Los tiradores de la pieza, ya en el mundo, cada uno con qué mueve.
   *  `t` es la altura sobre el plano: 0, la mitad, o el espesor. */
  function delMundo(id) {
    const d = cache.get(id);
    if (!d || typeof Planos === "undefined") return [];
    const h = d.altura || 0;
    const alturas = Math.abs(h) > 1e-9 ? [0, h / 2, h] : [0];
    const salida = [];
    for (const v of d.vertices || []) {
      for (const t of alturas) {
        salida.push({
          tipo: "vertice", id, plano: d.plano, uv: v.uv,
          entidad: v.entidad, punto: v.punto,
          p: Planos.aMundo(d.plano, v.uv[0], v.uv[1], t),
        });
      }
    }
    // El medio de un tramo no lleva el de media altura: ahí no hay arista.
    const deSegmento = Math.abs(h) > 1e-9 ? [0, h] : [0];
    for (const s of d.segmentos || []) {
      for (const t of deSegmento) {
        salida.push({
          tipo: "segmento", id, plano: d.plano, uv: s.uv,
          entidad: s.entidad, a: s.a, b: s.b,
          p: Planos.aMundo(d.plano, s.uv[0], s.uv[1], t),
        });
      }
    }
    return salida;
  }

  // --- pintar --------------------------------------------------------------

  function pintar(c) {
    const id = idActivo();
    if (!id || !window.aPX) return;
    if (!cache.has(id)) { cargar(id); return; }
    const arr = delMundo(id);
    if (!arr.length) return;
    c.save();
    for (const t of arr) {
      const q = window.aPX(t.p[0], t.p[1], t.p[2]);
      const agarrado = arrastre && arrastre.clave === claveDe(t);
      if (t.tipo === "vertice") {
        c.fillStyle = agarrado ? "#ffd35a" : "#4aa3ff";
        c.strokeStyle = "rgba(255,255,255,0.9)";
        c.lineWidth = 1;
        c.fillRect(q[0] - 3.5, q[1] - 3.5, 7, 7);
        c.strokeRect(q[0] - 3.5, q[1] - 3.5, 7, 7);
      } else {
        c.fillStyle = "rgba(255,255,255,0.9)";
        c.strokeStyle = agarrado ? "#ffd35a" : "#4aa3ff";
        c.lineWidth = 1.5;
        c.beginPath();
        c.arc(q[0], q[1], 3.2, 0, Math.PI * 2);
        c.fill();
        c.stroke();
      }
    }
    if (arrastre) pintarFantasma(c);
    c.restore();
  }

  /** Mientras se arrastra: a dónde va el tirador y cuánto lleva. Igual que el
   *  fantasma de jalar una cara, no se le pide la pieza al motor en cada
   *  cuadro; rehacer un sólido cuesta decenas de milisegundos y el ratón manda
   *  eventos mucho más seguido. */
  function pintarFantasma(c) {
    const a = arrastre;
    if (!a || !window.aPX) return;
    const destino = Planos.aMundo(a.plano, a.uv[0] + a.du, a.uv[1] + a.dv, a.t);
    const q0 = window.aPX(a.p[0], a.p[1], a.p[2]);
    const q1 = window.aPX(destino[0], destino[1], destino[2]);
    c.save();
    c.strokeStyle = "rgba(255,211,90,0.95)";
    c.lineWidth = 1.5;
    c.setLineDash([5, 4]);
    c.beginPath();
    c.moveTo(q0[0], q0[1]);
    c.lineTo(q1[0], q1[1]);
    c.stroke();
    c.setLineDash([]);
    c.fillStyle = "#ffd35a";
    c.beginPath();
    c.arc(q1[0], q1[1], 4.5, 0, Math.PI * 2);
    c.fill();
    const texto = `${a.du >= 0 ? "+" : ""}${a.du.toFixed(2)} , ${a.dv >= 0 ? "+" : ""}${a.dv.toFixed(2)}`;
    c.font = "bold 13px system-ui, sans-serif";
    const an = c.measureText(texto).width + 12;
    c.fillStyle = "rgba(0,0,0,0.72)";
    c.fillRect(q1[0] + 14, q1[1] - 26, an, 20);
    c.fillStyle = "#ffd35a";
    c.fillText(texto, q1[0] + 20, q1[1] - 12);
    c.restore();
  }

  // --- el gesto ------------------------------------------------------------

  /** El tirador bajo el cursor, o null. De adelante hacia atrás no importa:
   *  el más cercano en pantalla es el que se quiso agarrar. */
  function bajo(px, py) {
    const id = idActivo();
    if (!id || !window.aPX || !cache.has(id)) return null;
    let mejor = null, d2mejor = RADIO * RADIO;
    for (const t of delMundo(id)) {
      const q = window.aPX(t.p[0], t.p[1], t.p[2]);
      const d2 = (q[0] - px) ** 2 + (q[1] - py) ** 2;
      if (d2 <= d2mejor) { d2mejor = d2; mejor = t; }
    }
    return mejor;
  }

  /** Cuántas unidades del dibujo vale un paso de pantalla, sobre el plano de
   *  la pieza. Devuelve la matriz inversa de 2×2, o null si el plano se ve de
   *  canto (determinante cero: el sistema no tiene solución). */
  function inversaDelPlano(plano, p) {
    const o = window.aPX(p[0], p[1], p[2]);
    const eu = Planos.aMundo(plano, 1, 0, 0), e0 = Planos.aMundo(plano, 0, 0, 0);
    const ev = Planos.aMundo(plano, 0, 1, 0);
    const qu = window.aPX(p[0] + eu[0] - e0[0], p[1] + eu[1] - e0[1], p[2] + eu[2] - e0[2]);
    const qv = window.aPX(p[0] + ev[0] - e0[0], p[1] + ev[1] - e0[1], p[2] + ev[2] - e0[2]);
    const a = qu[0] - o[0], b = qv[0] - o[0];
    const cc = qu[1] - o[1], d = qv[1] - o[1];
    const det = a * d - b * cc;
    if (Math.abs(det) < 1e-9) return null;
    return [d / det, -b / det, -cc / det, a / det];
  }

  function abajo(e) {
    if (e.button !== 0 || !window.aPX) return false;
    const [px, py] = coords(e);
    const t = bajo(px, py);
    if (!t) return false;
    const inv = inversaDelPlano(t.plano, t.p);
    if (!inv) {
      if (typeof Comandos !== "undefined") {
        Comandos.eco("Esa pieza se ve de canto: gira un poco la vista para poder jalar sus puntos.", "malo");
      }
      return true;              // el clic fue nuestro: que no empiece a jalar una cara
    }
    arrastre = { ...t, inv, px, py, du: 0, dv: 0,
                 t: alturaDe(t), clave: claveDe(t) };
    if (window.pintar) window.pintar();
    return true;
  }

  /** La altura sobre el plano a la que está pintado este tirador. Sale de
   *  deshacer el mapeo: es la tercera coordenada del plano de la pieza. */
  function alturaDe(t) {
    const base = Planos.aMundo(t.plano, t.uv[0], t.uv[1], 0);
    const uno = Planos.aMundo(t.plano, t.uv[0], t.uv[1], 1);
    for (let k = 0; k < 3; k++) {
      const paso = uno[k] - base[k];
      if (Math.abs(paso) > 1e-9) return (t.p[k] - base[k]) / paso;
    }
    return 0;
  }

  function claveDe(t) {
    return t.tipo === "vertice"
      ? `v:${t.entidad}:${t.punto}:${t.p.join(",")}`
      : `s:${t.entidad}:${t.a}:${t.b}:${t.p.join(",")}`;
  }

  function mover(e) {
    if (!arrastre) return false;
    const [px, py] = coords(e);
    const dpx = px - arrastre.px, dpy = py - arrastre.py;
    const [i0, i1, i2, i3] = arrastre.inv;
    let du = i0 * dpx + i1 * dpy;
    let dv = i2 * dpx + i3 * dpy;
    // El ortho de siempre: si está encendido, el tirador se va por el eje que
    // más se movió. Es lo que ya hace dibujar, y las manos lo esperan.
    if (estado.prefs && estado.prefs.ortho) {
      if (Math.abs(du) >= Math.abs(dv)) dv = 0; else du = 0;
    }
    arrastre.du = Math.round(du * 100) / 100;
    arrastre.dv = Math.round(dv * 100) / 100;
    if (window.pintar) window.pintar();
    return true;
  }

  async function arriba() {
    const a = arrastre;
    arrastre = null;
    if (!a) return false;
    if (window.pintar) window.pintar();
    if (!a.du && !a.dv) return true;          // un clic no es un arrastre
    await aplicar(a);
    return true;
  }

  async function aplicar(a) {
    const url = a.tipo === "vertice"
      ? `/api/cuerpo/${a.id}/mover-punto` : `/api/cuerpo/${a.id}/mover-segmento`;
    const cuerpo = a.tipo === "vertice"
      ? { entidad: a.entidad, punto: a.punto, x: a.uv[0] + a.du, y: a.uv[1] + a.dv }
      : { entidad: a.entidad, a: a.a, b: a.b, dx: a.du, dy: a.dv };
    try {
      const r = await fetch(url, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.status);
      olvidar(a.id);
      await Cuerpos.refrescarUna(a.id);
      cargar(a.id);
      const que = a.tipo === "vertice" ? "punto" : "arista";
      Comandos.eco(`${que} movido ${a.du >= 0 ? "+" : ""}${a.du} , ${a.dv >= 0 ? "+" : ""}${a.dv}`
        + ` · ahora ${j.caja[0]} × ${j.caja[1]} × ${j.caja[2]}`);
    } catch (e) {
      Comandos.eco("No se pudo mover: " + e.message, "malo");
    }
  }

  return { pintar, abajo, mover, arriba, bajo, cargar, olvidar, delMundo,
           arrastrando: () => !!arrastre };
})();

if (typeof window !== "undefined") window.Tiradores = Tiradores;
if (typeof module !== "undefined") module.exports = Tiradores;
