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
      // El plano de trabajo lo dice la rejilla, y nada más: hasta 0.19.0 se
      // pintaba además un rectángulo gris del tamaño del dibujo, y ése era el
      // borde que se veía en la Superior. Un suelo con orilla dice «el mundo
      // se acaba aquí», que es mentira. Mike, 20-sep: la rejilla es referencia
      // y la referencia no se acaba.
      dibujarRejilla(c, ctx);
      const textos = [];
      for (const t of ctx.trazos || []) {
        if (t.clase === "imagen") continue;
        if (t.texto !== undefined && t.altura) {
          if (t.altura * escala >= 4) textos.push(t);   // más chico no se lee
          continue;
        }
        const grosor = ctx.borrador ? 1 : Math.max(1, (t.grosor || 0) * 3.78 * 0.35);
        if (t.poligonos && t.poligonos.length) {
          c.fillStyle = colorDe(t.color);
          c.beginPath();
          for (const pol of t.poligonos) {
            for (let i = 0; i < pol.length; i++) {
              const mp = Planos.aMundo(t.plano || "XY", pol[i][0], pol[i][1], 0);
              const q = aPX(mp[0], mp[1], mp[2]);
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
          const mp = Planos.aMundo(t.plano || "XY", pts[i][0], pts[i][1], 0);
          const q = aPX(mp[0], mp[1], mp[2]);
          i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]);
        }
        c.stroke();
      }
      c.setLineDash([]);
      dibujarTextos(c, ctx, textos);
      if (typeof Cuerpos !== "undefined") Cuerpos.pintar(c, ctx.oscuro);
    } catch (e) {
      // El ciclo de pintado nunca muere.
      console.error("[visor] el cuadro tronó, el programa sigue:", e);
    }
  }

  /* --- La rejilla  ·  0.20.0 -----------------------------------------------
   *
   * Tres cosas que Mike pidió el 20-sep y que hasta la 0.19.0 no se cumplían:
   *
   * **Infinita.** No se pinta una caja alrededor del cero: se pinta lo que cabe
   * en la ventana. La cuenta va al revés —de las cuatro esquinas de la ventana
   * al plano— y salen exactamente las líneas que se ven, ni una más. Alejarse
   * no cuesta más caro porque el paso crece con el zoom. Antes era un cuadro
   * fijo de mil milímetros en el origen, y por eso se veía descentrada y con
   * orilla.
   *
   * **Sobre el plano que le toca a cada ventana.** El suelo visto desde la
   * Frontal no es una rejilla, es una raya: por eso la Frontal y la Lateral
   * salían vacías. Cada ventana pinta el plano en el que se dibuja —XY, XZ o
   * YZ— y la Perspectiva puede pintar los tres.
   *
   * **Clara.** Con los tres planos encimados en la Perspectiva, cada uno pesa
   * menos: tres rejillas al mismo tono son una maraña. Y en vez de un solo
   * tono hay dos —la fina y la de cada diez— más los ejes: así la fina puede
   * ser casi invisible y la referencia se sigue leyendo.
   */
  const BASES = {
    XY: [[1, 0, 0], [0, 1, 0]],    // el suelo    · la Superior
    XZ: [[1, 0, 0], [0, 0, 1]],    // de frente   · la Frontal
    YZ: [[0, 1, 0], [0, 0, 1]],    // de costado  · la Lateral
  };
  const MIN_PX = 14;               // más juntas que esto son ruido, no referencia
  const MAX_LINEAS = 500;          // freno duro: nunca se pintan más

  /** Un punto del plano, en coordenadas del mundo. */
  function puntoEn(plano, u, v) {
    return plano === "XY" ? [u, v, 0] : plano === "XZ" ? [u, 0, v] : [0, u, v];
  }

  /** El siguiente peldaño de la escalera 1-2-5, arriba o abajo. Trabaja por
   *  décadas, así que no se acaba: sirve para 0.2 mm y para 200 m. */
  function peldano(p, dir) {
    const d = Math.pow(10, Math.floor(Math.log10(p) + 1e-9));
    const m = p / d;
    const i = (m < 1.5 ? 0 : m < 3.5 ? 1 : 2) + dir;
    if (i > 2) return d * 10;
    if (i < 0) return d / 2;
    return d * [1, 2, 5][i];
  }

  function dibujarRejilla(c, ctx) {
    const planos = ctx.rejilla === false ? [] : (ctx.planos || ["XY"]);
    if (!planos.length) return;
    const x0 = ctx.ox || 0, x1 = x0 + ctx.ancho;
    const y0 = (ctx.oy || 0) + (ctx.titulo || 0), y1 = (ctx.oy || 0) + ctx.alto;
    // Con varios planos encimados cada uno pesa menos.
    const f = planos.length > 1 ? 0.6 : 1;
    for (const plano of planos) unPlano(c, ctx, plano, x0, y0, x1, y1, f);
  }

  function unPlano(c, ctx, plano, x0, y0, x1, y1, f) {
    const base = BASES[plano];
    if (!base) return;
    const { aPX } = ctx;
    const o = aPX(0, 0, 0);
    const a = aPX(base[0][0], base[0][1], base[0][2]);
    const b = aPX(base[1][0], base[1][1], base[1][2]);
    const ux = a[0] - o[0], uy = a[1] - o[1];
    const vx = b[0] - o[0], vy = b[1] - o[1];
    const det = ux * vy - uy * vx;
    // De canto: su rejilla sería una raya. Es el suelo visto desde la Frontal,
    // y es la razón de que ahí se pinte el XZ y no el XY.
    if (!isFinite(det) || Math.abs(det) < 1e-9) return;

    // Las cuatro esquinas de la ventana, llevadas al plano. Eso es la rejilla
    // infinita: no hay más líneas que las que caen aquí dentro.
    const inv = 1 / det;
    let u0 = Infinity, u1 = -Infinity, v0 = Infinity, v1 = -Infinity;
    for (const [px, py] of [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]) {
      const dx = px - o[0], dy = py - o[1];
      const u = (dx * vy - dy * vx) * inv, v = (dy * ux - dx * uy) * inv;
      if (u < u0) u0 = u; if (u > u1) u1 = u;
      if (v < v0) v0 = v; if (v > v1) v1 = v;
    }
    // En la Perspectiva la cuenta de arriba es aproximada —esa proyección no es
    // afín—, así que se pide de más y sobra un poco por los cuatro lados. Sobra
    // barato: lo que cae fuera lo recorta el lienzo.
    if (ctx.persp) {
      const mu = (u1 - u0) * 0.8, mv = (v1 - v0) * 0.8;
      u0 -= mu; u1 += mu; v0 -= mv; v1 += mv;
    }

    // El paso de las preferencias, subido o bajado por la escalera 1-2-5 hasta
    // que la celda quede por encima de MIN_PX. Es lo que hace que la misma
    // rejilla sirva con una pieza de 20 mm y con una nave de 80 m.
    const porPX = Math.min(Math.hypot(ux, uy), Math.hypot(vx, vy));
    if (!(porPX > 0)) return;
    let paso = Math.max(1e-6, ctx.paso || 10), g = 0;
    while (paso * porPX < MIN_PX && g++ < 60) paso = peldano(paso, +1);
    g = 0;
    while (paso * porPX > MIN_PX * 10 && g++ < 60) paso = peldano(paso, -1);
    if ((u1 - u0) / paso + (v1 - v0) / paso > MAX_LINEAS) return;

    // --- pintarla ---------------------------------------------------------
    const tinta = ctx.oscuro ? "255,255,255" : "0,0,0";
    const A_FINA = ctx.oscuro ? 0.05 : 0.055;
    const A_GORDA = ctx.oscuro ? 0.11 : 0.12;
    const A_EJE = ctx.oscuro ? 0.2 : 0.22;

    /** Las líneas del plano, en el contexto que se le dé. `dx, dy` corren el
     *  origen: sirve para pintar en un lienzo aparte del tamaño de la ventana. */
    const dibujar = (g, dx, dy) => {
      const seg = (au, av, bu, bv) => {
        const s0 = puntoEn(plano, au, av), s1 = puntoEn(plano, bu, bv);
        const a1 = aPX(s0[0], s0[1], s0[2]), b1 = aPX(s1[0], s1[1], s1[2]);
        g.moveTo(a1[0] - dx, a1[1] - dy); g.lineTo(b1[0] - dx, b1[1] - dy);
      };
      g.lineWidth = 1;
      // Dos niveles: la fina casi no se ve, la de cada diez sostiene la
      // lectura. La fina se salta los múltiplos de diez para no encimarse con
      // la gorda y acabar pintando un tono que nadie eligió.
      for (const [mult, alfa] of [[1, A_FINA], [10, A_GORDA]]) {
        const p = paso * mult;
        if (p * porPX > MIN_PX * 60) continue;     // tan separada que ya no dice nada
        g.strokeStyle = `rgba(${tinta},${alfa * f})`;
        g.beginPath();
        for (let k = Math.ceil(u0 / p); k * p <= u1; k++) {
          if (k === 0 || (mult === 1 && k % 10 === 0)) continue;
          seg(k * p, v0, k * p, v1);
        }
        for (let k = Math.ceil(v0 / p); k * p <= v1; k++) {
          if (k === 0 || (mult === 1 && k % 10 === 0)) continue;
          seg(u0, k * p, u1, k * p);
        }
        g.stroke();
      }
      // Los dos ejes del plano: sin ellos no se sabe dónde está el cero. Con
      // los tres planos encimados sólo el suelo los marca fuerte: seis rayas
      // cruzándose en el origen era justo el amontonamiento que hay que evitar.
      const mandan = !ctx.persp || plano === "XY";
      g.strokeStyle = `rgba(${tinta},${A_EJE * (mandan ? 1 : 0.45) * f})`;
      g.beginPath();
      seg(0, v0, 0, v1);
      seg(u0, 0, u1, 0);
      g.stroke();
    };

    // En las tres ventanas ortogonales no hay horizonte: se pintan todas las
    // líneas que caben y son exactas. Se acabó.
    if (!ctx.persp) { c.save(); dibujar(c, 0, 0); c.restore(); return; }

    /* En perspectiva no se puede pintar una rejilla infinita y que además se
     * lea: hacia el horizonte las líneas se juntan hasta volverse una mancha.
     * Hay que desvanecerla, y **cómo** se desvanece importa: la 0.20.0 lo hizo
     * con tres discos concéntricos, y los extremos de las líneas cortadas en
     * el borde de cada disco dibujaban tres arcos. Vistos casi de canto cerca
     * del horizonte, esos arcos se leen como tres planos espaciados — que es
     * justo lo que Mike vio y reportó.
     *
     * Así que el desvanecido no se hace a pasos sino de un golpe: la rejilla
     * se pinta en un lienzo aparte y se le aplica una máscara de degradado. No
     * queda ninguna orilla, porque no hay ningún corte: el tono baja hasta
     * cero y ya. Y el degradado va en **coordenadas del plano**, no de la
     * pantalla: sobre el suelo es un círculo, y en pantalla cae como la elipse
     * que le corresponde, así que lo que se apaga es lo lejano y no lo que
     * queda a los lados. */
    const dpr = (c.getTransform && c.getTransform().a) || 1;
    const off = lienzoAparte(ctx.ancho, ctx.alto, dpr);
    if (!off) { c.save(); dibujar(c, 0, 0); c.restore(); return; }
    const gc = off.getContext("2d");
    gc.setTransform(dpr, 0, 0, dpr, 0, 0);
    gc.clearRect(0, 0, ctx.ancho, ctx.alto);
    dibujar(gc, ctx.ox || 0, ctx.oy || 0);

    const dx = (x0 + x1) / 2 - o[0], dy = (y0 + y1) / 2 - o[1];
    const cu = (dx * vy - dy * vx) * inv, cv = (dy * ux - dx * uy) * inv;
    const radio = Math.max(u1 - u0, v1 - v0) * 0.72;
    gc.transform(ux, uy, vx, vy, o[0] - (ctx.ox || 0), o[1] - (ctx.oy || 0));
    gc.globalCompositeOperation = "destination-in";
    const grad = gc.createRadialGradient(cu, cv, 0, cu, cv, radio);
    grad.addColorStop(0, "rgba(0,0,0,1)");
    grad.addColorStop(0.55, "rgba(0,0,0,1)");
    grad.addColorStop(0.82, "rgba(0,0,0,0.45)");
    grad.addColorStop(1, "rgba(0,0,0,0)");
    gc.fillStyle = grad;
    // El cuadrado contiene al círculo, y fuera del círculo el degradado ya es
    // transparente: rellenar sólo esto es lo mismo que rellenarlo todo.
    gc.fillRect(cu - radio, cv - radio, radio * 2, radio * 2);
    gc.globalCompositeOperation = "source-over";
    gc.setTransform(1, 0, 0, 1, 0, 0);
    c.drawImage(off, ctx.ox || 0, ctx.oy || 0, ctx.ancho, ctx.alto);
  }

  /** Un lienzo aparte del tamaño de la ventana, reusado entre cuadros: crear
   *  uno por cuadro es basura que el navegador tiene que recoger sesenta veces
   *  por segundo mientras se orbita. */
  let aparte = null;
  function lienzoAparte(w, h, dpr) {
    if (typeof document === "undefined" || !(w > 0) || !(h > 0)) return null;
    const pw = Math.max(1, Math.round(w * dpr)), ph = Math.max(1, Math.round(h * dpr));
    if (!aparte) aparte = document.createElement("canvas");
    if (aparte.width !== pw || aparte.height !== ph) { aparte.width = pw; aparte.height = ph; }
    return aparte;
  }

  /** Los textos, como los pintaba el lienzo viejo: en su punto, con su altura,
   *  su ángulo y su alineación. Girada la vista se pintan de frente a quien
   *  mira (no tumbados sobre el plano): se leen, que es para lo que están. */
  function dibujarTextos(c, ctx, textos) {
    const { aPX, colorDe, escala } = ctx;
    const girada = !!(ctx.rx || ctx.rz);
    for (const t of textos) {
      const alturaPX = t.altura * escala;
      const mp = Planos.aMundo(t.plano || "XY", t.p[0], t.p[1], 0);
      const q = aPX(mp[0], mp[1], mp[2]);
      c.save();
      c.translate(q[0], q[1]);
      if (t.rotacion && !girada) c.rotate(-t.rotacion * Math.PI / 180);
      c.fillStyle = colorDe(t.color);
      c.font = `${alturaPX}px Cifras, Raleway, sans-serif`;
      c.textAlign = t.alineacion === "CENTRO" ? "center" : t.alineacion === "DER" ? "right" : "left";
      const lineas = String(t.texto).split("\n");
      for (let i = 0; i < lineas.length; i++) c.fillText(lineas[i], 0, i * alturaPX * 1.25);
      c.restore();
    }
  }

  return { camara, tamano, enPlanta, aPantalla, aPlano, girar, acercar, desplazar,
           encuadrar, invalidar, cuadroSirve, porProfundidad, triánguloBajo, pintarPlano,
           _cuadro: () => cuadro, _guardarCuadro: (c) => { cuadro = c; } };
})();

if (typeof window !== "undefined") window.Visor = Visor;
if (typeof module !== "undefined") module.exports = Visor;
