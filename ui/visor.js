/* El visor  ·  pensado en 3D desde la primera línea  ·  0.7.0
 *
 * Decisión de Mike (16-sep): un visor nuevo; lo demás se queda. `vista.js` era
 * 1 462 líneas hechas para mirar desde arriba, llenas de atajos que daban por
 * hecho la planta —la foto que se corre pero no gira, el pintado por lotes que
 * multiplica por la escala directo, el recorte por ventana, la rejilla—. Cada
 * atajo era una emboscada, y salían una por versión.
 *
 * Aquí no hay planta. Hay una cámara ortográfica con dos ángulos, y la planta
 * es el ángulo cero. Todo lo que se pinta —líneas del dibujo a altura cero,
 * textos, piezas sólidas— pasa por la misma proyección.
 *
 * Cuatro oficios y nada más:
 *   1. proyectar: mundo → pantalla, y pantalla → plano de trabajo;
 *   2. pintar todo en un mismo espacio, ordenado por profundidad;
 *   3. encuadrar lo que se ve, desde cualquier ángulo;
 *   4. decir qué hay bajo el cursor.
 *
 * Una sola caché: el cuadro entero. Se reusa para pan y zoom —válido en
 * cualquier ángulo porque la vista es ortográfica— y se tira al girar. Una
 * regla en vez de cinco atajos.
 *
 * Y una promesa: **el ciclo de pintado nunca muere**. Si algo truena al
 * pintar, se anota, se pinta lo que se pudo y el programa sigue vivo. Mike
 * perdió la 0.6.0 por un error de dibujo que se repetía en cada cuadro.
 *
 * Lo que no es pantalla —proyección, encuadre, orden, qué hay bajo el cursor—
 * se prueba con node, sin navegador. Es la parte que tiene lógica.
 *
 * En 0.7.0 el visor toma el mando **cuando la cámara está girada**. En planta
 * sigue el pintado de siempre, con sus cachés y sus 470 comprobaciones: el 2D
 * no corre ningún riesgo mientras el 3D madura aquí.
 */

