/* El 3D  ·  pintar cuerpos, girar la vista, jalar caras y mover puntos.
 *
 * Sin three.js a propósito. El motor ya manda los triángulos de cada cara y
 * las aristas; lo que falta es proyectarlos, ordenarlos por profundidad y
 * pintarlos. Eso son estas líneas. Meter una biblioteca de 1.2 MB para hacer
 * lo mismo habría engordado el instalador y atado el dibujo a la forma de
 * pensar de otro.
 *
 * Dos decisiones que se notan al usarlo:
 *
 * - **Una malla por cara.** Llegan separadas y con nombre. Así se puede
 *   señalar una con el ratón y saber cuál es para jalarla, que es de lo que se
 *   trata todo esto. Una sola malla para el sólido entero se pintaría más
 *   rápido y no serviría para modelar.
 * - **Se jala con el ratón, pero la medida se toma sobre la cara.** El
 *   arrastre se proyecta sobre la dirección a la que la cara apunta, no sobre
 *   la pantalla. Sin eso, jalar una cara vista de canto se sentiría al revés.
 *
 * El pintado va con el algoritmo del pintor: triángulos ordenados de lejos a
 * cerca. Con las piezas de un mueble —decenas de caras, no millones— alcanza
 * de sobra, y no necesita nada del navegador más que un canvas 2D.
 */

