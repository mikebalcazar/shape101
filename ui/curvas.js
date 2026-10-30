/* Curvas libres exactas en el navegador  ·  fase A2 del rumbo de modelado.
 *
 * El servidor manda una spline o una elipse en trozos rectos (`curva: true`),
 * y cada trozo trae la definición exacta de su curva (`def`) y el tramo de
 * parámetro que cubre (`ta`, `tb`). Ver core/geometria.py.
 *
 * Los trozos sirven para encontrar **dónde** buscar; aquí se calcula **qué**
 * hay ahí, sobre la curva de verdad: el cruce con una recta, un arco u otra
 * curva, el punto más cercano y el pie de la perpendicular. Es la regla de
 * Rhino: la malla (aquí, los trozos) es para ver y para buscar; la respuesta
 * sale de la geometría exacta. Sin esto, recortar una línea contra una spline
 * dejaba la punta hasta una décima fuera de la curva, y ese pelo es una pieza
 * que no cierra en la CNC.
 *
 * def = { t: "nurbs", p, c: [[x, y]…], k: [nudos…], w: [pesos…] | null }
 *     | { t: "elipse", c: [cx, cy], u: [ax, ay], v: [bx, by], r: [t0, t1] }
 *       (c + u·cos t + v·sin t, con t entre t0 y t1)
 */

