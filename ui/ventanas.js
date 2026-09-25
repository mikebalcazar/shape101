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
    // `mira`: el punto del mundo al que está anclada la perspectiva y
    // alrededor del que se orbita. Lo fija Extents; panear no lo mueve.
    { nombre: "Perspectiva", plano: "XY", rx: -60 * GRADO,  rz: 45 * GRADO, persp: true, foco: 1400, mira: [0, 0, 0] },
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
  let adoptado = false;
  function adoptar(puntos) {
    // La bandera es propia a propósito. Antes se preguntaba si `estado.vista`
    // era ya la ventana activa, y eso es falso a mitad de una navegación: con
    // el botón central sobre otra ventana, `estado.vista` apunta a la de abajo
    // del cursor. Adoptar se creía sin estrenar y secuestraba el gesto —volvía
    // la activa a la Superior y reencuadraba las cuatro—. Una bandera de «ya
    // pasó» no se deduce de un estado que el usuario mueve.
    if (typeof estado === "undefined" || adoptado) return false;
    adoptado = true;
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
    } else {
      // Documento vacío: las cuatro miran al cero, que es el único punto que
      // significa algo. Hasta la 0.19.0 la Superior heredaba la cámara de
      // siempre y las otras tres nacían con el origen **en su esquina de
      // arriba a la izquierda** — no era sólo feo: una pieza levantada después
      // caía fuera de la Perspectiva, no se le podía picar una cara, y JALAR y
      // CRECER se quedaban sin cara que mover. Mike lo reportó como «el grid
      // está descentrado»; era el mismo defecto.
      for (const v of ventanas) v.escala = ventanas[0].escala || 1;
      centrarEnOrigen();
    }
    return true;
  }

  /** Pone el origen del mundo en el centro de cada ventana, sin tocar el zoom. */
  function centrarEnOrigen() {
    for (const v of ventanas) {
      if (v.w <= 0 || v.h <= 0) continue;
      v.x = -v.w / 2 / v.escala;
      v.y = (v.h + TITULO) / 2 / v.escala;
      if (v.persp) v.mira = [0, 0, 0];
    }
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
      // La Perspectiva se ancla al centro de lo encuadrado: ahí queda el
      // punto de fuga y el pivote de orbitar, hasta el siguiente Extents.
      if (v.persp) v.mira = centroDe(puntos);
    }
  }

  /** El centro de la caja de unos puntos [x, y, z]. */
  function centroDe(puntos) {
    let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
    for (const p of puntos) {
      const z = p[2] || 0;
      if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
      if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
      if (z < z0) z0 = z; if (z > z1) z1 = z;
    }
    return isFinite(x0) ? [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2] : [0, 0, 0];
  }

  /* --- La rejilla, ventana por ventana  ·  0.20.0 --------------------------
   *
   * Mike, 20-sep: «hay que poder prender y apagar el grid por ventana y en la
   * perspectiva por plano». El interruptor de abajo (REJILLA, F7) manda sobre
   * las cuatro: apagarlo las apaga todas **sin perder** lo que cada una tenía
   * prendido, y volver a prenderlo las devuelve como estaban.
   */
  const PLANOS = ["XY", "XZ", "YZ"];

  function prefs() { return (typeof estado !== "undefined" && estado.prefs) || {}; }

  /** Qué planos de rejilla le tocan a una ventana. Vacío: sin rejilla. */
  function planosRejilla(v) {
    const p = prefs();
    if (p.rejilla === false) return [];
    if ((p.rejilla_ventanas || {})[v.nombre] === false) return [];
    if (!v.persp) return [v.plano];
    const pl = p.rejilla_planos || {};
    return PLANOS.filter((k) => pl[k] !== false);
  }

  /* Los interruptores viven en la barra del título de cada ventana, a la
   * derecha. En las tres ortogonales es uno —esa ventana tiene un solo plano—;
   * en la Perspectiva son tres, uno por plano, porque ahí los tres se ven a la
   * vez y cada uno estorba de distinta manera. */
  const ALTO_B = 13, HUECO = 3, MARGEN = 8;

  function botonesDe(v) {
    if (v.w < 130 || v.h <= 0) return [];        // ventana angosta: sin adornos
    const p = prefs();
    const y = v.oy + Math.floor((TITULO - ALTO_B) / 2);
    const viva = p.rejilla !== false && (p.rejilla_ventanas || {})[v.nombre] !== false;
    if (!v.persp) {
      const w = 16;
      return [{ x: v.ox + v.w - MARGEN - w, y, w, h: ALTO_B,
                icono: true, on: viva, que: "ventana", ventana: v.i }];
    }
    const w = 20, total = PLANOS.length * w + (PLANOS.length - 1) * HUECO;
    const pl = p.rejilla_planos || {};
    return PLANOS.map((k, i) => ({
      x: v.ox + v.w - MARGEN - total + i * (w + HUECO), y, w, h: ALTO_B,
      et: k, on: viva && pl[k] !== false, que: "plano", plano: k, ventana: v.i,
    }));
  }

  function pintarBoton(c, b, oscuro) {
    const tinta = oscuro ? "255,255,255" : "0,0,0";
    c.save();
    c.fillStyle = `rgba(${tinta},${b.on ? 0.13 : 0.04})`;
    c.fillRect(b.x, b.y, b.w, b.h);
    c.strokeStyle = `rgba(${tinta},${b.on ? 0.32 : 0.13})`;
    c.lineWidth = 1;
    c.strokeRect(b.x + 0.5, b.y + 0.5, b.w - 1, b.h - 1);
    if (b.icono) {
      // Una cuadrícula de 3×3: a trece píxeles se lee como rejilla.
      c.strokeStyle = `rgba(${tinta},${b.on ? 0.6 : 0.22})`;
      c.beginPath();
      for (let i = 1; i <= 2; i++) {
        const fx = b.x + Math.round(b.w * i / 3) + 0.5;
        const fy = b.y + Math.round(b.h * i / 3) + 0.5;
        c.moveTo(fx, b.y + 2); c.lineTo(fx, b.y + b.h - 2);
        c.moveTo(b.x + 2, fy); c.lineTo(b.x + b.w - 2, fy);
      }
      c.stroke();
    } else {
      c.font = "bold 8px system-ui, sans-serif";
      c.textAlign = "center";
      c.textBaseline = "middle";
      c.fillStyle = `rgba(${tinta},${b.on ? 0.7 : 0.28})`;
      c.fillText(b.et, b.x + b.w / 2, b.y + b.h / 2 + 0.5);
    }
    c.restore();
  }

  /** ¿Se picó un interruptor de rejilla? Devuelve cuál, o null. */
  function botonEn(px, py) {
    for (const v of ventanas) {
      if (v.w <= 0 || v.h <= 0) continue;
      if (px < v.ox || px >= v.ox + v.w || py < v.oy || py >= v.oy + TITULO) continue;
      for (const b of botonesDe(v)) {
        if (px >= b.x && px < b.x + b.w && py >= b.y && py < b.y + b.h) return b;
      }
    }
    return null;
  }

  /** Cambia el interruptor que se picó y devuelve lo que hay que guardar.
   *
   *  Si el interruptor general estaba apagado, picar uno de éstos lo prende:
   *  pedir una rejilla y que no pase nada porque hay otro apagado más arriba
   *  es de las cosas que hacen que uno crea que el programa está roto. */
  function alternarRejilla(b) {
    if (typeof estado === "undefined") return {};
    const p = estado.prefs || (estado.prefs = {});
    const patch = {};
    if (p.rejilla === false) { p.rejilla = true; patch.rejilla = true; }
    if (b.que === "plano") {
      const pl = { ...(p.rejilla_planos || {}) };
      pl[b.plano] = !(pl[b.plano] !== false);
      p.rejilla_planos = pl; patch.rejilla_planos = pl;
    } else {
      const vv = { ...(p.rejilla_ventanas || {}) };
      const n = ventanas[b.ventana].nombre;
      vv[n] = !(vv[n] !== false);
      p.rejilla_ventanas = vv; patch.rejilla_ventanas = vv;
    }
    return patch;
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
    for (const b of botonesDe(v)) pintarBoton(c, b, oscuro);
  }

  return { ventanas, repartir, la, laActiva, bajo, enTitulo, activar, maximizar,
           adoptar, encuadrarTodas, pintarTodas, proyectar, TITULO,
           navegarEn, terminarNavegacion,
           planosRejilla, botonEn, alternarRejilla, centrarEnOrigen,
           encuadrarUna: (i, puntos) => encuadrarTodas(puntos, proyectar, i),
           get activa() { return activa; }, get maximizada() { return maximizada; } };
})();

if (typeof window !== "undefined") window.Ventanas = Ventanas;
if (typeof module !== "undefined") module.exports = Ventanas;