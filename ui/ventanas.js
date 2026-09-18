/* Las cuatro ventanas  ·  superior, frontal, lateral y perspectiva  ·  0.9.0
 *
 * Decisión de Mike (17-sep): como Rhino. Un solo lienzo partido en 2×2, cada
 * ventana con su cámara fija, y dibujar en una ventana dibuja sobre su plano:
 * superior → XY en z = 0, frontal → XZ, lateral → YZ. Doble clic en el título
 * maximiza una; doble clic otra vez la devuelve.
 *
 * **Cómo se cuela esto en un programa que sólo sabía de una vista.** La ventana
 * activa ES `estado.vista`: al activar otra se intercambia el objeto entero.
 * Todo lo que ya funciona —dibujar, zoom, pan, osnap, selección— trabaja sobre
 * `estado.vista` y sigue trabajando, ahora sobre la activa, sin enterarse de
 * que hay tres más. Cada cámara lleva su origen en pantalla (`ox`, `oy`) y su
 * tamaño (`w`, `h`); las dos conversiones del lienzo los suman y los restan.
 *
 * El plano de trabajo de cada ventana es dato de la cámara (`plano`). En
 * 0.9.0 todavía se dibuja sobre XY en todas: el plano por ventana entra en
 * cuanto cada línea del dibujo sepa en qué plano vive.
 */

