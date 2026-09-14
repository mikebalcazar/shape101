/* Referencias a objetos  ·  feature 13.
 *
 * Trabaja sobre las primitivas exactas que manda el servidor (`core/geometria.py`),
 * no sobre la teselación del lienzo. El punto medio de un arco teselado no es
 * el punto medio del arco; en un plano que va a la CNC esa diferencia es una
 * pieza mal cortada.
 *
 * El orden de prioridad es el de AutoCAD y no es capricho: entre un extremo y
 * un cercano que caen a la misma distancia del cursor, el usuario quiso el
 * extremo. El cercano va hasta el final justamente porque siempre acierta —
 * si compitiera de tú a tú, taparía a todos los demás.
 */

const PRIORIDAD = ["extremo", "interseccion", "medio", "centro", "cuadrante",
                   "nodo", "perpendicular", "proyeccion", "cercano"];

const Osnap = (() => {
  const TAU = Math.PI * 2;
  const rad = (g) => g * Math.PI / 180;
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

  /* --- Utilidades de arco ---------------------------------------------- */
  const completo = (pr) => Math.abs((pr.a1 - pr.a0 + 360) % 360) < 1e-9 || pr.a1 === 360;

  function barrido(pr) {
    if (completo(pr)) return 360;
    return ((pr.a1 - pr.a0) % 360 + 360) % 360;
  }

  function enArco(pr, angGrados) {
    if (completo(pr)) return true;
    const d = ((angGrados - pr.a0) % 360 + 360) % 360;
    return d <= barrido(pr) + 1e-9;
  }

  const puntoArco = (pr, angGrados) => [
    pr.c[0] + pr.r * Math.cos(rad(angGrados)),
    pr.c[1] + pr.r * Math.sin(rad(angGrados)),
  ];

  /* --- Cajas para descartar rápido ------------------------------------- */
  function caja(pr) {
    if (pr.tipo === "seg") {
      return [Math.min(pr.a[0], pr.b[0]), Math.min(pr.a[1], pr.b[1]),
              Math.max(pr.a[0], pr.b[0]), Math.max(pr.a[1], pr.b[1])];
    }
    if (pr.tipo === "arco") {
      return [pr.c[0] - pr.r, pr.c[1] - pr.r, pr.c[0] + pr.r, pr.c[1] + pr.r];
    }
    return [pr.p[0], pr.p[1], pr.p[0], pr.p[1]];
  }

  function cerca(pr, p, tol) {
    const [x0, y0, x1, y1] = caja(pr);
    return p[0] >= x0 - tol && p[0] <= x1 + tol && p[1] >= y0 - tol && p[1] <= y1 + tol;
  }
  /** Distancia del punto a la caja de la primitiva (0 si cae dentro). */
  function distPrim(pr, p) {
    const [x0, y0, x1, y1] = caja(pr);
    const dx = p[0] < x0 ? x0 - p[0] : p[0] > x1 ? p[0] - x1 : 0;
    const dy = p[1] < y0 ? y0 - p[1] : p[1] > y1 ? p[1] - y1 : 0;
    return dx * dx + dy * dy;
  }

  /* --- Punto más cercano sobre una primitiva --------------------------- */
  function sobreSeg(pr, p) {
    const [ax, ay] = pr.a, [bx, by] = pr.b;
    const dx = bx - ax, dy = by - ay;
    const largo2 = dx * dx + dy * dy;
    if (largo2 < 1e-18) return [ax, ay];
    let t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / largo2;
    t = Math.max(0, Math.min(1, t));
    return [ax + t * dx, ay + t * dy];
  }

  function sobreArco(pr, p) {
    const ang = Math.atan2(p[1] - pr.c[1], p[0] - pr.c[0]) * 180 / Math.PI;
    if (enArco(pr, ang)) return puntoArco(pr, ang);
    // fuera del barrido: gana el extremo más próximo
    const e0 = puntoArco(pr, pr.a0), e1 = puntoArco(pr, pr.a1);
    return dist(p, e0) <= dist(p, e1) ? e0 : e1;
  }

  const sobre = (pr, p) => pr.tipo === "seg" ? sobreSeg(pr, p)
    : pr.tipo === "arco" ? sobreArco(pr, p) : pr.p;

  /* --- Intersecciones --------------------------------------------------- */
  function segSeg(A, B) {
    const [x1, y1] = A.a, [x2, y2] = A.b, [x3, y3] = B.a, [x4, y4] = B.b;
    const den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
    if (Math.abs(den) < 1e-12) return [];       // paralelas o coincidentes
    const t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den;
    const u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den;
    if (t < -1e-9 || t > 1 + 1e-9 || u < -1e-9 || u > 1 + 1e-9) return [];
    return [[x1 + t * (x2 - x1), y1 + t * (y2 - y1)]];
  }

  function segArco(S, A) {
    const [x1, y1] = S.a, [x2, y2] = S.b;
    const dx = x2 - x1, dy = y2 - y1;
    const fx = x1 - A.c[0], fy = y1 - A.c[1];
    const a = dx * dx + dy * dy;
    const b = 2 * (fx * dx + fy * dy);
    const c = fx * fx + fy * fy - A.r * A.r;
    const disc = b * b - 4 * a * c;
    if (disc < 0 || a < 1e-18) return [];
    const raiz = Math.sqrt(disc);
    const salida = [];
    for (const t of [(-b - raiz) / (2 * a), (-b + raiz) / (2 * a)]) {
      if (t < -1e-9 || t > 1 + 1e-9) continue;
      const p = [x1 + t * dx, y1 + t * dy];
      const ang = Math.atan2(p[1] - A.c[1], p[0] - A.c[0]) * 180 / Math.PI;
      if (enArco(A, ang)) salida.push(p);
    }
    return salida;
  }

  function arcoArco(A, B) {
    const d = dist(A.c, B.c);
    if (d < 1e-12 || d > A.r + B.r + 1e-9 || d < Math.abs(A.r - B.r) - 1e-9) return [];
    const a = (A.r * A.r - B.r * B.r + d * d) / (2 * d);
    const h2 = A.r * A.r - a * a;
    if (h2 < 0) return [];
    const h = Math.sqrt(h2);
    const mx = A.c[0] + a * (B.c[0] - A.c[0]) / d;
    const my = A.c[1] + a * (B.c[1] - A.c[1]) / d;
    const rx = -(B.c[1] - A.c[1]) * (h / d), ry = (B.c[0] - A.c[0]) * (h / d);
    const salida = [];
    for (const p of [[mx + rx, my + ry], [mx - rx, my - ry]]) {
      const angA = Math.atan2(p[1] - A.c[1], p[0] - A.c[0]) * 180 / Math.PI;
      const angB = Math.atan2(p[1] - B.c[1], p[0] - B.c[0]) * 180 / Math.PI;
      if (enArco(A, angA) && enArco(B, angB)) salida.push(p);
    }
    return salida;
  }

  function interseccion(A, B) {
    if (A.tipo === "punto" || B.tipo === "punto") return [];
    if (A.tipo === "seg" && B.tipo === "seg") return segSeg(A, B);
    if (A.tipo === "seg" && B.tipo === "arco") return segArco(A, B);
    if (A.tipo === "arco" && B.tipo === "seg") return segArco(B, A);
    return arcoArco(A, B);
  }

  /* --- Perpendicular ---------------------------------------------------- */
  function perpendicular(pr, base) {
    if (pr.tipo === "seg") {
      const [ax, ay] = pr.a, [bx, by] = pr.b;
      const dx = bx - ax, dy = by - ay;
      const largo2 = dx * dx + dy * dy;
      if (largo2 < 1e-18) return null;
      const t = ((base[0] - ax) * dx + (base[1] - ay) * dy) / largo2;
      if (t < -1e-9 || t > 1 + 1e-9) return null;     // el pie cae fuera
      return [ax + t * dx, ay + t * dy];
    }
    if (pr.tipo === "arco") {
      // el pie de la perpendicular a un círculo está en la línea centro-base
      const d = dist(base, pr.c);
      if (d < 1e-12) return null;
      const ang = Math.atan2(base[1] - pr.c[1], base[0] - pr.c[0]) * 180 / Math.PI;
      return enArco(pr, ang) ? puntoArco(pr, ang) : null;
    }
    return null;
  }

  /* --- Proyección perpendicular  ·  0.20.0 --------------------------------
   *
   * Mike (9-sep-2026): «proyectar el cursor sobre la perpendicular a una
   * entidad, y sobre la intersección de esa perpendicular con otra línea».
   *
   * Desde el punto anterior (`base`) se baja la perpendicular a la **recta**
   * de la entidad —no sólo al tramo: el pie puede caer más allá de donde la
   * línea termina— y esa perpendicular es una línea de rastreo. Sobre ella se
   * ofrecen dos puntos: el pie mismo, y donde cruza con otra entidad cercana.
   * En pantalla sale punteada desde la base (ver pintarReferencia), como el
   * rastreo de AutoCAD, para que se entienda de dónde viene el punto. */
  function pieEnRecta(pr, base) {
    if (pr.tipo !== "seg") return null;
    const [ax, ay] = pr.a, [bx, by] = pr.b;
    const dx = bx - ax, dy = by - ay;
    const largo2 = dx * dx + dy * dy;
    if (largo2 < 1e-18) return null;
    const t = ((base[0] - ax) * dx + (base[1] - ay) * dy) / largo2;
    return { p: [ax + t * dx, ay + t * dy], t };
  }

  function proyecciones(amplias, cercanas, p, base, tol) {
    const out = [];
    for (const pr of amplias) {
      if (pr.tipo !== "seg" || pr.aprox || pr.cota) continue;
      const pie = pieEnRecta(pr, base);
      if (!pie) continue;
      const v = [pie.p[0] - base[0], pie.p[1] - base[1]];
      const L = Math.hypot(v[0], v[1]);
      if (L < 1e-9) continue;            // la base está sobre la recta: no hay perpendicular
      const u = [v[0] / L, v[1] / L];
      // ¿El cursor va sobre esa perpendicular? Su proyección es un candidato:
      // así se puede seguir la perpendicular sin que haya nada debajo.
      const s = (p[0] - base[0]) * u[0] + (p[1] - base[1]) * u[1];
      const sobreRayo = [base[0] + u[0] * s, base[1] + u[1] * s];
      const lejos = dist(sobreRayo, p);
      if (lejos > tol) continue;         // el cursor no va por la perpendicular
      // El pie mismo (fuera del tramo; dentro ya lo da «perpendicular»).
      if (pie.t < -1e-9 || pie.t > 1 + 1e-9) out.push({ modo: "proyeccion", p: pie.p, id: pr.id, desde: base, pie: true });
      // Y donde la perpendicular cruza lo que hay cerca del cursor.
      const rayo = { tipo: "seg", a: [base[0] - u[0] * 1e6, base[1] - u[1] * 1e6],
                     b: [base[0] + u[0] * 1e6, base[1] + u[1] * 1e6] };
      for (const otra of cercanas) {
        if (otra === pr || otra.id === pr.id || otra.tipo === "punto" || otra.aprox || otra.cota) continue;
        for (const q of interseccion(rayo, otra)) {
          if (dist(q, p) <= tol) out.push({ modo: "proyeccion", p: q, id: otra.id, desde: base, pie: true });
        }
      }
      out.push({ modo: "proyeccion", p: sobreRayo, id: pr.id, desde: base, pie: false });
    }
    return out;
  }

  /* --- Búsqueda --------------------------------------------------------- */
  function candidatos(pr, tol, p, base, modos) {
    const out = [];
    const mete = (modo, punto) => { if (punto && modos[modo]) out.push({ modo, p: punto, id: pr.id }); };

    if (pr.tipo === "punto") {
      mete("nodo", pr.p);
      if (pr.clase === "centro") mete("centro", pr.p);
      return out;
    }
    if (pr.tipo === "seg") {
      mete("extremo", pr.a);
      mete("extremo", pr.b);
      mete("medio", [(pr.a[0] + pr.b[0]) / 2, (pr.a[1] + pr.b[1]) / 2]);
    } else if (pr.tipo === "arco") {
      mete("centro", pr.c);
      if (!completo(pr)) {
        mete("extremo", puntoArco(pr, pr.a0));
        mete("extremo", puntoArco(pr, pr.a1));
        mete("medio", puntoArco(pr, pr.a0 + barrido(pr) / 2));
      }
      for (const q of [0, 90, 180, 270]) {
        if (enArco(pr, q)) mete("cuadrante", puntoArco(pr, q));
      }
    }
    if (base) mete("perpendicular", perpendicular(pr, base));
    mete("cercano", sobre(pr, p));
    return out;
  }

  /** Busca la mejor referencia bajo el punto `p` (en mm).
   *  `base` es el punto anterior de la herramienta, si lo hay: sin él no tiene
   *  sentido una perpendicular.
   *  `excluir` es un Set de ids que no se miran. Se usa al jalar un grip: una
   *  línea no se engancha a sí misma —el extremo que se está moviendo está
   *  justo debajo del cursor y ganaría siempre—, y sin esto arrastrar un
   *  extremo para pegarlo a otro es imposible. */
  function buscar(p, base, excluir, opciones = null) {
    const prefs = estado.prefs;
    if (!prefs || !prefs.osnap) return null;
    const modos = prefs.osnap_modos || {};
    const tol = (prefs.osnap_apertura || 14) / estado.vista.escala;
    // `opciones.cotas`: se admiten las líneas de cota de otras cotas (sólo al
    // colocar una cota, ver ui/cotas.js). El resto del tiempo se ignoran.
    const conCotas = !!(opciones && opciones.cotas);

    const cercanas = [];
    /* **Por el índice, no recorriendo el plano.** Esto recorría las 185 000
     * primitivas del plano de Mondelez en **cada movimiento del ratón**: 9 a
     * 16 ms por cuadro, o sea el cuadro entero. Es lo que se sentía como
     * «torpe»: el ratón iba medio cuadro atrás. `Indice.cerca` devuelve sólo
     * lo que cae en las celdas de alrededor —unas decenas— y es la misma
     * rejilla que ya usa la selección.
     *
     * Sobre una hoja se puede uno enganchar además a lo que se ve por las
     * ventanas: sin eso, una cota puesta en el plano no toca la esquina del
     * mueble y no mide el mueble — mide donde atinó el ratón. Ésas son pocas
     * (van recortadas a la ventana) y se recorren tal cual. */
    const candidatas = Indice.cerca(p, tol);
    if (estado.modo === "papel" && estado.geometriaVentana.length) {
      for (const pr of estado.geometriaVentana) candidatas.push(pr);
    }
    for (const pr of candidatas) {
      // Las primitivas `aprox` son la tesela de algo ajeno que no modelamos
      // (una cota, una spline de otro programa). Sirven para picarlo y
      // seleccionarlo; **no** para engancharse a ellas. El punto medio de una
      // raya teselada no es el punto medio de la curva, y ese pelo de
      // diferencia es una pieza mal cortada.
      if (pr.aprox) continue;
      if (pr.cota && !conCotas) continue;
      if (excluir && excluir.has(pr.id)) continue;
      if (cerca(pr, p, tol)) cercanas.push(pr);
      if (cercanas.length > 400) break;   // en un nudo muy denso, con eso basta
    }

    let posibles = [];
    // La proyección perpendicular mira más lejos que la apertura: la entidad
    // a la que se baja la perpendicular puede no estar bajo el cursor.
    if (modos.proyeccion && base) {
      const amplias = [];
      for (const pr of Indice.cerca(p, tol * 12)) {
        if (pr.tipo !== "seg" || pr.aprox || pr.cota) continue;
        if (excluir && excluir.has(pr.id)) continue;
        if (cerca(pr, p, tol * 12)) amplias.push(pr);
        if (amplias.length > 80) break;
      }
      posibles.push(...proyecciones(amplias, cercanas, p, base, tol));
    }
    if (!cercanas.length && !posibles.length) return null;

    for (const pr of cercanas) posibles.push(...candidatos(pr, tol, p, base, modos));

    if (modos.interseccion) {
      // Las intersecciones son de a pares: con 400 cercanas son 80 000 cruces
      // por movimiento del ratón. En un nudo denso bastan las 60 más cercanas
      // al cursor — las demás no van a ganar de todos modos.
      if (cercanas.length > 60) {
        cercanas.sort((a, b) => distPrim(a, p) - distPrim(b, p));
        cercanas.length = 60;
      }
      for (let i = 0; i < cercanas.length; i++) {
        for (let j = i + 1; j < cercanas.length; j++) {
          if (cercanas[i].id === cercanas[j].id) continue;   // consigo misma, no
          for (const q of interseccion(cercanas[i], cercanas[j])) {
            posibles.push({ modo: "interseccion", p: q, id: cercanas[i].id });
          }
        }
      }
    }

    let mejor = null;
    for (const c of posibles) {
      const d = dist(c.p, p);
      if (d > tol) continue;
      // Sobre la perpendicular, un pie o un cruce vale más que «seguir la
      // línea» a secas, que siempre es lo más cercano al cursor.
      const rango = PRIORIDAD.indexOf(c.modo) + (c.modo === "proyeccion" && !c.pie ? 0.5 : 0);
      if (!mejor || rango < mejor.rango || (rango === mejor.rango && d < mejor.d)) {
        mejor = { ...c, d, rango };
      }
    }
    return mejor;
  }

  return { buscar, sobre, interseccion, perpendicular, caja };
})();