const Visor = (() => {
  // --- la cámara -----------------------------------------------------------
  // x, y: qué punto del plano de trabajo cae en el centro de la pantalla.
  // escala: píxeles por milímetro. rx, rz: los ángulos; en cero es planta.
  const camara = { x: 0, y: 0, escala: 1, rx: 0, rz: 0 };
  let ancho = 800, alto = 600;

  function tamano(w, h) { ancho = w; alto = h; }
  function enPlanta() { return !camara.rx && !camara.rz; }

  /** Mundo → pantalla. Devuelve [px, py, profundidad]; la profundidad sirve
   *  para ordenar: más grande, más cerca de quien mira. */
  function aPantalla(x, y, z = 0) {
    const cz = Math.cos(camara.rz), sz = Math.sin(camara.rz);
    const cx = Math.cos(camara.rx), sx = Math.sin(camara.rx);
    const ux = x * cz - y * sz;
    const uy = x * sz + y * cz;
    const vy = uy * cx - z * sx;
    const prof = uy * sx + z * cx;
    return [ancho / 2 + (ux - camara.x) * camara.escala,
            alto / 2 - (vy - camara.y) * camara.escala, prof];
  }

  /** Pantalla → plano de trabajo (z = 0). Es donde vive el dibujo: el punto
   *  que sueltas es el que estabas viendo. */
  function aPlano(px, py) {
    const ux = (px - ancho / 2) / camara.escala + camara.x;
    const vy = camara.y - (py - alto / 2) / camara.escala;
    const cx = Math.cos(camara.rx);
    const uy = Math.abs(cx) < 1e-9 ? 0 : vy / cx;
    const cz = Math.cos(camara.rz), sz = Math.sin(camara.rz);
    return [ux * cz + uy * sz, -ux * sz + uy * cz];
  }

  /** Gira la cámara **sin mover de sitio lo que estás mirando**: se anota el
   *  punto del plano que está en el centro, se gira, y se vuelve a poner ahí. */
  function girar(rx, rz) {
    const centro = aPlano(ancho / 2, alto / 2);
    camara.rx = Math.max(-Math.PI / 2, Math.min(0, rx));
    camara.rz = rz;
    const q = aPantalla(centro[0], centro[1], 0);
    camara.x += (q[0] - ancho / 2) / camara.escala;
    camara.y += (alto / 2 - q[1]) / camara.escala;
    invalidar();
  }

  /** Acerca alrededor de un punto de la pantalla: lo que está bajo el cursor
   *  se queda bajo el cursor. Vale en cualquier ángulo. */
  function acercar(factor, px = ancho / 2, py = alto / 2) {
    const antes = aPlano(px, py);
    camara.escala = Math.max(1e-4, Math.min(1e4, camara.escala * factor));
    const q = aPantalla(antes[0], antes[1], 0);
    camara.x += (q[0] - px) / camara.escala;
    camara.y += (py - q[1]) / camara.escala;
  }

  function desplazar(dpx, dpy) {
    camara.x -= dpx / camara.escala;
    camara.y += dpy / camara.escala;
  }

  /** Encuadra una lista de puntos [x, y, z] desde el ángulo que haya. Se
   *  proyecta con escala 1 para medir, y de ahí sale la escala y el centro. */
  function encuadrar(puntos, margen = 0.08) {
    if (!puntos.length) return;
    const guardada = camara.escala, gx = camara.x, gy = camara.y;
    camara.escala = 1; camara.x = 0; camara.y = 0;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const p of puntos) {
      const q = aPantalla(p[0], p[1], p[2] || 0);
      if (q[0] < x0) x0 = q[0]; if (q[0] > x1) x1 = q[0];
      if (q[1] < y0) y0 = q[1]; if (q[1] > y1) y1 = q[1];
    }
    const an = Math.max(1e-6, x1 - x0), al = Math.max(1e-6, y1 - y0);
    camara.escala = Math.min(ancho / an, alto / al) * (1 - 2 * margen);
    if (!isFinite(camara.escala) || camara.escala <= 0) { camara.escala = guardada; camara.x = gx; camara.y = gy; return; }
    camara.x = 0; camara.y = 0;
    const cxp = ((x0 + x1) / 2 - ancho / 2) * camara.escala + ancho / 2;
    const cyp = ((y0 + y1) / 2 - alto / 2) * camara.escala + alto / 2;
    camara.x = (cxp - ancho / 2) / camara.escala;
    camara.y = (alto / 2 - cyp) / camara.escala;
    invalidar();
  }

  // --- la única caché ------------------------------------------------------
  let cuadro = null;
  function invalidar() { cuadro = null; }
  function cuadroSirve() {
    return !!cuadro && cuadro.rx === camara.rx && cuadro.rz === camara.rz &&
           cuadro.w === ancho && cuadro.h === alto;
  }

  // --- orden de lo que se pinta --------------------------------------------
  function porProfundidad(items, profDe) {
    return items.map((it, i) => [profDe(it), i, it]).sort((a, b) => a[0] - b[0]).map((t) => t[2]);
  }

  // --- qué hay bajo el cursor ----------------------------------------------
  function dentroDelTriangulo(q, x, y) {
    const [a, b, c] = q;
    const s = (p1, p2) => (x - p2[0]) * (p1[1] - p2[1]) - (p1[0] - p2[0]) * (y - p2[1]);
    const d1 = s(a, b), d2 = s(b, c), d3 = s(c, a);
    return !((d1 < 0 || d2 < 0 || d3 < 0) && (d1 > 0 || d2 > 0 || d3 > 0));
  }

  function triánguloBajo(tris, x, y) {
    let mejor = null, mejorProf = -Infinity;
    for (const t of tris) {
      if (!dentroDelTriangulo(t.q, x, y)) continue;
      const prof = (t.q[0][2] + t.q[1][2] + t.q[2][2]) / 3;
      if (prof > mejorProf) { mejorProf = prof; mejor = t; }
    }
    return mejor;
  }

  // --- pintar el plano girado ------------------------------------------------
  /** Pinta el dibujo y las piezas en un mismo espacio, con la proyección que
   *  se le pase (`ctx.aPX`, la misma que usa el resto del lienzo). Sin lotes,
   *  sin recorte por ventana, sin foto: cada cuadro es la verdad. Textos y
   *  cotas no van todavía: se conectan cuando esto esté firme.
   *
   *  Lo que pinta y de dónde sale:
   *    · `t.puntos`    las líneas del dibujo (polilíneas, arcos y círculos ya
   *                    aplanados por el motor);
   *    · `t.poligonos` los rellenos;
   *    · las piezas, por `Cuerpos.pintar`, ordenadas por profundidad.
   */
  function pintarPlano(c, ctx) {
    try {
      const { ancho: w, alto: h, aPX, colorDe, escala } = ctx;
      if (ctx.fondo) {
        c.clearRect(0, 0, w, h);
        c.fillStyle = ctx.lienzoColor;
        c.fillRect(0, 0, w, h);
      }
      c.lineCap = "round";
      c.lineJoin = "round";
      // El plano de trabajo, apenas insinuado: sin él no se sabe dónde está el
      // suelo cuando la pieza es lo único que hay.
      dibujarSuelo(c, ctx);
      for (const t of ctx.trazos || []) {
        if (t.clase === "imagen") continue;
        const grosor = ctx.borrador ? 1 : Math.max(1, (t.grosor || 0) * 3.78 * 0.35);
        if (t.poligonos && t.poligonos.length) {
          c.fillStyle = colorDe(t.color);
          c.beginPath();
          for (const pol of t.poligonos) {
            for (let i = 0; i < pol.length; i++) {
              const q = aPX(pol[i][0], pol[i][1], 0);
              i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]);
            }
            c.closePath();
          }
          c.fill();
        }
        const pts = t.puntos;
        if (!pts || pts.length < 2) continue;
        c.strokeStyle = colorDe(t.color);
        c.lineWidth = grosor;
        const patron = !ctx.borrador && (t.patron || []).length ? t.patron : null;
        c.setLineDash(patron ? patron.map((v) => Math.max(1, Math.abs(v) * escala * (t.escala_tl || 1))) : []);
        c.beginPath();
        for (let i = 0; i < pts.length; i++) {
          const q = aPX(pts[i][0], pts[i][1], 0);
          i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]);
        }
        c.stroke();
      }
      c.setLineDash([]);
      if (typeof Cuerpos !== "undefined") Cuerpos.pintar(c, ctx.oscuro);
    } catch (e) {
      // El ciclo de pintado nunca muere.
      console.error("[visor] el cuadro tronó, el programa sigue:", e);
    }
  }

  function dibujarSuelo(c, ctx) {
    const { aPX } = ctx;
    // Un rectángulo del tamaño de lo que hay, o de un metro si no hay nada.
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const t of ctx.trazos || []) for (const p of (t.puntos || [])) {
      if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
      if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
    }
    if (!isFinite(x0)) { x0 = -500; y0 = -500; x1 = 500; y1 = 500; }
    const mx = (x1 - x0) * 0.25 + 50, my = (y1 - y0) * 0.25 + 50;
    const esquinas = [[x0 - mx, y0 - my], [x1 + mx, y0 - my], [x1 + mx, y1 + my], [x0 - mx, y1 + my]];
    c.save();
    c.fillStyle = ctx.oscuro ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.03)";
    c.strokeStyle = ctx.oscuro ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)";
    c.lineWidth = 1;
    c.beginPath();
    esquinas.forEach((p, i) => { const q = aPX(p[0], p[1], 0); i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]); });
    c.closePath();
    c.fill();
    c.stroke();
    c.restore();
  }

  return { camara, tamano, enPlanta, aPantalla, aPlano, girar, acercar, desplazar,
           encuadrar, invalidar, cuadroSirve, porProfundidad, triánguloBajo, pintarPlano,
           _cuadro: () => cuadro, _guardarCuadro: (c) => { cuadro = c; } };
})();

if (typeof window !== "undefined") window.Visor = Visor;
if (typeof module !== "undefined") module.exports = Visor;
