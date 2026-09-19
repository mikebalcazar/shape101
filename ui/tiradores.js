/* Los tiradores de una pieza  ·  sus vértices y sus aristas  ·  0.14.0
 *
 * Mike, el 19-sep, viendo la 0.13.0: *«debería ser un sólido, cada contorno
 * independiente. Todas las aristas son independientes y todos los puntos
 * también»*.
 *
 * Hasta la 0.13.0 los tiradores salían del **boceto**: una pieza era un
 * contorno levantado, así que la esquina de abajo y la de arriba eran el mismo
 * punto y mover una movía las dos. Ahora salen del **sólido**: cada vértice y
 * cada arista de verdad, cada uno suyo.
 *
 * Lo que no se perdió en el camino: la pieza se sigue guardando como cómo se
 * hizo. Cada tirador viaja con su **nombre** —`abajo|lado[0]|lado[3]` es la
 * esquina donde se juntan esas tres caras— y no con un índice, así que cambiar
 * una cota del boceto no le cambia el nombre a la esquina. Es lo mismo que ya
 * hacía posible jalar una cara y que siguiera jalada.
 *
 * **En qué plano se arrastra.** En el de la ventana donde estás: en la
 * Superior mueves en XY, en la Frontal en XZ, en la Lateral en YZ. Sin
 * ambigüedad y sin modos: la ventana ya dice el plano. En la Perspectiva se
 * mueve sobre el suelo (XY), que es lo único que se puede decidir solo.
 *
 * Si ese plano se ve **de canto** desde donde estás mirando, no hay forma
 * honesta de saber a dónde quiere ir el ratón: se avisa y no se mueve nada.
 */