const Curvas = (() => {
  /* --- Evaluar ---------------------------------------------------------- */
  function tramo(def, t) {
    const { p, k, c } = def;
    const n = c.length;
    if (t >= k[n]) { let s = n - 1; while (s > p && k[s] >= k[n]) s--; return s; }
    if (t <= k[p]) { let s = p; while (s < n - 1 && k[s + 1] <= k[p]) s++; return s; }
    let bajo = p, alto = n;
    while (alto - bajo > 1) { const m = (bajo + alto) >> 1; if (t < k[m]) alto = m; else bajo = m; }
    return bajo;
  }

  /* Funciones base y su primera derivada en el tramo s (Piegl y Tiller, A2.3,
   * reducida a la primera derivada). */
  function bases(def, s, t) {
    const { p, k } = def;
    const ndu = Array.from({ length: p + 1 }, () => new Array(p + 1).fill(0));
    const izq = new Array(p + 1).fill(0), der = new Array(p + 1).fill(0);
    ndu[0][0] = 1;
    for (let j = 1; j <= p; j++) {
      izq[j] = t - k[s + 1 - j];
      der[j] = k[s + j] - t;
      let guardado = 0;
      for (let r = 0; r < j; r++) {
        ndu[j][r] = der[r + 1] + izq[j - r];
        const temp = ndu[j][r] === 0 ? 0 : ndu[r][j - 1] / ndu[j][r];
        ndu[r][j] = guardado + der[r + 1] * temp;
        guardado = izq[j - r] * temp;
      }
      ndu[j][j] = guardado;
    }
    const N = [], D = [];
    for (let r = 0; r <= p; r++) {
      N.push(ndu[r][p]);
      // N'_{r,p} = p (N_{r,p-1}/(u_{i+p}-u_i) - N_{r+1,p-1}/(u_{i+p+1}-u_{i+1}))
      let d = 0;
      if (p > 0) {
        // Con nudos repetidos el denominador es cero y la base también: 0/0 vale 0.
        if (r >= 1 && ndu[p][r - 1] !== 0) d += ndu[r - 1][p - 1] / ndu[p][r - 1];
        if (r <= p - 1 && ndu[p][r] !== 0) d -= ndu[r][p - 1] / ndu[p][r];
        d *= p;
      }
      D.push(d);
    }
    return [N, D];
  }

  /** [punto, derivada] de la curva en t. */
  function evaluar(def, t) {
    if (def.t === "elipse") {
      const co = Math.cos(t), si = Math.sin(t);
      return [[def.c[0] + def.u[0] * co + def.v[0] * si, def.c[1] + def.u[1] * co + def.v[1] * si],
              [-def.u[0] * si + def.v[0] * co, -def.u[1] * si + def.v[1] * co]];
    }
    const s = tramo(def, t);
    const [N, D] = bases(def, s, t);
    const p = def.p;
    let x = 0, y = 0, w = 0, dx = 0, dy = 0, dw = 0;
    for (let r = 0; r <= p; r++) {
      const i = s - p + r;
      const wi = def.w ? def.w[i] : 1;
      const [cx, cy] = def.c[i];
      x += N[r] * wi * cx; y += N[r] * wi * cy; w += N[r] * wi;
      dx += D[r] * wi * cx; dy += D[r] * wi * cy; dw += D[r] * wi;
    }
    const X = x / w, Y = y / w;
    return [[X, Y], [(dx - dw * X) / w, (dy - dw * Y) / w]];
  }

  const punto = (def, t) => evaluar(def, t)[0];

  /* --- Raíz de una función en [a, b] con cambio de signo ---------------- */
  /* Bisección con secante: siempre converge (el intervalo nunca se sale de
   * donde está la raíz) y en curvas suaves llega en pocas vueltas. */
  function raiz(f, a, b) {
    let fa = f(a), fb = f(b);
    if (fa === 0) return a;
    if (fb === 0) return b;
    if (fa * fb > 0) return null;
    for (let i = 0; i < 100; i++) {
      let m = b - fb * (b - a) / (fb - fa);
      if (!(m > Math.min(a, b) && m < Math.max(a, b))) m = (a + b) / 2;
      // Media vuelta de bisección cada tanto para no estancarse en un lado.
      if (i % 3 === 2) m = (a + b) / 2;
      const fm = f(m);
      if (fm === 0 || Math.abs(b - a) < 1e-15 * Math.max(1, Math.abs(m))) return m;
      if (fa * fm < 0) { b = m; fb = fm; } else { a = m; fa = fm; }
    }
    return (a + b) / 2;
  }

  function dominio(def) {
    if (def.t === "elipse") return def.r || [-Infinity, Infinity];
    return [def.k[def.p], def.k[def.c.length]];
  }

  /* Dónde buscar una raíz: el tramo del trozo y, si ahí no hay cambio de
   * signo, los tramos de los vecinos. Las cuerdas de dos trozos pueden cruzar
   * una recta en un trozo mientras la curva la cruza en el de al lado. */
  function ventanas(pr) {
    const [a, b] = dominio(pr.def);
    const h = pr.tb - pr.ta;
    return [[pr.ta, pr.tb], [Math.max(a, pr.ta - h), pr.ta], [pr.tb, Math.min(b, pr.tb + h)]]
      .filter(([x, y]) => y > x);
  }

  function raizCerca(f, pr) {
    for (const [a, b] of ventanas(pr)) {
      const t = raiz(f, a, b);
      if (t !== null) return t;
    }
    return null;
  }

  /* --- Cruces exactos ----------------------------------------------------- */
  /** Cruce de la recta del segmento S con el trozo `pr`. Los extremos del
   * trozo están sobre la curva, así que si caen de lados opuestos de la recta
   * la raíz está entre ellos, sin adivinar. */
  function conRecta(S, pr) {
    const ux = S.b[0] - S.a[0], uy = S.b[1] - S.a[1];
    const f = (t) => { const q = punto(pr.def, t); return ux * (q[1] - S.a[1]) - uy * (q[0] - S.a[0]); };
    const t = raizCerca(f, pr);
    if (t === null) return null;
    const q = punto(pr.def, t);
    const L2 = ux * ux + uy * uy;
    const s = L2 < 1e-18 ? 0 : ((q[0] - S.a[0]) * ux + (q[1] - S.a[1]) * uy) / L2;
    return s < -1e-9 || s > 1 + 1e-9 ? null : q;
  }

  /** Cruce del círculo de A con el trozo; quien llama comprueba el barrido. */
  function conCirculo(A, pr) {
    const f = (t) => { const q = punto(pr.def, t); return Math.hypot(q[0] - A.c[0], q[1] - A.c[1]) - A.r; };
    const t = raizCerca(f, pr);
    return t === null ? null : punto(pr.def, t);
  }

  /** Cruce de dos trozos de curva: Newton en dos variables desde el cruce de
   * sus cuerdas. Si no converge dentro de los dos tramos, no se inventa nada:
   * se devuelve null y quien llama se queda con el cruce de las cuerdas. */
  function conCurva(A, B, q0) {
    const proyectar = (pr) => {
      const ax = pr.b[0] - pr.a[0], ay = pr.b[1] - pr.a[1];
      const L2 = ax * ax + ay * ay;
      const f = L2 < 1e-18 ? 0 : ((q0[0] - pr.a[0]) * ax + (q0[1] - pr.a[1]) * ay) / L2;
      return pr.ta + Math.max(0, Math.min(1, f)) * (pr.tb - pr.ta);
    };
    let s = proyectar(A), t = proyectar(B);
    const holgura = (pr) => (pr.tb - pr.ta);
    for (let i = 0; i < 50; i++) {
      const [P, dP] = evaluar(A.def, s), [Q, dQ] = evaluar(B.def, t);
      const rx = P[0] - Q[0], ry = P[1] - Q[1];
      if (Math.hypot(rx, ry) < 1e-11) break;
      // [dP  -dQ] [ds dt]ᵀ = -r
      const det = dP[0] * -dQ[1] - (-dQ[0]) * dP[1];
      if (Math.abs(det) < 1e-18) return null;           // tangentes: no hay cruce limpio
      const ds = (-rx * -dQ[1] - (-dQ[0]) * -ry) / det;
      const dt = (dP[0] * -ry - -rx * dP[1]) / det;
      s += ds; t += dt;
      if (s < A.ta - holgura(A) || s > A.tb + holgura(A) || t < B.ta - holgura(B) || t > B.tb + holgura(B)) return null;
    }
    const P = punto(A.def, s), Q = punto(B.def, t);
    if (Math.hypot(P[0] - Q[0], P[1] - Q[1]) > 1e-8) return null;
    if (!enDominio(A.def, s) || !enDominio(B.def, t)) return null;
    return P;
  }

  function enDominio(def, t) {
    const [a, b] = dominio(def);
    return t >= a - 1e-12 && t <= b + 1e-12;
  }

  /* --- Cercano y perpendicular ------------------------------------------- */
  /** El punto del trozo más cercano a p: sección áurea sobre |C(t)-p|² y un
   * pulido de Newton. Dentro de un trozo la distancia no tiene dos valles
   * (el trozo es casi recto: se separa de su cuerda menos que la flecha). */
  function cercanoT(pr, p) {
    const d2 = (t) => { const q = punto(pr.def, t); return (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2; };
    let a = pr.ta, b = pr.tb;
    const g = (Math.sqrt(5) - 1) / 2;
    let x1 = b - g * (b - a), x2 = a + g * (b - a), f1 = d2(x1), f2 = d2(x2);
    for (let i = 0; i < 60 && Math.abs(b - a) > 1e-14 * Math.max(1, Math.abs(a)); i++) {
      if (f1 < f2) { b = x2; x2 = x1; f2 = f1; x1 = b - g * (b - a); f1 = d2(x1); }
      else { a = x1; x1 = x2; f1 = f2; x2 = a + g * (b - a); f2 = d2(x2); }
    }
    let t = (a + b) / 2;
    // Los extremos del trozo también compiten: el mínimo puede estar en uno.
    let mejor = t, dm = d2(t);
    for (const e of [pr.ta, pr.tb]) { const de = d2(e); if (de < dm) { mejor = e; dm = de; } }
    return mejor;
  }

  const cercano = (pr, p) => punto(pr.def, cercanoT(pr, p));

  /** El pie de la perpendicular desde `base`: el punto donde (C - base)·C' = 0.
   * Null si en este trozo no hay ninguno (el pie cae en otro trozo o fuera). */
  function perpendicular(pr, base) {
    const f = (t) => { const [q, d] = evaluar(pr.def, t); return (q[0] - base[0]) * d[0] + (q[1] - base[1]) * d[1]; };
    const t = raiz(f, pr.ta, pr.tb);
    return t === null ? null : punto(pr.def, t);
  }

  return { evaluar, punto, conRecta, conCirculo, conCurva, cercano, perpendicular };
})();

if (typeof module !== "undefined") module.exports = Curvas;
