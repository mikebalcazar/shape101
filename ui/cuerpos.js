/* Los cuerpos 3D, pintados en el lienzo de siempre  ·  0.6.0
 *
 * Hasta la 0.5.0 el 3D vivía en un lienzo aparte, encima del dibujo. Mike lo
 * dijo mejor que yo: *«desde el dibujo 2D ya es un espacio 3D, sólo estamos
 * dibujando sobre el plano de la vista superior; pero al extruir aparece un 3D
 * flotando, despegado del plano»*. Tenía razón: era un visor, no un espacio.
 *
 * Ahora no hay dos lienzos. Los cuerpos se pintan dentro de `dibujarPlano`,
 * con la misma cámara y las mismas dos funciones de conversión que las líneas
 * (`window.aPX`). La pieza se para sobre el contorno del que salió porque
 * están en el mismo sitio, no porque alguien los haya alineado.
 *
 * El orden de pintado es el del pintor: triángulos de lejos a cerca. Con las
 * piezas de un mueble —decenas de caras— alcanza de sobra y no hace falta
 * WebGL ni una biblioteca de 1.2 MB.
 */

const Cuerpos = (() => {
  const mallas = new Map();        // id → lo que devolvió el motor
  let pidiendo = false;
  let otraVez = false;           // llegó otra petición mientras ésta iba en camino

  // Colores de la madera. Tres tonos según a dónde mire la cara: sin eso, un
  // sólido se ve como una mancha y no se entiende la forma.
  const CLARO = [214, 180, 133], MEDIO = [176, 143, 100], OSCURO = [128, 101, 68];
  const SENALADA = [255, 211, 90];

  async function pedir(url, cuerpo) {
    const r = await fetch(url, cuerpo === undefined ? undefined
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || j.error || `${r.status} en ${url}`);
    return j;
  }

  /** Trae del motor las piezas del dibujo. Se llama cuando el documento cambió,
   *  no en cada cuadro: la malla sólo cambia si cambió la pieza. */
  async function refrescar() {
    // Si ya hay una pregunta en vuelo, no se hacen dos: se apunta que al
    // terminar hay que volver a preguntar. Devolverse sin más —como hasta la
    // 0.12.1— perdía la petición buena: abrir un archivo justo mientras la
    // anterior contestaba dejaba las piezas del dibujo nuevo sin pedir.
    if (pidiendo) { otraVez = true; return; }
    pidiendo = true;
    try {
      const { ids } = await pedir("/api/cuerpo/lista");
      for (const id of ids) {
        if (!mallas.has(id)) mallas.set(id, await pedir(`/api/cuerpo/${id}/malla`));
      }
      for (const id of [...mallas.keys()]) if (!ids.includes(id)) mallas.delete(id);
    } catch (e) {
      // Que no haya piezas, o que el motor todavía no conteste, no es un error
      // que deba tapar el dibujo: se sigue pintando el 2D como siempre.
    } finally {
      pidiendo = false;
    }
    if (window.invalidarPlano) window.invalidarPlano();
    if (window.pintar) window.pintar();
    if (otraVez) { otraVez = false; await refrescar(); }
  }

  /** Vuelve a traer una pieza concreta: después de jalarle una cara o de mover
   *  un punto. */
  async function refrescarUna(id) {
    try {
      mallas.set(id, await pedir(`/api/cuerpo/${id}/malla`));
    } catch (e) { /* se queda la anterior, que es mejor que nada */ }
    if (window.invalidarPlano) window.invalidarPlano();
    if (window.pintar) window.pintar();
  }

  function olvidar() { mallas.clear(); }

  // --- pintar --------------------------------------------------------------
  const LUZ = [0.4, -0.5, 0.75];
  let senalada = null;             // {id, cara}

  function normal(P) {
    const [A, B, C] = P;
    const u = [B[0] - A[0], B[1] - A[1], B[2] - A[2]];
    const w = [C[0] - A[0], C[1] - A[1], C[2] - A[2]];
    const n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const l = Math.hypot(n[0], n[1], n[2]) || 1;
    return [n[0] / l, n[1] / l, n[2] / l];
  }

  /** Las aristas de una cara que son borde de la cara —las que sólo tiene un
   *  triángulo— y no costura entre dos triángulos. Con eso el renderizado
   *  dibuja el contorno de cada cara justo después de rellenarla, y las caras
   *  de adelante tapan las aristas de atrás sin calcular nada más. */
  const clave = (a, b) => a < b ? a * 65536 + b : b * 65536 + a;
  function bordesDe(cara) {
    if (cara._bordes) return cara._bordes;
    const veces = new Map();
    const ix = cara.i;
    for (let k = 0; k < ix.length; k += 3) {
      for (const [a, b] of [[ix[k], ix[k + 1]], [ix[k + 1], ix[k + 2]], [ix[k + 2], ix[k]]]) {
        const c = clave(a, b); veces.set(c, (veces.get(c) || 0) + 1);
      }
    }
    cara._bordes = new Set([...veces].filter(([, n]) => n === 1).map(([c]) => c));
    return cara._bordes;
  }

  /** Todos los triángulos de todas las piezas, ya proyectados y ordenados de
   *  lejos a cerca. La profundidad sale de la cámara: con la vista en planta
   *  todos valen lo mismo, y entonces manda la altura, que es lo que se
   *  espera mirando desde arriba. */
  function triangulos() {
    const v = estado.vista;
    const cx = Math.cos(v.rx), sx = Math.sin(v.rx);
    const cz = Math.cos(v.rz), sz = Math.sin(v.rz);
    const tris = [];
    for (const [id, m] of mallas) {
      for (const cara of m.caras || []) {
        const vs = cara.v, ix = cara.i;
        const borde = bordesDe(cara);
        for (let k = 0; k < ix.length; k += 3) {
          const a = ix[k] * 3, b = ix[k + 1] * 3, d = ix[k + 2] * 3;
          const P = [[vs[a], vs[a + 1], vs[a + 2]],
                     [vs[b], vs[b + 1], vs[b + 2]],
                     [vs[d], vs[d + 1], vs[d + 2]]];
          let prof = 0;
          for (const p of P) prof += (p[0] * sz + p[1] * cz) * sx + p[2] * cx;
          tris.push({ id, cara: cara.nombre, P, q: P.map((p) => window.aPX(p[0], p[1], p[2])), prof: prof / 3,
                      borde: [borde.has(clave(ix[k], ix[k + 1])), borde.has(clave(ix[k + 1], ix[k + 2])), borde.has(clave(ix[k + 2], ix[k]))] });
        }
      }
    }
    tris.sort((a, b) => a.prof - b.prof);
    return tris;
  }

  function color(t, oscuro) {
    const n = normal(t.P);
    const luz = Math.abs(n[0] * LUZ[0] + n[1] * LUZ[1] + n[2] * LUZ[2]);
    const tono = (oscuro ? 0.35 : 0.5) + 0.65 * luz;
    const base = senalada && senalada.id === t.id && senalada.cara === t.cara ? SENALADA
      : Math.abs(n[2]) > 0.7 ? CLARO : Math.abs(n[0]) > 0.7 ? MEDIO : OSCURO;
    return `rgb(${Math.min(255, Math.round(base[0] * tono))},${Math.min(255, Math.round(base[1] * tono))},${Math.min(255, Math.round(base[2] * tono))})`;
  }

  // --- estilos de vista  ·  0.21.8 -----------------------------------------
  // Mike, 25-sep: «quiero poder tener un estilo de vista, aparte de la básica,
  // de wireframe ghosteado y otro de renderizado. Que se vean los sólidos con
  // materiales y mejor rasterizados».
  //   basico      · el de siempre: tres tonos de madera y todas las aristas.
  //   alambrico   · fantasma: caras translúcidas, se ven las aristas de atrás.
  //   renderizado · luz principal + luz de relleno + brillo, con el color de
  //                 la capa como material (blanco/negro = madera).
  const ESTILOS = ["basico", "alambrico", "renderizado"];
  function estilo() {
    const e = (typeof estado !== "undefined" && estado.prefs && estado.prefs.estilo_3d) || "basico";
    return ESTILOS.includes(e) ? e : "basico";
  }

  function materialDe(m) {
    const h = String(m.color || "").replace("#", "");
    if (/^[0-9a-fA-F]{6}$/.test(h)) {
      const rgb = [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
      const gris = Math.max(...rgb) - Math.min(...rgb) < 12;
      if (!gris) return rgb;                         // color de capa: ése es el material
      if (Math.max(...rgb) < 235 && Math.max(...rgb) > 30) return rgb;   // gris de verdad
    }
    return CLARO;                                   // sin color: madera
  }

  const _norm = (v) => { const l = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0] / l, v[1] / l, v[2] / l]; };
  const _dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

  /** Hacia dónde está la cámara, en el mundo: el eje de profundidad de `triangulos`. */
  function haciaCamara() {
    const v = estado.vista;
    const cx = Math.cos(v.rx), sx = Math.sin(v.rx);
    const cz = Math.cos(v.rz), sz = Math.sin(v.rz);
    return _norm([sz * sx, cz * sx, cx]);
  }

  function colorRenderizado(t, base, oscuro, d) {
    let n = normal(t.P);
    if (_dot(n, d) < 0) n = [-n[0], -n[1], -n[2]];  // la cara mira a la cámara
    const L1 = _norm([0.45, -0.55, 0.7]), L2 = _norm([-0.6, 0.3, 0.35]);
    const dif = Math.max(0, _dot(n, L1)) * 0.7 + Math.max(0, _dot(n, L2)) * 0.22;
    const H = _norm([L1[0] + d[0], L1[1] + d[1], L1[2] + d[2]]);
    const esp = Math.pow(Math.max(0, _dot(n, H)), 28) * 0.28;
    const amb = oscuro ? 0.2 : 0.3;
    const k = amb + dif;
    const c = base.map((b) => Math.min(255, Math.round(b * k + 255 * esp)));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  function pintar(c, oscuro) {
    if (!mallas.size || !window.aPX) return;
    const E = estilo();
    const tinta = oscuro ? "235,235,238" : "20,20,24";
    const tris = triangulos();
    if (E === "alambrico") {
      // Caras apenas veladas —lo justo para que se lea qué es sólido— y todas
      // las aristas encima, también las que quedan atrás: es un fantasma.
      c.save();
      c.globalAlpha = oscuro ? 0.16 : 0.12;
      for (const t of tris) {
        const s = senalada && senalada.id === t.id && senalada.cara === t.cara;
        const b = s ? SENALADA : CLARO;
        c.fillStyle = `rgb(${b[0]},${b[1]},${b[2]})`;
        c.beginPath();
        c.moveTo(t.q[0][0], t.q[0][1]); c.lineTo(t.q[1][0], t.q[1][1]); c.lineTo(t.q[2][0], t.q[2][1]);
        c.closePath(); c.fill();
      }
      c.restore();
      pintarAristas(c, `rgba(${tinta},0.9)`, 1);
      return;
    }
    if (E === "renderizado") {
      const d = haciaCamara();
      c.save();
      c.lineJoin = "round";
      const arista = `rgba(${tinta},0.45)`;
      for (const t of tris) {
        const m = mallas.get(t.id);
        const s = senalada && senalada.id === t.id && senalada.cara === t.cara;
        const col = colorRenderizado(t, s ? SENALADA : materialDe(m), oscuro, d);
        c.fillStyle = col; c.strokeStyle = col; c.lineWidth = 1;
        c.beginPath();
        c.moveTo(t.q[0][0], t.q[0][1]); c.lineTo(t.q[1][0], t.q[1][1]); c.lineTo(t.q[2][0], t.q[2][1]);
        c.closePath(); c.fill(); c.stroke();   // el trazo tapa las costuras entre triángulos
        // El contorno de la cara, en el mismo orden de pintado: lo de adelante
        // tapa las aristas de atrás. No se ven aristas a través de la pieza.
        if (t.borde[0] || t.borde[1] || t.borde[2]) {
          c.strokeStyle = arista; c.lineWidth = 0.9;
          c.beginPath();
          for (let k = 0; k < 3; k++) {
            if (!t.borde[k]) continue;
            const a = t.q[k], b = t.q[(k + 1) % 3];
            c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]);
          }
          c.stroke();
        }
      }
      c.restore();
      return;
    }
    for (const t of tris) {
      c.fillStyle = color(t, oscuro);
      c.beginPath();
      c.moveTo(t.q[0][0], t.q[0][1]);
      c.lineTo(t.q[1][0], t.q[1][1]);
      c.lineTo(t.q[2][0], t.q[2][1]);
      c.closePath();
      c.fill();
    }
    pintarAristas(c, oscuro ? "rgba(235,235,238,0.55)" : "rgba(20,20,24,0.75)", 1);
  }

  function pintarAristas(c, color, grosor) {
    c.strokeStyle = color;
    c.lineWidth = grosor;
    for (const m of mallas.values()) {
      for (const arista of m.aristas || []) {
        c.beginPath();
        arista.forEach((p, i) => {
          const q = window.aPX(p[0], p[1], p[2]);
          if (i) c.lineTo(q[0], q[1]); else c.moveTo(q[0], q[1]);
        });
        c.stroke();
      }
    }
  }

  // --- señalar una cara ----------------------------------------------------
  function dentro(q, x, y) {
    const [a, b, c] = q;
    const s = (p1, p2) => (x - p2[0]) * (p1[1] - p2[1]) - (p1[0] - p2[0]) * (y - p2[1]);
    const d1 = s(a, b), d2 = s(b, c), d3 = s(c, a);
    return !((d1 < 0 || d2 < 0 || d3 < 0) && (d1 > 0 || d2 > 0 || d3 > 0));
  }

  /** La cara que está bajo el cursor, o null. Se recorre de cerca a lejos:
   *  la primera que atrapa el punto es la que se está viendo. */
  function caraEn(px, py) {
    const tris = triangulos();
    for (let i = tris.length - 1; i >= 0; i--) {
      if (dentro(tris[i].q, px, py)) return { id: tris[i].id, cara: tris[i].cara, tri: tris[i] };
    }
    return null;
  }

  function senalar(cual) {
    senalada = cual ? { id: cual.id, cara: cual.cara } : null;
    // El panel del historial sigue a la pieza señalada: señalar una cara es
    // decir «de ésta quiero ver cómo se hizo». No se espera a la respuesta
    // porque pintar no debe quedarse esperando a la red.
    if (window.Historial) Historial.alSenalar(senalada);
    if (window.invalidarPlano) window.invalidarPlano();
    if (window.pintar) window.pintar();
    return senalada;
  }

  function hay() { return mallas.size > 0; }

  /** Las ocho esquinas de la caja que encierra todas las piezas, en el mundo.
   *
   *  Es para encuadrar: hasta la 0.19.0 encuadrar sólo miraba los trazos del
   *  dibujo 2D, así que una pieza sin su contorno —borrado después de
   *  levantarla— no entraba en la cuenta y Extents la dejaba fuera. */
  function esquinas(solo = null) {
    let x0 = Infinity, y0 = Infinity, z0 = Infinity;
    let x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
    for (const [id, m] of mallas) {
      if (solo !== null && id !== solo) continue;
      for (const cara of m.caras || []) {
        const vs = cara.v || [];
        for (let i = 0; i + 2 < vs.length; i += 3) {
          if (vs[i] < x0) x0 = vs[i]; if (vs[i] > x1) x1 = vs[i];
          if (vs[i + 1] < y0) y0 = vs[i + 1]; if (vs[i + 1] > y1) y1 = vs[i + 1];
          if (vs[i + 2] < z0) z0 = vs[i + 2]; if (vs[i + 2] > z1) z1 = vs[i + 2];
        }
      }
    }
    if (!isFinite(x0)) return [];
    const fuera = [];
    for (const x of [x0, x1]) for (const y of [y0, y1]) for (const z of [z0, z1]) fuera.push([x, y, z]);
    return fuera;
  }
  function primero() { return [...mallas.keys()][0] || null; }
  function medidas(id) { return mallas.get(id || primero()) || null; }

  return { refrescar, refrescarUna, olvidar, pintar, caraEn, senalar, hay, primero, medidas, esquinas,
           estilo, ESTILOS,
           get senalada() { return senalada; } };
})();

window.Cuerpos = Cuerpos;
