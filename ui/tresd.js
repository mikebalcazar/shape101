/* Señalar y jalar caras  ·  sobre el lienzo de siempre  ·  0.6.0
 *
 * Esto era antes un lienzo aparte que se ponía encima del dibujo. Ya no: las
 * piezas se pintan en el mismo sitio que las líneas (ver `cuerpos.js`), así que
 * aquí sólo queda el gesto —señalar una cara y jalarla—, el aviso de lo que va
 * a pasar antes de que pase, y los dos comandos que levantan una pieza.
 *
 * **El fantasma.** Mientras arrastras se dibuja dónde va a quedar la cara y
 * cuántos milímetros llevas, siguiendo al cursor. Hasta la 0.5.0 no se veía
 * nada hasta soltar, y Mike lo dijo claro: *«falta mucho feedback visual, hay
 * que ir viendo en tiempo real a dónde se mueve la cara»*.
 *
 * No se le pide la pieza al motor en cada cuadro a propósito. Rehacer un sólido
 * cuesta decenas de milisegundos y el ratón manda eventos mucho más seguido: se
 * encolarían y el arrastre se sentiría pegajoso, que es peor que no ver nada.
 * El fantasma es una promesa barata; al soltar, el motor la cumple y la pieza
 * se rehace de verdad.
 *
 * **La medida se toma sobre la cara, no sobre la pantalla.** El arrastre se
 * proyecta en la dirección a la que la cara mira. Sin eso, jalar una cara vista
 * de canto se sentiría al revés: la pantalla no sabe hacia dónde mira la cara,
 * el sólido sí.
 */

