/* Las cotas de la pieza señalada, en la ventana  ·  0.16.0
 *
 * Mike, 19-sep, sobre la etapa B: *«hoy sólo se mueven los puntos con el
 * ratón; que cambiar el ancho a 900 sea teclear 900»*. El panel del historial
 * ya deja teclearlo. Esto es la otra mitad: **ver la medida sin teclear nada**.
 *
 * Tres cotas y ninguna más —ancho, fondo y espesor de la caja de la pieza—,
 * porque son las tres que se dicen en un taller cuando se pide un tablero. No
 * es un acotado de plano: es el letrero de la pieza que estás tocando.
 *
 * **Se dibujan en píxeles, no en unidades del dibujo.** El texto y las flechas
 * miden lo mismo con cualquier zoom, que es lo que uno espera de una ayuda en
 * pantalla; las cotas del documento —las de `cotas.js`, que sí se imprimen—
 * siguen viviendo en unidades, como deben.
 *
 * La caja se saca de la malla que ya está en pantalla y no de una llamada
 * nueva: la pieza ya está pintada, la caja es leerla. Si hubiera que preguntar
 * al servidor, las cotas irían siempre un cuadro tarde.
 */

const CotasPieza = (() => {
  let encendido = true;

  /** La caja de la pieza, del mundo. `Cuerpos.medidas()` trae el **tamaño**,
   *  que no basta: para poner una cota hace falta saber dónde empieza. */
  function caja(id) {
    const m = window.Cuerpos && Cuerpos.medidas(id);
    if (!m || !m.caras) return null;
    let lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const cara of m.caras) {
      const vs = cara.vertices || cara.v || [];
      for (let i = 0; i + 2 < vs.length; i += 3) {
        for (let k = 0; k < 3; k++) {
          const x = vs[i + k];
          if (x < lo[k]) lo[k] = x;
          if (x > hi[k]) hi[k] = x;
        }
      }
    }
    return isFinite(lo[0]) ? { lo, hi } : null;
  }

  function numero(v) {
    // Sin decimales cuando son cero: «600» se lee mejor que «600.00», y en el
    // taller se dicta así.
    const r = Math.round(v * 100) / 100;
    return (Number.isInteger(r) ? r : r.toFixed(2)) + "";
  }

  /** Una cota entre dos puntos del mundo, corrida `sep` píxeles hacia donde
   *  diga `hacia` (también en píxeles). */
  function una(c, A, B, texto, sep, hacia, color) {
    const a = window.aPX(A[0], A[1], A[2]);
    const b = window.aPX(B[0], B[1], B[2]);
    const largo = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (largo < 26) return;            // más corta que su propio texto: estorba
    const n = [hacia[0], hacia[1]];
    const a2 = [a[0] + n[0] * sep, a[1] + n[1] * sep];
    const b2 = [b[0] + n[0] * sep, b[1] + n[1] * sep];

    c.strokeStyle = color;
    c.fillStyle = color;
    c.lineWidth = 1;

    // Los testigos: del filo de la pieza a la línea de cota, con un respiro.
    c.beginPath();
    c.moveTo(a[0] + n[0] * 3, a[1] + n[1] * 3);
    c.lineTo(a2[0] + n[0] * 4, a2[1] + n[1] * 4);
    c.moveTo(b[0] + n[0] * 3, b[1] + n[1] * 3);
    c.lineTo(b2[0] + n[0] * 4, b2[1] + n[1] * 4);
    c.stroke();

    c.beginPath();
    c.moveTo(a2[0], a2[1]);
    c.lineTo(b2[0], b2[1]);
    c.stroke();

    // Palomitas en vez de flechas: es lo que usa el taller en sus planos, y a
    // este tamaño se leen mejor que una punta rellena.
    const u = [(b2[0] - a2[0]) / largo, (b2[1] - a2[1]) / largo];
    for (const [p, s] of [[a2, 1], [b2, -1]]) {
      c.beginPath();
      c.moveTo(p[0] - (u[0] + u[1]) * 4 * s, p[1] - (u[1] - u[0]) * 4 * s);
      c.lineTo(p[0] + (u[0] + u[1]) * 4 * s, p[1] + (u[1] - u[0]) * 4 * s);
      c.stroke();
    }

    const mx = (a2[0] + b2[0]) / 2, my = (a2[1] + b2[1]) / 2;
    c.font = "11px ui-monospace, Menlo, Consolas, monospace";
    c.textAlign = "center";
    c.textBaseline = "middle";
    const ancho = c.measureText(texto).width + 8;
    // Una caja debajo del número: encima de una pieza de madera, texto claro
    // sobre claro no se lee.
    c.save();
    c.globalAlpha = 0.85;
    c.fillStyle = "rgba(20,22,28,0.92)";
    c.fillRect(mx - ancho / 2, my - 8, ancho, 16);
    c.restore();
    c.fillStyle = color;
    c.fillText(texto, mx, my);
  }

  /** Hacia dónde sale la cota, en píxeles: perpendicular al tramo y **hacia
   *  afuera de la pieza**, que se sabe mirando dónde quedó su centro. */
  function afuera(A, B, centro) {
    const a = window.aPX(A[0], A[1], A[2]);
    const b = window.aPX(B[0], B[1], B[2]);
    const cm = window.aPX(centro[0], centro[1], centro[2]);
    const d = [b[0] - a[0], b[1] - a[1]];
    const L = Math.hypot(d[0], d[1]) || 1;
    let n = [-d[1] / L, d[0] / L];
    const m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    if ((m[0] - cm[0]) * n[0] + (m[1] - cm[1]) * n[1] < 0) n = [-n[0], -n[1]];
    return n;
  }

  const SEP = 18;                       // píxeles de la pieza a la línea de cota

  /** Las tres cotas de la pieza señalada, **en un solo sitio**: pintarlas y
   *  picarlas tienen que medir lo mismo o se pica una y se edita otra.
   *
   *  Son las tres aristas de la caja que nacen en la esquina de abajo. Se
   *  eligió esa esquina y no otra para que las tres no se encimen entre ellas.
   */
  function tramos(id) {
    const k = caja(id);
    if (!k) return [];
    const { lo, hi } = k;
    const centro = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2];
    return [
      { que: "ancho",   etiqueta: "Ancho",   A: [lo[0], lo[1], lo[2]], B: [hi[0], lo[1], lo[2]], medida: hi[0] - lo[0] },
      { que: "fondo",   etiqueta: "Fondo",   A: [hi[0], lo[1], lo[2]], B: [hi[0], hi[1], lo[2]], medida: hi[1] - lo[1] },
      { que: "espesor", etiqueta: "Espesor", A: [lo[0], lo[1], lo[2]], B: [lo[0], lo[1], hi[2]], medida: hi[2] - lo[2] },
    ].filter((t) => t.medida > 1e-6).map((t) => ({ ...t, hacia: afuera(t.A, t.B, centro) }));
  }

  /** Dónde cae el número de una cota, en píxeles del lienzo. Es el blanco que
   *  se pica para teclear la medida. */
  function blanco(t) {
    const a = window.aPX(t.A[0], t.A[1], t.A[2]);
    const b = window.aPX(t.B[0], t.B[1], t.B[2]);
    if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 26) return null;
    const x = (a[0] + b[0]) / 2 + t.hacia[0] * SEP;
    const y = (a[1] + b[1]) / 2 + t.hacia[1] * SEP;
    const ancho = 10 + String(numero(t.medida)).length * 7;
    return { x: x - ancho / 2, y: y - 9, w: ancho, h: 18 };
  }

  function pintar(c) {
    if (!encendido || !window.aPX || !window.Cuerpos) return;
    const s = Cuerpos.senalada;
    if (!s) return;
    const color = "#ffd35a";
    c.save();
    for (const t of tramos(s.id)) {
      una(c, t.A, t.B, numero(t.medida), SEP, t.hacia, color);
    }
    c.restore();
  }

  // --- picar una cota y teclear la medida ----------------------------------
  //
  // Mike pidió «UI intuitiva sin necesidad de comandos complejos». Lo más
  // directo que hay para cambiar una medida es picar la medida.

  function coords(e) {
    const lienzo = document.querySelector("canvas");
    const r = lienzo.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  function cotaEn(px, py) {
    if (!encendido || !window.aPX || !window.Cuerpos || !Cuerpos.senalada) return null;
    for (const t of tramos(Cuerpos.senalada.id)) {
      const b = blanco(t);
      if (b && px >= b.x && px <= b.x + b.w && py >= b.y && py <= b.y + b.h) return t;
    }
    return null;
  }

  /** Qué paso del historial manda esa medida. El ancho y el fondo viven en el
   *  contorno; el espesor, en la extrusión. Se busca por lo que el paso
   *  **ofrece**, no por su número: así un historial con otro orden sigue
   *  funcionando. */
  function donde(pasos, que) {
    const clave = que === "espesor" ? "mm" : que;
    for (const p of pasos) {
      if (que === "espesor" && p.op !== "extruir") continue;
      if (que !== "espesor" && p.op !== "boceto") continue;
      if ((p.campos || []).some((c) => c.clave === clave)) return { i: p.i, clave };
    }
    return null;
  }

  async function editar(t) {
    const id = Cuerpos.senalada.id;
    let pasos = (window.Historial && Historial.id === id) ? Historial.pasos : [];
    if (!pasos.length) {
      try {
        pasos = (await fetch(`/api/cuerpo/${id}/historial`).then((x) => x.json())).pasos || [];
      } catch (e) { pasos = []; }
    }
    const d = donde(pasos, t.que);
    if (!d) {
      Comandos.eco("Esta medida no sale de un número del historial, así que no se "
        + "puede teclear. Jálala con los tiradores.", "malo");
      return;
    }
    const v = await Entrada.pedirNumero({
      mensaje: `${t.etiqueta} de la pieza`, valor: Math.round(t.medida * 100) / 100,
      minimo: 0.01, clave: "cota-pieza-" + t.que });
    if (!isFinite(v) || v <= 0) return;
    try {
      const r = await fetch(`/api/cuerpo/${id}/paso/${d.i}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ campos: { [d.clave]: v } }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.status);
      if (window.Historial) await Historial.trasCambiar(j, `${t.etiqueta} = ${v}`);
      else { await Cuerpos.refrescarUna(id); }
    } catch (e) {
      Comandos.eco("No se pudo: " + e.message, "malo");
    }
  }

  /** El clic. Va **antes que los tiradores**: el número de una cota se pinta
   *  encima de todo, y lo que se ve encima es lo que se agarra. */
  function abajo(e) {
    if (e.button !== 0 || !window.aPX) return false;
    const [px, py] = coords(e);
    const t = cotaEn(px, py);
    if (!t) return false;
    editar(t);                    // no se espera: el clic ya se consumió
    return true;
  }

  function alternar(v) {
    encendido = v === undefined ? !encendido : !!v;
    if (window.pintar) window.pintar();
    return encendido;
  }

  // `caja` sale al mundo para que la prueba mida lo mismo que se dibuja, y
  // no sólo compruebe que pintar no truena.
  return { pintar, alternar, caja, tramos, blanco, cotaEn, donde, abajo,
           get encendido() { return encendido; } };
})();

if (typeof window !== "undefined") window.CotasPieza = CotasPieza;
if (typeof module !== "undefined") module.exports = CotasPieza;

if (typeof Comandos !== "undefined") {
  Comandos.registrar({
    nombre: "COTAPIEZA", alias: ["CP", "PIECEDIM"],
    ayuda: "COTAPIEZA — enciende o apaga las cotas de la pieza señalada",
    correr: async () => {
      const v = CotasPieza.alternar();
      Comandos.eco("Cotas de la pieza: " + (v ? "encendidas" : "apagadas"));
    },
  });
}