const Tiradores = (() => {
  const cache = new Map();          // id → {plano, vertices, aristas}
  let arrastre = null;
  const pidiendo = new Set();

  const RADIO = 8;                  // radio de agarre, en píxeles

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

  /** Todos los tiradores de la pieza, ya en coordenadas del mundo: el motor
   *  los manda girados al plano de la pieza. */
  function delMundo(id) {
    const d = cache.get(id);
    if (!d) return [];
    const salida = [];
    for (const v of d.vertices || []) {
      salida.push({ tipo: "vertice", id, nombre: v.nombre, p: v.p });
    }
    for (const a of d.aristas || []) {
      // El medio de una arista curva no se jala: moverlo tendría que cambiar
      // la curva, y eso es otra operación. No se enseña lo que no jala.
      if (a.recta === false) continue;
      salida.push({ tipo: "arista", id, nombre: a.nombre, p: a.p, a: a.a, b: a.b });
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
      const agarrado = arrastre && arrastre.nombre === t.nombre && arrastre.tipo === t.tipo;
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

  /** Mientras se arrastra: a dónde va, y cuánto lleva. No se le pide la pieza
   *  al motor en cada cuadro —rehacer un sólido cuesta decenas de milisegundos
   *  y el ratón manda eventos mucho más seguido—; el fantasma es la promesa
   *  barata y al soltar el motor la cumple. */
  function pintarFantasma(c) {
    const a = arrastre;
    if (!a || !window.aPX || !a.d) return;
    const q0 = window.aPX(a.p[0], a.p[1], a.p[2]);
    const q1 = window.aPX(a.p[0] + a.d[0], a.p[1] + a.d[1], a.p[2] + a.d[2]);
    c.save();
    c.strokeStyle = "rgba(255,211,90,0.95)";
    c.lineWidth = 1.5;
    c.setLineDash([5, 4]);
    c.beginPath();
    c.moveTo(q0[0], q0[1]);
    c.lineTo(q1[0], q1[1]);
    c.stroke();
    // Una arista se mueve entera: se dibuja dónde va a quedar, no sólo su medio.
    if (a.tipo === "arista" && a.a && a.b) {
      const qa = window.aPX(a.a[0] + a.d[0], a.a[1] + a.d[1], a.a[2] + a.d[2]);
      const qb = window.aPX(a.b[0] + a.d[0], a.b[1] + a.d[1], a.b[2] + a.d[2]);
      c.beginPath();
      c.moveTo(qa[0], qa[1]);
      c.lineTo(qb[0], qb[1]);
      c.stroke();
    }
    c.setLineDash([]);
    c.fillStyle = "#ffd35a";
    c.beginPath();
    c.arc(q1[0], q1[1], 4.5, 0, Math.PI * 2);
    c.fill();
    const largo = Math.hypot(a.d[0], a.d[1], a.d[2]);
    const texto = `${largo.toFixed(2)}  (${a.d.map((k) => k.toFixed(1)).join(", ")})`;
    c.font = "bold 13px system-ui, sans-serif";
    const an = c.measureText(texto).width + 12;
    c.fillStyle = "rgba(0,0,0,0.72)";
    c.fillRect(q1[0] + 14, q1[1] - 26, an, 20);
    c.fillStyle = "#ffd35a";
    c.fillText(texto, q1[0] + 20, q1[1] - 12);
    c.restore();
  }

  // --- el gesto ------------------------------------------------------------

  /** El tirador bajo el cursor, o null: el más cercano dentro del radio. */
  function bajo(px, py) {
    const id = idActivo();
    if (!id || !window.aPX || !cache.has(id)) return null;
    let mejor = null, d2mejor = RADIO * RADIO;
    for (const t of delMundo(id)) {
      const q = window.aPX(t.p[0], t.p[1], t.p[2]);
      const d2 = (q[0] - px) ** 2 + (q[1] - py) ** 2;
      // A igualdad, gana el vértice: es el que está encima en la pantalla y el
      // que la mano quiso agarrar al picar una esquina.
      if (d2 < d2mejor || (d2 === d2mejor && t.tipo === "vertice")) {
        d2mejor = d2; mejor = t;
      }
    }
    return mejor;
  }

  /** El plano sobre el que se arrastra: el de la ventana donde estás. */
  function planoDeArrastre() {
    if (typeof estado === "undefined" || !estado.vista) return "XY";
    // La Perspectiva no tiene un plano propio que signifique algo: ahí se
    // mueve sobre el suelo, que es lo único decidible sin preguntar.
    return estado.vista.persp ? "XY" : (estado.vista.plano || "XY");
  }

  /** Cuánto vale un paso de pantalla sobre ese plano, como matriz inversa de
   *  2×2. Null si el plano se ve de canto: el sistema no tiene solución y no
   *  hay manera honesta de saber a dónde quiere ir el ratón. */
  function inversaDelPlano(plano, p) {
    const o = window.aPX(p[0], p[1], p[2]);
    const e0 = Planos.aMundo(plano, 0, 0, 0);
    const eu = Planos.aMundo(plano, 1, 0, 0);
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
    if (e.button !== 0 || !window.aPX || typeof Planos === "undefined") return false;
    const [px, py] = coords(e);
    const t = bajo(px, py);
    if (!t) return false;
    const plano = planoDeArrastre();
    const inv = inversaDelPlano(plano, t.p);
    if (!inv) {
      if (typeof Comandos !== "undefined") {
        Comandos.eco("Ese plano se ve de canto desde aquí: gira la vista o usa otra ventana "
          + "para jalar este punto.", "malo");
      }
      return true;              // el clic fue nuestro: que no empiece a jalar una cara
    }
    arrastre = { ...t, plano, inv, px, py, d: [0, 0, 0] };
    if (window.pintar) window.pintar();
    return true;
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
    const e0 = Planos.aMundo(arrastre.plano, 0, 0, 0);
    const p = Planos.aMundo(arrastre.plano, du, dv, 0);
    arrastre.d = [p[0] - e0[0], p[1] - e0[1], p[2] - e0[2]].map((k) => Math.round(k * 100) / 100);
    if (window.pintar) window.pintar();
    return true;
  }

  async function arriba() {
    const a = arrastre;
    arrastre = null;
    if (!a) return false;
    if (window.pintar) window.pintar();
    if (!a.d || a.d.every((k) => !k)) return true;      // un clic no es un arrastre
    await aplicar(a);
    return true;
  }

  async function aplicar(a) {
    const url = `/api/cuerpo/${a.id}/mover-${a.tipo}`;
    try {
      const r = await fetch(url, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: a.nombre, d: a.d }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.status);
      olvidar(a.id);
      await Cuerpos.refrescarUna(a.id);
      cargar(a.id);
      const que = a.tipo === "vertice" ? "punto" : "arista";
      Comandos.eco(`${que} «${a.nombre}» movido (${a.d.join(", ")})`
        + ` · ahora ${j.caja[0]} × ${j.caja[1]} × ${j.caja[2]}`);
    } catch (e) {
      // El motor deshace solo si la pieza no cierra: lo que hay que hacer aquí
      // es decir por qué y volver a pedir los tiradores, que no cambiaron.
      Comandos.eco("No se pudo mover: " + e.message, "malo");
      olvidar(a.id);
      cargar(a.id);
    }
  }

  return { pintar, abajo, mover, arriba, bajo, cargar, olvidar, delMundo,
           planoDeArrastre, arrastrando: () => !!arrastre };
})();

if (typeof window !== "undefined") window.Tiradores = Tiradores;
if (typeof module !== "undefined") module.exports = Tiradores;