const TresD = (() => {
  let arrastre = null;

  function lienzo() { return document.getElementById("lienzo"); }

  function coords(e) {
    const r = lienzo().getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  function normal(P) {
    const [A, B, C] = P;
    const u = [B[0] - A[0], B[1] - A[1], B[2] - A[2]];
    const w = [C[0] - A[0], C[1] - A[1], C[2] - A[2]];
    const n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const l = Math.hypot(n[0], n[1], n[2]) || 1;
    return [n[0] / l, n[1] / l, n[2] / l];
  }

  /** Cuántos milímetros representa el arrastre, medidos sobre la dirección a la
   *  que apunta la cara. */
  function mmDelArrastre(a, px, py) {
    const q0 = window.aPX(0, 0, 0);
    const q1 = window.aPX(a.normal[0], a.normal[1], a.normal[2]);
    const dir = [q1[0] - q0[0], q1[1] - q0[1]];
    const largo = Math.hypot(dir[0], dir[1]);
    // Cara vista **exactamente** de canto: su dirección no se proyecta en la
    // pantalla y no hay forma honesta de saber cuánto quiere moverse el ratón.
    // Antes de inventar un número, se avisa y se deja que gire la vista.
    if (largo < 1e-6) return null;
    const proy = ((px - a.px) * dir[0] + (py - a.py) * dir[1]) / largo;
    return Math.round((proy / estado.vista.escala) * 100) / 100;
  }

  // --- el fantasma ---------------------------------------------------------
  /** Lo dibuja `vista.js` en la capa de encima, en cada cuadro, mientras dure
   *  el arrastre. Es sólo la cara movida y la cota: nada de rehacer el sólido. */
  function pintarFantasma(c) {
    const a = arrastre;
    if (!a || a.mm === null || !a.mm || !window.aPX) return;
    const d = a.normal.map((n) => n * a.mm);
    c.save();
    c.strokeStyle = "rgba(255,211,90,0.95)";
    c.fillStyle = "rgba(255,211,90,0.22)";
    c.lineWidth = 1.5;
    c.setLineDash([6, 4]);
    c.beginPath();
    a.contorno.forEach((p, i) => {
      const q = window.aPX(p[0] + d[0], p[1] + d[1], p[2] + d[2]);
      if (i) c.lineTo(q[0], q[1]); else c.moveTo(q[0], q[1]);
    });
    c.closePath();
    c.fill();
    c.stroke();
    // Las líneas que unen la cara vieja con la nueva: es lo que hace ver
    // **cuánto** se movió, no sólo a dónde llegó.
    c.setLineDash([2, 3]);
    for (const p of a.contorno) {
      const q0 = window.aPX(p[0], p[1], p[2]);
      const q1 = window.aPX(p[0] + d[0], p[1] + d[1], p[2] + d[2]);
      c.beginPath();
      c.moveTo(q0[0], q0[1]);
      c.lineTo(q1[0], q1[1]);
      c.stroke();
    }
    c.setLineDash([]);
    const texto = `${a.mm > 0 ? "+" : ""}${a.mm.toFixed(2)} mm`;
    c.font = "bold 13px system-ui, sans-serif";
    const an = c.measureText(texto).width + 12;
    const px = a.px2 || a.px, py = a.py2 || a.py;
    c.fillStyle = "rgba(0,0,0,0.72)";
    c.fillRect(px + 14, py - 26, an, 20);
    c.fillStyle = "#ffd35a";
    c.fillText(texto, px + 20, py - 12);
    c.restore();
  }

  /** El borde de la cara, para dibujar el fantasma. Si no se puede sacar de la
   *  malla, se usa el triángulo que se señaló: peor aviso que el bueno, pero
   *  mejor que ninguno. */
  function contornoDe(malla, tri) {
    if (!malla || !malla.v || !malla.i) return tri;
    const pts = [];
    for (let k = 0; k < malla.v.length; k += 3) pts.push([malla.v[k], malla.v[k + 1], malla.v[k + 2]]);
    if (pts.length < 3) return tri;
    // Se ordenan alrededor de su propio centro: para una cara plana —que es lo
    // que son todas las de una pieza de taller— eso da su contorno.
    const c = pts.reduce((s, p) => [s[0] + p[0] / pts.length, s[1] + p[1] / pts.length, s[2] + p[2] / pts.length], [0, 0, 0]);
    const n = normal(tri);
    const ejeU = Math.abs(n[2]) < 0.9 ? [-n[1], n[0], 0] : [1, 0, 0];
    const lu = Math.hypot(ejeU[0], ejeU[1], ejeU[2]) || 1;
    const u = ejeU.map((x) => x / lu);
    const v = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0]];
    const ang = (p) => {
      const dd = [p[0] - c[0], p[1] - c[1], p[2] - c[2]];
      return Math.atan2(dd[0] * v[0] + dd[1] * v[1] + dd[2] * v[2],
                        dd[0] * u[0] + dd[1] * u[1] + dd[2] * u[2]);
    };
    return pts.slice().sort((a, b) => ang(a) - ang(b));
  }

  // --- el gesto ------------------------------------------------------------
  function abajo(e) {
    if (e.button !== 0 || !Cuerpos.hay() || !window.aPX) return false;
    const [px, py] = coords(e);
    const cara = Cuerpos.caraEn(px, py);
    if (!cara) return false;
    Cuerpos.senalar(cara);
    const m = Cuerpos.medidas(cara.id);
    const malla = (m && (m.caras || []).find((k) => k.nombre === cara.cara)) || null;
    arrastre = {
      id: cara.id, cara: cara.cara, px, py, mm: 0,
      normal: normal(cara.tri.P),
      contorno: contornoDe(malla, cara.tri.P),
    };
    return true;             // el clic fue nuestro: que no seleccione ni dibuje
  }

  function mover(e) {
    if (!arrastre) return false;
    const [px, py] = coords(e);
    arrastre.mm = mmDelArrastre(arrastre, px, py);
    arrastre.px2 = px;
    arrastre.py2 = py;
    if (arrastre.mm === null && !arrastre.avisado) {
      arrastre.avisado = true;
      Comandos.eco("Esa cara se ve de canto: gira un poco la vista con ORBITAR para poder jalarla.", "malo");
    }
    if (typeof Vista !== "undefined" && Vista.pintar) Vista.pintar();
    return true;
  }

  async function arriba() {
    const a = arrastre;
    arrastre = null;
    if (!a) return false;
    if (typeof Vista !== "undefined" && Vista.pintar) Vista.pintar();
    if (a.mm === null || Math.abs(a.mm) < 0.5) return true;   // un clic no es una jalada
    await jalar(a.id, a.cara, a.mm);
    return true;
  }

  async function jalar(id, cara, mm) {
    try {
      const r = await fetch(`/api/cuerpo/${id}/empujar-cara`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cara, mm }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.status);
      await Cuerpos.refrescarUna(id);
      Comandos.eco(`cara «${cara}» movida ${mm > 0 ? "+" : ""}${mm} mm · ahora ${j.caja[0]} × ${j.caja[1]} × ${j.caja[2]} mm`);
    } catch (e) {
      Comandos.eco("No se pudo jalar: " + e.message, "malo");
    }
  }

  return { abajo, mover, arriba, jalar, pintarFantasma,
           arrastrando: () => !!arrastre,
           senalada: () => Cuerpos.senalada,
           primerCuerpo: () => Cuerpos.primero() };
})();