const Ventanas = (() => {
  const GRADO = Math.PI / 180;
  const TITULO = 18;                  // alto de la franja con el nombre

  const ventanas = [
    { nombre: "Superior",    plano: "XY", rx: 0,            rz: 0 },
    { nombre: "Perspectiva", plano: "XY", rx: -60 * GRADO,  rz: 45 * GRADO, persp: true, dist: 4000 },
    { nombre: "Frontal",     plano: "XZ", rx: -90 * GRADO,  rz: 0 },
    { nombre: "Lateral",     plano: "YZ", rx: -90 * GRADO,  rz: -90 * GRADO },
  ].map((v, i) => ({ ...v, i, x: 0, y: 0, escala: 1, ox: 0, oy: 0, w: 100, h: 100 }));

  let activa = 0;
  let maximizada = null;            // índice, o null
  let ancho = 800, alto = 600;

  /** Reparte el lienzo. 2×2, o una sola si está maximizada. */
  function repartir(w, h) {
    ancho = w; alto = h;
    const mitadW = Math.floor(w / 2), mitadH = Math.floor(h / 2);
    ventanas.forEach((v, i) => {
      if (maximizada !== null) {
        const es = i === maximizada;
        Object.assign(v, { ox: 0, oy: 0, w: es ? w : 0, h: es ? h : 0 });
        return;
      }
      const col = i % 2, fila = Math.floor(i / 2);
      Object.assign(v, {
        ox: col ? mitadW : 0, oy: fila ? mitadH : 0,
        w: col ? w - mitadW : mitadW, h: fila ? h - mitadH : mitadH,
      });
    });
  }

  function la(i) { return ventanas[i]; }
  function laActiva() { return ventanas[activa]; }

  /** Qué ventana hay bajo un punto del lienzo, o -1. */
  function bajo(px, py) {
    for (const v of ventanas) {
      if (v.w <= 0 || v.h <= 0) continue;
      if (px >= v.ox && px < v.ox + v.w && py >= v.oy && py < v.oy + v.h) return v.i;
    }
    return -1;
  }

  function enTitulo(px, py) {
    const i = bajo(px, py);
    return i >= 0 && py - ventanas[i].oy < TITULO ? i : -1;
  }

  /** Navegar —pan, zoom, órbita— en la ventana bajo el cursor sin cambiar
   *  la activa: la activa es de los comandos, y se elige con clic. Mike lo
   *  quiso así: híbrido. Dura lo que dura el gesto. */
  let navegando = null;
  function navegarEn(px, py) {
    const i = bajo(px, py);
    if (i < 0 || i === activa || typeof estado === "undefined") return false;
    navegando = i;
    estado.vista = ventanas[i];
    return true;
  }
  function terminarNavegacion() {
    if (navegando === null || typeof estado === "undefined") return;
    navegando = null;
    estado.vista = ventanas[activa];
  }

  /** Activar: la cámara de esa ventana pasa a ser `estado.vista`. */
  function activar(i) {
    if (i < 0 || i >= ventanas.length || i === activa) return false;
    activa = i;
    if (typeof estado !== "undefined") estado.vista = ventanas[i];
    return true;
  }

  function maximizar(i) {
    maximizada = maximizada === i ? null : i;
    repartir(ancho, alto);
    if (maximizada !== null) activar(maximizada);
  }

  /** La misma proyección del lienzo, sin el origen de la ventana: sirve para
   *  medir dónde caería algo antes de decidir la escala. */
  function proyectar(v, x, y, z) {
    const cz = Math.cos(v.rz), sz = Math.sin(v.rz);
    const cx = Math.cos(v.rx), sx = Math.sin(v.rx);
    const ux = x * cz - y * sz;
    const uy = x * sz + y * cz;
    const vy = uy * cx - (z || 0) * sx;
    return [(ux - v.x) * v.escala, (v.y - vy) * v.escala];
  }

  /** La primera vez: la cámara que el programa traía —la de siempre— pasa a
   *  ser la ventana superior, y las otras tres se encuadran a lo que hay.
   *  Devuelve true si adoptó. */
  function adoptar(puntos) {
    if (typeof estado === "undefined" || estado.vista === ventanas[activa]) return false;
    const vieja = estado.vista || {};
    ventanas[0].x = vieja.x || 0;
    ventanas[0].y = vieja.y || 0;
    ventanas[0].escala = vieja.escala || 1;
    activa = 0;
    estado.vista = ventanas[0];
    if (puntos && puntos.length) {
      // Las otras tres se encuadran solas; la superior conserva lo que el
      // usuario tenía, que es lo que estaba mirando.
      const guardada = { x: ventanas[0].x, y: ventanas[0].y, escala: ventanas[0].escala };
      encuadrarTodas(puntos);
      Object.assign(ventanas[0], guardada);
    }
    return true;
  }

  /** Encuadra todas las ventanas a los mismos puntos [x, y, z]. Cada una desde
   *  su ángulo, con su tamaño. */
  function encuadrarTodas(puntos, proyectarCon = proyectar, solo = null) {
    for (const v of ventanas) {
      if (solo !== null && v.i !== solo) continue;
      if (v.w <= 0 || v.h <= 0 || !puntos.length) continue;
      const guardada = { x: v.x, y: v.y, escala: v.escala };
      v.x = 0; v.y = 0; v.escala = 1;
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const p of puntos) {
        const q = proyectarCon(v, p[0], p[1], p[2] || 0);
        if (q[0] < x0) x0 = q[0]; if (q[0] > x1) x1 = q[0];
        if (q[1] < y0) y0 = q[1]; if (q[1] > y1) y1 = q[1];
      }
      const an = Math.max(1e-6, x1 - x0), al = Math.max(1e-6, y1 - y0);
      const escala = Math.min(v.w / an, (v.h - TITULO) / al) * 0.84;
      if (!isFinite(escala) || escala <= 0) { Object.assign(v, guardada); continue; }
      v.escala = escala;
      // Con la escala puesta, el centro de la caja dice cuánto correr. En la
      // convención del lienzo, x e y son la esquina de arriba a la izquierda.
      // La Y proyectada ya viene volteada (py = (v.y − vy)·escala), así que el
      // centro en Y de la cámara es −cy, no cy. Es la misma trampa del signo
      // de siempre: en el dibujo la Y sube, en la pantalla baja.
      const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;      // con escala 1 y cámara en cero
      v.x = cx - v.w / 2 / escala;
      v.y = -cy + (v.h + TITULO) / 2 / escala;
    }
  }

  /** Pinta las cuatro: cada una recortada, con `estado.vista` intercambiada
   *  mientras se pinta, y devuelta al terminar. `pintarUna(c, ventana)` es
   *  del lienzo: pinta con la cámara que encuentre en `estado.vista`. */
  function pintarTodas(c, pintarUna, oscuro) {
    const guardada = typeof estado !== "undefined" ? estado.vista : null;
    try {
      for (const v of ventanas) {
        if (v.w <= 0 || v.h <= 0) continue;
        c.save();
        c.beginPath();
        c.rect(v.ox, v.oy, v.w, v.h);
        c.clip();
        if (typeof estado !== "undefined") estado.vista = v;
        pintarUna(c, v);
        c.restore();
        pintarTitulo(c, v, oscuro);
      }
    } finally {
      if (guardada && typeof estado !== "undefined") estado.vista = guardada;
    }
  }

  function pintarTitulo(c, v, oscuro) {
    const esActiva = v.i === activa;
    c.save();
    c.fillStyle = oscuro ? "rgba(0,0,0,0.45)" : "rgba(255,255,255,0.75)";
    c.fillRect(v.ox, v.oy, v.w, TITULO);
    c.font = "bold 11px system-ui, sans-serif";
    c.fillStyle = esActiva ? "#ffd35a" : (oscuro ? "#cfd1d6" : "#333");
    c.fillText(v.nombre, v.ox + 8, v.oy + 13);
    // El borde de la activa, para que se vea cuál manda.
    c.strokeStyle = esActiva ? "#ffd35a" : (oscuro ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.15)");
    c.lineWidth = esActiva ? 2 : 1;
    c.strokeRect(v.ox + 0.5, v.oy + 0.5, v.w - 1, v.h - 1);
    c.restore();
  }

  return { ventanas, repartir, la, laActiva, bajo, enTitulo, activar, maximizar,
           adoptar, encuadrarTodas, pintarTodas, proyectar, TITULO,
           navegarEn, terminarNavegacion,
           encuadrarUna: (i, puntos) => encuadrarTodas(puntos, proyectar, i),
           get activa() { return activa; }, get maximizada() { return maximizada; } };
})();

if (typeof window !== "undefined") window.Ventanas = Ventanas;
if (typeof module !== "undefined") module.exports = Ventanas;