const TresD = (() => {
  const API = "/api/cuerpo";
  let lienzo = null, ctx = null;
  let activo = false;
  const cuerpos = new Map();          // id → malla del motor
  let camara = { rx: -1.1, rz: 0.6, zoom: 1, cx: 0, cy: 0 };
  let senalada = null;                // {id, cara}
  let arrastre = null;
  let puntoSenalado = null;           // {id, entidad, punto}

  // --- el lienzo -----------------------------------------------------------
  function preparar() {
    if (lienzo) return;
    lienzo = document.createElement("canvas");
    lienzo.id = "lienzo3d";
    Object.assign(lienzo.style, {
      position: "absolute", inset: "0", width: "100%", height: "100%",
      display: "none", zIndex: "5", cursor: "grab", touchAction: "none",
    });
    const casa = document.getElementById("lienzo")?.parentElement || document.body;
    casa.appendChild(lienzo);
    ctx = lienzo.getContext("2d");
    lienzo.addEventListener("pointerdown", alBajar);
    lienzo.addEventListener("pointermove", alMover);
    window.addEventListener("pointerup", alSubir);
    lienzo.addEventListener("wheel", (e) => {
      e.preventDefault();
      camara.zoom *= e.deltaY < 0 ? 1.1 : 1 / 1.1;
      pintar();
    }, { passive: false });
    window.addEventListener("resize", () => { medir(); pintar(); });
  }

  function medir() {
    if (!lienzo) return;
    const r = lienzo.getBoundingClientRect();
    const d = window.devicePixelRatio || 1;
    lienzo.width = Math.max(1, Math.round(r.width * d));
    lienzo.height = Math.max(1, Math.round(r.height * d));
    ctx.setTransform(d, 0, 0, d, 0, 0);
  }

  // --- la cámara -----------------------------------------------------------
  // Órbita sencilla: se gira alrededor de Z (rz) y se inclina (rx). Sin
  // perspectiva: en un taller se mide, y la perspectiva engaña al ojo.
  function proyectar(p) {
    const cz = Math.cos(camara.rz), sz = Math.sin(camara.rz);
    const cx = Math.cos(camara.rx), sx = Math.sin(camara.rx);
    const x = p[0] * cz - p[1] * sz;
    const y = p[0] * sz + p[1] * cz;
    const yy = y * cx - p[2] * sx;
    const prof = y * sx + p[2] * cx;                 // lo que está más lejos
    const w = lienzo.clientWidth, h = lienzo.clientHeight;
    return [w / 2 + (x - camara.cx) * camara.zoom,
            h / 2 - (yy - camara.cy) * camara.zoom, prof];
  }

  function encuadrar() {
    const pts = [];
    for (const m of cuerpos.values()) {
      for (const c of m.caras || []) {
        for (let i = 0; i < c.v.length; i += 3) pts.push([c.v[i], c.v[i + 1], c.v[i + 2]]);
      }
    }
    if (!pts.length) return;
    // Dos pasadas: la primera mide con zoom 1 para sacar la escala, la segunda
    // centra ya con esa escala puesta. Sale más corto que despejar la ecuación.
    camara.zoom = 1; camara.cx = 0; camara.cy = 0;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const p of pts) {
      const q = proyectar(p);
      x0 = Math.min(x0, q[0]); x1 = Math.max(x1, q[0]);
      y0 = Math.min(y0, q[1]); y1 = Math.max(y1, q[1]);
    }
    const w = lienzo.clientWidth, h = lienzo.clientHeight;
    camara.zoom = Math.min(w / Math.max(1, x1 - x0), h / Math.max(1, y1 - y0)) * 0.75;
    let a0 = Infinity, b0 = Infinity, a1 = -Infinity, b1 = -Infinity;
    for (const p of pts) {
      const q = proyectar(p);
      a0 = Math.min(a0, q[0]); a1 = Math.max(a1, q[0]);
      b0 = Math.min(b0, q[1]); b1 = Math.max(b1, q[1]);
    }
    camara.cx = ((a0 + a1) / 2 - w / 2) / camara.zoom;
    camara.cy = -((b0 + b1) / 2 - h / 2) / camara.zoom;
  }

  // --- pintar --------------------------------------------------------------
  const LUZ = [0.4, -0.5, 0.75];

  function triangulos() {
    const tris = [];
    for (const [id, m] of cuerpos) {
      for (const c of m.caras || []) {
        const v = c.v, ix = c.i;
        for (let k = 0; k < ix.length; k += 3) {
          const a = ix[k] * 3, b = ix[k + 1] * 3, d = ix[k + 2] * 3;
          const P = [[v[a], v[a + 1], v[a + 2]], [v[b], v[b + 1], v[b + 2]], [v[d], v[d + 1], v[d + 2]]];
          const q = P.map(proyectar);
          tris.push({ id, cara: c.nombre, q, prof: (q[0][2] + q[1][2] + q[2][2]) / 3, P });
        }
      }
    }
    tris.sort((p, s) => p.prof - s.prof);      // de lejos a cerca
    return tris;
  }

  function color(t, elegida) {
    const n = normalDe(t);
    const luz = Math.abs(n[0] * LUZ[0] + n[1] * LUZ[1] + n[2] * LUZ[2]);
    const tono = 0.35 + 0.65 * luz;
    if (elegida) return `rgb(${Math.round(255 * tono)},${Math.round(200 * tono)},${Math.round(70 * tono)})`;
    return `rgb(${Math.round(190 * tono)},${Math.round(160 * tono)},${Math.round(120 * tono)})`;
  }

  function pintar() {
    if (!activo || !ctx) return;
    const w = lienzo.clientWidth, h = lienzo.clientHeight;
    ctx.clearRect(0, 0, w, h);
    for (const t of triangulos()) {
      const elegida = senalada && senalada.id === t.id && senalada.cara === t.cara;
      ctx.fillStyle = color(t, elegida);
      ctx.beginPath();
      ctx.moveTo(t.q[0][0], t.q[0][1]);
      ctx.lineTo(t.q[1][0], t.q[1][1]);
      ctx.lineTo(t.q[2][0], t.q[2][1]);
      ctx.closePath();
      ctx.fill();
    }
    ctx.strokeStyle = "rgba(20,20,20,0.85)";
    ctx.lineWidth = 1;
    for (const m of cuerpos.values()) {
      for (const a of m.aristas || []) {
        ctx.beginPath();
        a.forEach((p, i) => { const q = proyectar(p); i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); });
        ctx.stroke();
      }
    }
    pintarPuntos();
    pintarLetrero();
  }

  /** Los vértices del contorno con el que nació la pieza. Se pintan en el
   *  plano de abajo (z = 0) porque es donde vive el boceto. */
  function puntosDelBoceto() {
    const out = [];
    for (const [id, m] of cuerpos) {
      const ops = m.operaciones_json || [];
      ops.forEach((op) => {
        if (op.op !== "boceto") return;
        (op.entidades || []).forEach((e, ie) => {
          if (e.tipo === "polilinea") (e.puntos || []).forEach((p, ip) => out.push({ id, entidad: ie, punto: ip, p: [p[0], p[1], 0] }));
          else if (e.tipo === "circulo" || e.tipo === "arco") out.push({ id, entidad: ie, punto: 0, p: [e.centro[0], e.centro[1], 0] });
          else if (e.tipo === "linea") { out.push({ id, entidad: ie, punto: 0, p: [e.p1[0], e.p1[1], 0] }); out.push({ id, entidad: ie, punto: 1, p: [e.p2[0], e.p2[1], 0] }); }
        });
      });
    }
    return out;
  }

  function pintarPuntos() {
    for (const v of puntosDelBoceto()) {
      const q = proyectar(v.p);
      const elegido = puntoSenalado && puntoSenalado.id === v.id
        && puntoSenalado.entidad === v.entidad && puntoSenalado.punto === v.punto;
      ctx.fillStyle = elegido ? "#ffd35a" : "#2a7fff";
      ctx.beginPath();
      ctx.arc(q[0], q[1], elegido ? 6 : 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function pintarLetrero() {
    const m = [...cuerpos.values()][0];
    if (!m || !m.caja) return;
    const txt = `${m.caja[0]} × ${m.caja[1]} × ${m.caja[2]} mm · ${(m.volumen_mm3 / 1000).toFixed(1)} cm³`
      + (senalada ? ` · cara «${senalada.cara}»` : "");
    ctx.fillStyle = "rgba(0,0,0,0.6)";
    ctx.font = "12px system-ui, sans-serif";
    const an = ctx.measureText(txt).width + 12;
    ctx.fillRect(8, 8, an, 22);
    ctx.fillStyle = "#fff";
    ctx.fillText(txt, 14, 23);
  }

  // --- señalar con el ratón ------------------------------------------------
  function dentro(q, x, y) {
    const [a, b, c] = q;
    const s = (p1, p2) => (x - p2[0]) * (p1[1] - p2[1]) - (p1[0] - p2[0]) * (y - p2[1]);
    const d1 = s(a, b), d2 = s(b, c), d3 = s(c, a);
    const neg = d1 < 0 || d2 < 0 || d3 < 0, pos = d1 > 0 || d2 > 0 || d3 > 0;
    return !(neg && pos);
  }

  function caraEn(x, y) {
    const tris = triangulos();
    for (let i = tris.length - 1; i >= 0; i--) if (dentro(tris[i].q, x, y)) return tris[i];
    return null;
  }

  function puntoEn(x, y) {
    for (const v of puntosDelBoceto()) {
      const q = proyectar(v.p);
      if (Math.hypot(q[0] - x, q[1] - y) <= 8) return v;
    }
    return null;
  }

  function coords(e) {
    const r = lienzo.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  function normalDe(t) {
    const [A, B, C] = t.P;
    const u = [B[0] - A[0], B[1] - A[1], B[2] - A[2]];
    const w = [C[0] - A[0], C[1] - A[1], C[2] - A[2]];
    const n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const l = Math.hypot(n[0], n[1], n[2]) || 1;
    return n.map((v) => v / l);
  }

  function alBajar(e) {
    const [x, y] = coords(e);
    const v = puntoEn(x, y);
    if (v) {
      puntoSenalado = v; senalada = null;
      arrastre = { que: "punto", v, x, y };
      lienzo.style.cursor = "grabbing";
      pintar();
      return;
    }
    const t = caraEn(x, y);
    if (t && !e.shiftKey) {
      senalada = { id: t.id, cara: t.cara };
      puntoSenalado = null;
      arrastre = { que: "cara", id: t.id, cara: t.cara, x, y, normal: normalDe(t) };
      lienzo.style.cursor = "ns-resize";
      pintar();
      return;
    }
    arrastre = { que: "girar", x, y, rx: camara.rx, rz: camara.rz };
    lienzo.style.cursor = "grabbing";
  }

  function alMover(e) {
    if (!arrastre) return;
    const [x, y] = coords(e);
    if (arrastre.que === "girar") {
      camara.rz = arrastre.rz + (x - arrastre.x) * 0.01;
      camara.rx = Math.max(-Math.PI / 2, Math.min(0, arrastre.rx + (y - arrastre.y) * 0.01));
      pintar();
    } else {
      arrastre.dx = x - arrastre.x;
      arrastre.dy = y - arrastre.y;
    }
  }

  /** Cuántos milímetros representa el arrastre, medidos sobre la dirección en
   *  que apunta la cara. Sin esto, jalar una cara vista de canto se sentiría
   *  al revés: la pantalla no sabe hacia dónde mira la cara, el sólido sí. */
  function mmDelArrastre(a) {
    const q0 = proyectar([0, 0, 0]), q1 = proyectar(a.normal);
    const dir = [q1[0] - q0[0], q1[1] - q0[1]];
    const largo = Math.hypot(dir[0], dir[1]) || 1;
    const proy = ((a.dx || 0) * dir[0] + (a.dy || 0) * dir[1]) / largo;
    return Math.round((proy / camara.zoom) * 100) / 100;
  }

  async function alSubir() {
    const a = arrastre;
    arrastre = null;
    if (lienzo) lienzo.style.cursor = "grab";
    if (!a || a.que === "girar") return;
    if (a.que === "cara") {
      const mm = mmDelArrastre(a);
      if (Math.abs(mm) < 0.5) return;                 // un clic no es una jalada
      await jalar(a.id, a.cara, mm);
    } else if (a.que === "punto") {
      // El punto se mueve sobre el plano de abajo: se deshace la proyección
      // con dos direcciones conocidas, la X y la Y del dibujo.
      const o = proyectar([0, 0, 0]), ex = proyectar([1, 0, 0]), ey = proyectar([0, 1, 0]);
      const m = [[ex[0] - o[0], ey[0] - o[0]], [ex[1] - o[1], ey[1] - o[1]]];
      const det = m[0][0] * m[1][1] - m[0][1] * m[1][0];
      if (!det) return;
      const dx = ((a.dx || 0) * m[1][1] - (a.dy || 0) * m[0][1]) / det;
      const dy = ((a.dy || 0) * m[0][0] - (a.dx || 0) * m[1][0]) / det;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
      await moverPunto(a.v, a.v.p[0] + dx, a.v.p[1] + dy);
    }
  }

  // --- hablar con el motor -------------------------------------------------
  async function pedir(url, cuerpo) {
    const r = await fetch(url, cuerpo === undefined ? undefined
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || j.error || `${r.status} en ${url}`);
    return j;
  }

  function decir(txt, malo) {
    if (typeof Comandos !== "undefined" && Comandos.eco) Comandos.eco(txt, malo ? "malo" : undefined);
    else console.log(txt);
  }

  async function traer(id) {
    const m = await pedir(`${API}/${id}/malla`);
    try {
      const ent = await pedir("/api/entidades/varias", { ids: [id] });
      m.operaciones_json = (ent.entidades && ent.entidades[0] && ent.entidades[0].operaciones) || [];
    } catch (e) {
      m.operaciones_json = [];      // sin esto sólo se pierden los puntos azules
    }
    cuerpos.set(id, m);
    return m;
  }

  async function jalar(id, cara, mm) {
    try {
      await pedir(`${API}/${id}/empujar-cara`, { cara, mm });
      await traer(id);
      pintar();
      decir(`cara «${cara}» jalada ${mm} mm`);
    } catch (e) { decir("No se pudo jalar: " + e.message, true); }
  }

  async function moverPunto(v, x, y) {
    try {
      await pedir(`${API}/${v.id}/mover-punto`, { entidad: v.entidad, punto: v.punto, x, y });
      await traer(v.id);
      pintar();
      decir(`punto movido a ${x.toFixed(2)}, ${y.toFixed(2)}`);
    } catch (e) { decir("No se pudo mover: " + e.message, true); }
  }

  // --- entrar y salir ------------------------------------------------------
  async function abrir(ids) {
    preparar();
    activo = true;
    lienzo.style.display = "block";
    medir();
    for (const id of ids || []) {
      try { await traer(id); } catch (e) { decir("No se pudo traer la pieza: " + e.message, true); }
    }
    if (!cuerpos.size) decir("No hay piezas en 3D todavía: usa EXTRUIR sobre un contorno cerrado.");
    encuadrar();
    pintar();
  }

  function cerrar() {
    activo = false;
    if (lienzo) lienzo.style.display = "none";
  }

  window.addEventListener("keydown", (e) => {
    if (activo && e.key === "Escape") { cerrar(); decir("de vuelta al dibujo"); }
  });

  return { abrir, cerrar, pintar, traer, activo: () => activo, cuerpos };
})();

/* --- los comandos --------------------------------------------------------- */

Comandos.registrar({
  nombre: "EXTRUIR", alias: ["EXT", "EXTRUDE"],
  ayuda: "EXTRUIR [mm] · levanta el contorno seleccionado y lo vuelve sólido",
  correr: async (args) => {
    const ids = [...(typeof estado !== "undefined" && estado.sel ? estado.sel : [])];
    if (!ids.length) { Comandos.eco("Selecciona primero el contorno cerrado que quieres levantar.", "malo"); return; }
    let mm = parseFloat(args[0]);
    if (!isFinite(mm)) {
      // `Comandos.pedir` sólo escribe el mensaje en la consola; no devuelve lo
      // tecleado. Para una medida hace falta una respuesta, así que se pregunta
      // aparte y se sugiere el espesor más común de taller.
      mm = parseFloat(window.prompt("Espesor en mm", "18") || "");
    }
    if (!isFinite(mm) || mm === 0) { Comandos.eco("EXTRUIR necesita un espesor distinto de cero.", "malo"); return; }
    try {
      const m = await fetch("/api/cuerpo/extruir", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, mm }),
      }).then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || r.status); return j; });
      Comandos.eco(`pieza de ${m.caja[0]} × ${m.caja[1]} × ${m.caja[2]} mm · ${(m.volumen_mm3 / 1000).toFixed(1)} cm³`);
      await TresD.abrir([m.id]);
    } catch (e) { Comandos.eco("No se pudo extruir: " + e.message, "malo"); }
  },
});

Comandos.registrar({
  nombre: "3D", alias: ["TRESD", "VER3D"],
  ayuda: "Enseña las piezas en 3D · Escape para volver al dibujo",
  correr: async () => {
    if (TresD.activo()) { TresD.cerrar(); return; }
    await TresD.abrir([...TresD.cuerpos.keys()]);
  },
});