window.TresD = TresD;

/* --- los comandos --------------------------------------------------------- */

Comandos.registrar({
  nombre: "EXTRUIR", alias: ["EXT", "EXTRUDE"],
  ayuda: "EXTRUIR [mm] · levanta el contorno seleccionado y lo vuelve una pieza sólida",
  correr: async (args) => {
    const ids = [...(typeof estado !== "undefined" && estado.sel ? estado.sel : [])];
    if (!ids.length) { Comandos.eco("Selecciona primero el contorno cerrado que quieres levantar.", "malo"); return; }
    let mm = parseFloat(args[0]);
    if (!isFinite(mm)) {
      // Electron no tiene la ventanita de preguntar del navegador: usarla deja
      // el comando muerto. La app ya pide medidas con la cajita de siempre,
      // que acepta coma o punto y recuerda lo último que se tecleó.
      if (typeof Entrada === "undefined" || !Entrada.pedirNumero) {
        Comandos.eco("EXTRUIR necesita un espesor.", "malo");
        return;
      }
      mm = await Entrada.pedirNumero({ mensaje: "Espesor en mm", valor: 18, clave: "extruir-espesor" });
    }
    if (!isFinite(mm) || mm === 0) { Comandos.eco("EXTRUIR necesita un espesor distinto de cero.", "malo"); return; }
    try {
      const m = await fetch("/api/cuerpo/extruir", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, mm }),
      }).then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || r.status); return j; });
      await Cuerpos.refrescar();
      // Se gira a isométrica sólo si se estaba mirando desde arriba: en planta
      // una pieza recién levantada se ve idéntica al contorno del que salió, y
      // parecería que no pasó nada. Si el usuario ya había girado la vista, se
      // respeta la suya.
      if (typeof Camara !== "undefined" && Camara.enPlanta()) Camara.ver("ISO");
      Comandos.eco(`pieza de ${m.caja[0]} × ${m.caja[1]} × ${m.caja[2]} mm · ${(m.volumen_mm3 / 1000).toFixed(1)} cm³`);
    } catch (e) { Comandos.eco("No se pudo extruir: " + e.message, "malo"); }
  },
});

Comandos.registrar({
  nombre: "3D", alias: ["TRESD", "VER3D"],
  ayuda: "Alterna entre mirar desde arriba y la vista isométrica",
  correr: async () => {
    if (typeof Camara === "undefined") return;
    await Cuerpos.refrescar();
    if (Camara.enPlanta()) { Camara.ver("ISO"); Comandos.eco("vista isométrica · ORBITAR para girarla"); }
    else { Camara.ver("PLANTA"); Comandos.eco("vista de planta: se dibuja como siempre"); }
  },
});
