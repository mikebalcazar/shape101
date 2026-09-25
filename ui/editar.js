/* Edición  ·  features 32 a 41, 43 y 44.
 *
 * Todas siguen el mismo guion: se pide la selección (o se usa la que ya había),
 * se piden los puntos que hagan falta, y se manda **una** operación al servidor
 * — una transacción, un Ctrl+Z.
 *
 * Las transformaciones no se hacen con una matriz genérica a propósito. Una
 * matriz mueve bien los puntos y estropea todo lo demás: el radio de un círculo
 * espejeado, los ángulos de un arco, la rotación de un texto que queda al
 * revés y no se puede leer. Cada tipo dice cómo se transforma él.
 */

/* ===================================================================== */
/* Transformaciones                                                      */
/* ===================================================================== */
const rad = (g) => g * Math.PI / 180;
const deg = (r) => r * 180 / Math.PI;

const T = {
  mover: (dx, dy) => ({
    punto: (p) => [p[0] + dx, p[1] + dy],
    angulo: (a) => a,
    escala: 1,
    espejo: false,
  }),
  rotar: (c, ang) => {
    const s = Math.sin(rad(ang)), k = Math.cos(rad(ang));
    return {
      punto: (p) => [c[0] + (p[0] - c[0]) * k - (p[1] - c[1]) * s,
                     c[1] + (p[0] - c[0]) * s + (p[1] - c[1]) * k],
      angulo: (a) => (a + ang) % 360,
      escala: 1,
      espejo: false,
    };
  },
  escalar: (c, f) => ({
    punto: (p) => [c[0] + (p[0] - c[0]) * f, c[1] + (p[1] - c[1]) * f],
    angulo: (a) => a,
    escala: f,
    espejo: false,
  }),
  /* Escala en UNA dirección (Mike, 12-sep-2026): el vector base→referencia es
   * el eje; sólo se estira la componente de cada punto sobre ese eje, la
   * perpendicular queda igual. Un mueble de 900 de ancho pasa a 1000 sin
   * tocar el alto. `u` es el eje unitario y `k` el factor sobre él. */
  escalarEje: (c, u, k) => ({
    punto: (p) => {
      const dx = p[0] - c[0], dy = p[1] - c[1];
      const t = dx * u[0] + dy * u[1];
      return [c[0] + dx + (k - 1) * t * u[0], c[1] + dy + (k - 1) * t * u[1]];
    },
    angulo: (a) => a,
    escala: 1,          // radios, alturas de texto y bloques no cambian
    espejo: false,
    eje: { u, k },
  }),
  espejo: (a, b) => {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const largo2 = dx * dx + dy * dy || 1;
    const angEje = deg(Math.atan2(dy, dx));
    return {
      punto: (p) => {
        const t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / largo2;
        const px = a[0] + t * dx, py = a[1] + t * dy;
        return [2 * px - p[0], 2 * py - p[1]];
      },
      angulo: (ang) => (2 * angEje - ang + 720) % 360,
      escala: 1,
      espejo: true,
    };
  },
};

/* ===================================================================== */
/* El fantasma  ·  punto 13                                              */
/* ===================================================================== */
/* Mike: *«cuando se mueva un objeto, o se rote, mostrar el preview de cómo se
 * está moviendo el objeto a su nueva posición, con trazo fantasmeado»*.
 *
 * Hasta ahora la única pista era una goma de un punto a otro: dice cuánto te
 * mueves, no **cómo queda**. Con una rotación eso es casi inútil — nadie
 * traduce de cabeza «32° respecto a este centro» a la posición final de un
 * mueble.
 *
 * Se pintan los trazos que el lienzo ya tiene, pasados por la misma
 * transformación que se va a mandar al servidor. Que sea la misma función
 * importa: si el fantasma se calculara aparte, enseñaría una cosa y se
 * ejecutaría otra, y el usuario aprendería a desconfiar de él.
 *
 * Sale de los trazos ya teselados y no de las entidades porque es una vista
 * previa: no tiene que ser exacta al micrón, tiene que ir a la velocidad del
 * ratón. En una selección enorme se corta, por lo mismo. */
const FANTASMA_MAX = 4000;      // trazos; de ahí para arriba se arrastraría

function fantasmaDe(ids, t) {
  const dentro = new Set(ids);
  const salida = [];
  for (const tr of estado.trazos) {
    if (!dentro.has(tr.id)) continue;
    if (salida.length >= FANTASMA_MAX) break;
    if (tr.clase === "linea" && tr.puntos) {
      salida.push({ clase: "linea", puntos: tr.puntos.map(t.punto) });
    } else if (tr.clase === "texto") {
      salida.push({ clase: "texto", p: t.punto(tr.p), texto: tr.texto,
                    altura: tr.altura * (t.escala || 1),
                    rotacion: t.angulo(tr.rotacion || 0),
                    alineacion: tr.alineacion });
    }
  }
  return salida;
}

/** El hule de siempre —la liga del punto base al cursor— más el fantasma. */
function conFantasma(ids, base, hacerT) {
  return (q) => ({
    partes: [{ tipo: "linea", a: base, b: q }],
    fantasma: fantasmaDe(ids, hacerT(q)),
  });
}

/** Qué cambia en una entidad cuando se le aplica la transformación `t`. */
function transformar(ent, t, seleccion = null) {
  const P = t.punto;
  switch (ent.tipo) {
    case "cota": {
      // Mike (7-sep-2026): «las líderes, una vez creadas no me deja moverlas,
      // ni las cotas. Las cotas se deben mover con referencia a la entidad de
      // la que se referencian». Los puntos pegados a una entidad que NO viene
      // en la selección se quedan donde la entidad los tiene; lo que se mueve
      // es lo demás (la línea de cota, el texto, el codo de la directriz). Si
      // la entidad también se mueve, se mueve todo y la liga la vuelve a
      // cuadrar el motor. Sin ligas, se mueve entera.
      const ligas = ent.liga || [];
      const sel = seleccion || new Set();
      let pegados = 0;
      const puntos = ent.puntos.map((q, i) => {
        const l = ligas[i];
        if (l && l.id && !sel.has(l.id)) { pegados++; return q; }
        return P(q);
      });
      const cambios = { puntos };
      if (!pegados && !t.espejo && ent.clase === "lineal") cambios.rotacion = t.angulo(ent.rotacion || 0);
      return cambios;
    }
    case "linea":
      return { p1: P(ent.p1), p2: P(ent.p2) };
    case "polilinea": {
      // El bulge cambia de signo al espejear: si no, los arcos de una puerta
      // espejeada se van hacia el lado contrario del que deberían.
      const puntos = ent.puntos.map((v) => {
        const q = P([v[0], v[1]]);
        return [q[0], q[1], t.espejo ? -(v[2] || 0) : (v[2] || 0)];
      });
      return { puntos };
    }
    case "circulo":
      return { centro: P(ent.centro), radio: ent.radio * t.escala };
    case "arco": {
      const a0 = t.angulo(ent.ang_ini), a1 = t.angulo(ent.ang_fin);
      // Espejear invierte el sentido del barrido, así que los extremos se
      // intercambian; si no, el arco sale complementario (el trozo que falta).
      return {
        centro: P(ent.centro), radio: ent.radio * t.escala,
        ang_ini: t.espejo ? a1 : a0,
        ang_fin: t.espejo ? a0 : a1,
      };
    }
    case "elipse": {
      const c = P(ent.centro);
      const punta = P([ent.centro[0] + ent.eje_mayor[0], ent.centro[1] + ent.eje_mayor[1]]);
      return { centro: c, eje_mayor: [punta[0] - c[0], punta[1] - c[1]], razon: ent.razon };
    }
    case "spline":
      return {
        puntos_ajuste: (ent.puntos_ajuste || []).map(P),
        puntos_control: (ent.puntos_control || []).map(P),
      };
    case "punto":
      return { p: P(ent.p) };
    case "solido":
      return { puntos: ent.puntos.map(P) };
    case "texto":
    case "textom": {
      // El texto espejeado NO se voltea: un rótulo al revés no se lee, y nadie
      // que espejea media cocina quiere las notas en espejo.
      const cambios = { p: P(ent.p), altura: ent.altura * t.escala };
      if (!t.espejo) cambios.rotacion = t.angulo(ent.rotacion);
      if (ent.tipo === "textom") cambios.ancho = ent.ancho * t.escala;
      return cambios;
    }
    case "insercion":
      return {
        p: P(ent.p), rotacion: t.angulo(ent.rotacion),
        escala: [ent.escala[0] * t.escala * (t.espejo ? -1 : 1), ent.escala[1] * t.escala],
      };
    case "rayado":
      return {
        rutas: ent.rutas.map((ruta) => ruta.map((v) => {
          const q = P([v[0], v[1]]);
          return [q[0], q[1], t.espejo ? -(v[2] || 0) : (v[2] || 0)];
        })),
      };
    default:
      return null;      // una entidad ajena no se mueve: no sabemos qué es
  }
}

async function traer(ids) {
  // Una petición, no una por entidad: mover 5 000 cosas eran 5 000 viajes al
  // motor antes de empezar a mover. Ver `/api/entidades/varias`.
  if (!ids.length) return [];
  const r = await post("/api/entidades/varias", { ids });
  return r.entidades;
}

async function aplicarOperacion(op) {
  const r = await post("/api/operacion", op);
  aplicar(r);
  // El parche trae sólo lo que cambió. Si por lo que sea no viene, se recarga
  // el dibujo entero: lento, pero correcto. Ver `aplicarParche` en app.js.
  if (!aplicarParche(r)) await recargarTrazos();
  return r;
}

/** Aplica una transformación a una selección. Si `copia`, deja el original. */
async function transformarSeleccion(ids, t, accion, copia = false, extra = null) {
  const ents = await traer(ids);
  const cambios = {};
  const agregar = [];
  const borrar = [];
  let ajenas = 0, arcos = 0, bulges = 0;
  const sel = new Set(ids);
  for (const ent of ents) {
    // Escala en una dirección: un círculo deja de ser círculo. Se cambia por
    // la elipse exacta (borrar + agregar); un arco no tiene entidad exacta
    // aquí y se deja quieto avisando; los arcos de polilínea (bulge) se
    // aproximan: se estira la cuerda y se conserva el bulge.
    if (t.eje && !copia && ent.tipo === "circulo") {
      const { u, k } = t.eje;
      const r = ent.radio;
      const mayor = k >= 1 ? [u[0] * r * k, u[1] * r * k] : [-u[1] * r, u[0] * r];
      agregar.push({ tipo: "elipse", capa: ent.capa, color: ent.color, tipo_linea: ent.tipo_linea,
                     centro: t.punto(ent.centro), eje_mayor: mayor, razon: k >= 1 ? 1 / k : k });
      borrar.push(ent.id);
      continue;
    }
    if (t.eje && ent.tipo === "arco") { arcos++; continue; }
    if (t.eje && ent.tipo === "polilinea" && (ent.puntos || []).some((v) => v[2])) bulges++;
    const c = transformar(ent, t, sel);
    if (!c) { ajenas++; continue; }
    // Una copia de una cota no sigue pegada a la pieza original: sería una
    // cota que mide otra cosa de la que está encima.
    if (extra) Object.assign(c, extra);   // p. ej. el plano nuevo, al girar entre planos
    if (copia) agregar.push({ ...ent, ...c, id: undefined, ...(ent.tipo === "cota" ? { liga: [] } : {}) });
    else cambios[ent.id] = c;
  }
  await aplicarOperacion({ accion, cambios, agregar, borrar });
  if (arcos) Comandos.eco(`${arcos} arco(s) no se escalan en una sola dirección: se quedaron como estaban.`, "malo");
  if (bulges) Comandos.eco(`${bulges} polilínea(s) con arcos: los arcos se aproximaron (cuerda estirada, curvatura igual).`);
  if (ajenas) {
    Comandos.eco(`${ajenas} entidad(es) del archivo original no se movieron: ` +
                 "este programa todavía no sabe qué son.", "malo");
  }
  return Object.keys(cambios).length + agregar.length;
}

/* Escalar en una dirección  ·  Mike (12-sep-2026): «sólo se incrementa escala
 * en el vector que se seleccionó el origen y referencia». Base → referencia
 * define el eje y lo que mide hoy; el punto nuevo (o el factor) dice lo que
 * debe medir sobre ese eje. Un snap fuera del eje se proyecta al eje. */
Comandos.registrar({
  nombre: "ESCALARD", alias: ["ESD", "SCD", "ESCALAD"],
  ayuda: "Escala sólo en una dirección: punto base, referencia (define el eje) y punto nuevo (o factor)",
  correr: async () => {
    const ids = await Seleccion.pedir({ mensaje: "Selecciona lo que se escala en una dirección" });
    if (!ids.length) return;
    const c = await Entrada.pedirPunto({ mensaje: "Punto base" });
    const r1 = await Entrada.pedirPunto({
      mensaje: "Punto de referencia: marca el eje y lo que mide hoy", base: c,
      hule: (q) => ({ tipo: "linea", a: c, b: q }),
    });
    const L0 = Math.hypot(r1[0] - c[0], r1[1] - c[1]);
    if (L0 < 1e-9) return Comandos.eco("El punto de referencia es el mismo que la base.", "malo");
    const u = [(r1[0] - c[0]) / L0, (r1[1] - c[1]) / L0];
    const sobreEje = (q) => ((q[0] - c[0]) * u[0] + (q[1] - c[1]) * u[1]) / L0;
    const r2 = await Entrada.pedirPunto({
      mensaje: "Punto nuevo: hasta dónde debe llegar sobre el eje (o teclea el factor)", base: c, numero: true,
      hule: conFantasma(ids, c, (q) => T.escalarEje(c, u, Math.max(1e-9, sobreEje(q)))),
    });
    const k = Array.isArray(r2) ? sobreEje(r2) : r2.numero;
    if (!(k > 1e-9)) return Comandos.eco("El factor tiene que ser mayor que cero (el punto nuevo quedó atrás de la base).", "malo");
    if (Math.abs(k - 1) < 1e-12) return Comandos.eco("Factor 1: nada que hacer.");
    await transformarSeleccion(ids, T.escalarEje(c, u, k), `Escalar en una dirección ${ids.length}`);
    Comandos.eco(`Escaladas ${ids.length} entidad(es) ×${mm(k)} sobre el eje.`);
    Seleccion.limpiar();
  },
});

/* ===================================================================== */
/* Borrar                                                                */
/* ===================================================================== */
Comandos.registrar({
  nombre: "BORRAR", alias: ["B", "E", "SUPR"],
  ayuda: "Borra lo seleccionado (tecla Supr)",
  correr: async () => {
    // Una pieza señalada por una cara también se borra: señalar una cara no
    // la mete en la selección, y Mike (24-sep) no podía borrar sólidos con
    // Supr por eso. Si hay selección, manda la selección, como siempre.
    const senalada = typeof Cuerpos !== "undefined" && Cuerpos.senalada;
    const ids = (!estado.sel.size && senalada) ? [senalada.id]
      : await Seleccion.pedir({ mensaje: "Selecciona lo que se borra" });
    if (!ids.length) return;
    await aplicarOperacion({ accion: `Borrar ${ids.length}`, borrar: ids });
    if (senalada && ids.includes(senalada.id)) {
      Cuerpos.senalar(null);
      await Cuerpos.refrescar();
    }
    Seleccion.limpiar();
    Comandos.eco(`${ids.length} entidad(es) borradas.`);
  },
});

/* ===================================================================== */
/* 32 · Mover   ·   33 · Copiar                                          */
/* ===================================================================== */
async function moverOCopiar(copia) {
  const ids = await Seleccion.pedir({
    mensaje: `Selecciona lo que se ${copia ? "copia" : "mueve"}` });
  if (!ids.length) return;
  const base = await Entrada.pedirPunto({ mensaje: "Punto base" });
  if (copia) {
    // Copiar sigue pidiendo destinos hasta que le digan basta: sembrar ocho
    // jaladeras son ocho clics, no ocho veces el comando.
    let n = 0;
    try {
      while (true) {
        const p = await Entrada.pedirPunto({
          mensaje: "Destino (Escape termina)", base, direccion: true,
          hule: conFantasma(ids, base, (q) => T.mover(q[0] - base[0], q[1] - base[1])),
        });
        await transformarSeleccion(ids, T.mover(p[0] - base[0], p[1] - base[1]),
                                   `Copiar ${ids.length}`, true);
        n++;
      }
    } catch (err) {
      if (err.message !== "cancelado") throw err;
    }
    Comandos.eco(`${n} copia(s).`);
  } else {
    const p = await Entrada.pedirPunto({
      mensaje: "Destino", base, direccion: true,
      hule: conFantasma(ids, base, (q) => T.mover(q[0] - base[0], q[1] - base[1])),
    });
    await transformarSeleccion(ids, T.mover(p[0] - base[0], p[1] - base[1]),
                               `Mover ${ids.length}`);
    Comandos.eco(`Movidas ${ids.length}: ΔX ${mm(p[0] - base[0])}, ΔY ${mm(p[1] - base[1])}.`);
  }
  Seleccion.limpiar();
}

Comandos.registrar({ nombre: "MOVER", alias: ["M"], ayuda: "Mueve lo seleccionado",
                     correr: () => moverOCopiar(false) });
Comandos.registrar({ nombre: "COPIAR", alias: ["CP", "CO"], ayuda: "Copia lo seleccionado",
                     correr: () => moverOCopiar(true) });

/* ===================================================================== */
/* 34 · Rotar                                                            */
/* ===================================================================== */
/* Girar de un plano a otro  ·  0.21.3
 *
 * Mike (24-sep): importó un dibujo de draw101 —que cae en el suelo— y quiso
 * pararlo en la pared: «rotarlo 90° desde la vista lateral y no puedo». ROTAR
 * giraba siempre dentro del plano de la entidad, mirara uno desde donde
 * mirara. Ahora ROTAR gira **alrededor de la normal de la ventana donde se
 * está**: desde la Lateral, el eje es X, y un dibujo del suelo girado 90° ahí
 * queda en la Frontal (XZ). Como sólo existen tres planos, entre planos el
 * giro va de 90 en 90; el fantasma lo enseña ya redondeado.
 *
 * La cuenta va por el mundo de tres: cada punto del dibujo se lleva al mundo,
 * se gira alrededor del eje que pasa por el centro, y se vuelve a las dos
 * coordenadas del plano al que cayó. Lo que sale es una transformación plana
 * de las de siempre —con espejo, si el giro lo dejó volteado— más el nombre
 * del plano nuevo. */
const _A_LOCAL = {
  XY: (m) => [m[0], m[1], m[2]],
  XZ: (m) => [m[0], m[2], -m[1]],
  YZ: (m) => [m[1], m[2], m[0]],
};

function giroEntrePlanos(origen, ventana, c, ang) {
  const n = Planos.normal(ventana);
  const C = Planos.aMundo(ventana, c[0], c[1], 0);
  const s = Math.sin(rad(ang)), k = Math.cos(rad(ang));
  const R = (m) => {   // Rodrigues alrededor de n, que es unitario
    const v = [m[0] - C[0], m[1] - C[1], m[2] - C[2]];
    const nv = n[0] * v[0] + n[1] * v[1] + n[2] * v[2];
    const cr = [n[1] * v[2] - n[2] * v[1], n[2] * v[0] - n[0] * v[2], n[0] * v[1] - n[1] * v[0]];
    return [0, 1, 2].map((i) => C[i] + v[i] * k + cr[i] * s + n[i] * nv * (1 - k));
  };
  const muestra = [[0, 0], [1, 0], [0, 1]].map(([u, v]) => R(Planos.aMundo(origen, u, v, 0)));
  // El plano al que cayó: aquel en el que las tres muestras quedan a la misma
  // altura `w`. Si el centro de giro no está en el origen, esa altura no es
  // cero: el dibujo cae en una pared **paralela** (y = 350, por ejemplo), y
  // aquí sólo existen los tres planos por el origen —también las extrusiones
  // salen de ahí—. Así que se deja en el plano por el origen y se avisa. Mike
  // (24-sep) lo vivió como «ese giro no deja el dibujo en ningún plano».
  let plano = null, loc = null, altura = 0;
  for (const cand of ["XY", "XZ", "YZ"]) {
    const l = muestra.map(_A_LOCAL[cand]);
    const ws = l.map((q) => q[2]);
    if (Math.max(...ws) - Math.min(...ws) < 1e-6) { plano = cand; loc = l; altura = ws[0]; break; }
  }
  if (!plano) return null;    // el giro no cayó en ningún plano: no era de 90 en 90
  const [A, B, D] = loc;
  const eu = [B[0] - A[0], B[1] - A[1]], ev = [D[0] - A[0], D[1] - A[1]];
  const espejo = eu[0] * ev[1] - eu[1] * ev[0] < 0;
  const K = deg(Math.atan2(eu[1], eu[0]));
  return {
    plano, altura,
    t: {
      punto: (p) => [A[0] + p[0] * eu[0] + p[1] * ev[0], A[1] + p[0] * eu[1] + p[1] * ev[1]],
      angulo: (a) => espejo ? (K - a + 720) % 360 : (a + K + 360) % 360,
      escala: 1,
      espejo,
    },
  };
}

Comandos.registrar({
  nombre: "ROTAR", alias: ["RO"],
  ayuda: "Rota lo seleccionado alrededor de un punto; desde otra ventana, lo pasa de plano (de 90 en 90)",
  correr: async () => {
    const ids = await Seleccion.pedir({ mensaje: "Selecciona lo que se rota" });
    if (!ids.length) return;
    const ventana = (estado.vista && estado.vista.plano) || "XY";
    const planos = new Set((await traer(ids)).map((e) => e.plano || "XY"));
    const entrePlanos = !(planos.size === 1 && planos.has(ventana));
    if (entrePlanos && planos.size > 1) {
      return Comandos.eco("Para girar de un plano a otro, selecciona cosas que estén en el mismo plano.", "malo");
    }
    const c = await Entrada.pedirPunto({ mensaje: "Centro de giro" });
    const anguloDe = (q) => Array.isArray(q) ? deg(Math.atan2(q[1] - c[1], q[0] - c[0])) : q.numero;
    if (!entrePlanos) {
      const p = await Entrada.pedirPunto({
        mensaje: "Ángulo (o teclea los grados)", base: c, numero: true,
        hule: conFantasma(ids, c, (q) => T.rotar(c, anguloDe(q))),
      });
      const ang = anguloDe(p);
      await transformarSeleccion(ids, T.rotar(c, ang), `Rotar ${ids.length}`);
      Comandos.eco(`Rotadas ${ids.length} entidad(es) ${grados(ang)}°.`);
      Seleccion.limpiar();
      return;
    }
    const origen = [...planos][0];
    const a90 = (a) => ((Math.round(a / 90) * 90) % 360 + 360) % 360;
    const p = await Entrada.pedirPunto({
      mensaje: `Ángulo, de 90 en 90: el dibujo está en ${origen} y aquí se gira alrededor del eje de la ventana (o teclea los grados)`,
      base: c, numero: true,
      hule: (q) => {
        const g = giroEntrePlanos(origen, ventana, c, a90(anguloDe(q)));
        return { partes: [{ tipo: "linea", a: c, b: Array.isArray(q) ? q : c }],
                 fantasma: g ? fantasmaDe(ids, g.t).map((tr) => ({ ...tr, plano: g.plano })) : [] };
      },
    });
    const ang = a90(anguloDe(p));
    if (ang === 0) return Comandos.eco("Giro de 0°: nada que hacer. Entre planos se gira de 90 en 90.");
    const g = giroEntrePlanos(origen, ventana, c, ang);
    if (!g) return Comandos.eco("Ese giro no deja el dibujo en ningún plano.", "malo");
    await transformarSeleccion(ids, g.t, `Rotar ${ids.length} a ${g.plano}`, false, { plano: g.plano });
    Comandos.eco(`Rotadas ${ids.length} entidad(es) ${grados(ang)}° alrededor del eje de la ${ventana}: ahora están en ${g.plano}.`);
    if (Math.abs(g.altura) > 1e-6) {
      Comandos.eco(`Quedan en el plano ${g.plano} por el origen: aquí sólo hay tres planos, y una pared a ${mm(Math.abs(g.altura))} ${U()} del origen no existe. El giro es el mismo; sólo se corrió hasta el plano.`);
    }
    Seleccion.limpiar();
  },
});

/* ===================================================================== */
/* 35 · Escalar                                                          */
/* ===================================================================== */
/* Mike (9-sep-2026): «como casi todos los CAD: base → punto de referencia (lo
 * que mide hoy) → punto nuevo (lo que debe medir)». Factor = |nuevo − base| /
 * |referencia − base|. En cualquiera de los dos pasos se puede teclear el
 * factor directo. La previa enseña el fantasma mientras se mueve el tercero. */
Comandos.registrar({
  nombre: "ESCALAR", alias: ["ES", "SC"],
  ayuda: "Escala lo seleccionado: punto base, punto de referencia y punto nuevo (o teclea el factor)",
  correr: async () => {
    const ids = await Seleccion.pedir({ mensaje: "Selecciona lo que se escala" });
    if (!ids.length) return;
    const c = await Entrada.pedirPunto({ mensaje: "Punto base" });
    let f = null;
    const r1 = await Entrada.pedirPunto({
      mensaje: "Punto de referencia (o teclea el factor)", base: c, numero: true,
      hule: (q) => ({ tipo: "linea", a: c, b: q }),
    });
    if (!Array.isArray(r1)) f = r1.numero;
    else {
      const L0 = Math.hypot(r1[0] - c[0], r1[1] - c[1]);
      if (L0 < 1e-9) return Comandos.eco("El punto de referencia es el mismo que la base.", "malo");
      const r2 = await Entrada.pedirPunto({
        mensaje: "Punto nuevo: hasta dónde debe llegar (o teclea el factor)", base: c, numero: true,
        hule: conFantasma(ids, c, (q) => T.escalar(c, Math.max(1e-9, Math.hypot(q[0] - c[0], q[1] - c[1]) / L0))),
      });
      f = Array.isArray(r2) ? Math.hypot(r2[0] - c[0], r2[1] - c[1]) / L0 : r2.numero;
    }
    if (!(f > 1e-9)) return Comandos.eco("El factor tiene que ser mayor que cero.", "malo");
    if (Math.abs(f - 1) < 1e-12) return Comandos.eco("Factor 1: nada que hacer.");
    await transformarSeleccion(ids, T.escalar(c, f), `Escalar ${ids.length}`);
    Comandos.eco(`Escaladas ${ids.length} entidad(es) ×${mm(f)}.`);
    Seleccion.limpiar();
  },
});

/* ===================================================================== */
/* 36 · Espejo                                                           */
/* ===================================================================== */
Comandos.registrar({
  nombre: "ESPEJO", alias: ["SI", "MI"],
  ayuda: "Refleja lo seleccionado sobre un eje",
  correr: async () => {
    const ids = await Seleccion.pedir({ mensaje: "Selecciona lo que se refleja" });
    if (!ids.length) return;
    const a = await Entrada.pedirPunto({ mensaje: "Primer punto del eje" });
    const b = await Entrada.pedirPunto({
      mensaje: "Segundo punto del eje", base: a,
      hule: conFantasma(ids, a, (q) => T.espejo(a, q)),
    });
    const borrar = (await Entrada.pedirTexto({
      mensaje: "¿Borrar el original? S/N", valor: "N" })).toUpperCase().startsWith("S");
    await transformarSeleccion(ids, T.espejo(a, b), `Espejo ${ids.length}`, !borrar);
    if (borrar) Comandos.eco(`${ids.length} entidad(es) reflejadas.`);
    else Comandos.eco(`${ids.length} copia(s) reflejadas.`);
    Seleccion.limpiar();
  },
});

/* ===================================================================== */
/* 37 · Desfase (offset)                                                 */
/* ===================================================================== */
/* Sólo línea, polilínea, círculo y arco. Una spline desfasada de verdad no es
 * una spline —es otra curva sin forma cerrada— y las aproximaciones que hacen
 * otros programas se notan en el corte. Mejor decir que no se puede. */
function desfasar(ent, d, lado) {
  if (ent.tipo === "linea") {
    const dx = ent.p2[0] - ent.p1[0], dy = ent.p2[1] - ent.p1[1];
    const L = Math.hypot(dx, dy);
    if (L < 1e-12) return null;
    const nx = -dy / L * d * lado, ny = dx / L * d * lado;
    return { ...ent, id: undefined,
             p1: [ent.p1[0] + nx, ent.p1[1] + ny],
             p2: [ent.p2[0] + nx, ent.p2[1] + ny] };
  }
  if (ent.tipo === "circulo") {
    const r = ent.radio + d * lado;
    return r > 1e-9 ? { ...ent, id: undefined, radio: r } : null;
  }
  if (ent.tipo === "arco") {
    const r = ent.radio + d * lado;
    return r > 1e-9 ? { ...ent, id: undefined, radio: r } : null;
  }
  if (ent.tipo === "polilinea") {
    // Cada tramo se desplaza y los vecinos se recortan en su cruce. Es el
    // desfase que hace falta para sacar el interior de un mueble a partir de su
    // exterior, que es para lo que se usa nueve de cada diez veces.
    const pts = ent.puntos.map((v) => [v[0], v[1]]);
    const n = pts.length;
    const tramos = [];
    const ultimo = ent.cerrada ? n : n - 1;
    for (let i = 0; i < ultimo; i++) {
      const a = pts[i], b = pts[(i + 1) % n];
      const dx = b[0] - a[0], dy = b[1] - a[1];
      const L = Math.hypot(dx, dy);
      if (L < 1e-12) continue;
      const nx = -dy / L * d * lado, ny = dx / L * d * lado;
      tramos.push([[a[0] + nx, a[1] + ny], [b[0] + nx, b[1] + ny]]);
    }
    if (!tramos.length) return null;
    const nuevos = [];
    for (let i = 0; i < tramos.length; i++) {
      const cur = tramos[i];
      const sig = tramos[(i + 1) % tramos.length];
      if (i === 0 && !ent.cerrada) nuevos.push([cur[0][0], cur[0][1], 0]);
      if (i === tramos.length - 1 && !ent.cerrada) {
        nuevos.push([cur[1][0], cur[1][1], 0]);
        break;
      }
      const cruce = Osnap.interseccion(
        { tipo: "seg", a: [cur[0][0] - (cur[1][0] - cur[0][0]) * 1000, cur[0][1] - (cur[1][1] - cur[0][1]) * 1000],
          b: [cur[1][0] + (cur[1][0] - cur[0][0]) * 1000, cur[1][1] + (cur[1][1] - cur[0][1]) * 1000] },
        { tipo: "seg", a: [sig[0][0] - (sig[1][0] - sig[0][0]) * 1000, sig[0][1] - (sig[1][1] - sig[0][1]) * 1000],
          b: [sig[1][0] + (sig[1][0] - sig[0][0]) * 1000, sig[1][1] + (sig[1][1] - sig[0][1]) * 1000] });
      nuevos.push(cruce.length ? [cruce[0][0], cruce[0][1], 0] : [cur[1][0], cur[1][1], 0]);
    }
    return { ...ent, id: undefined, puntos: nuevos };
  }
  return null;
}

Comandos.registrar({
  nombre: "DESFASE", alias: ["DF", "O", "OFFSET"],
  ayuda: "Copia una línea, polilínea, círculo o arco a una distancia dada",
  correr: async () => {
    const d = await Entrada.pedirNumero({ mensaje: "Distancia del desfase", minimo: 1e-6 });
    await repetir(async () => {
      const id = await Seleccion.pedirUna({
        mensaje: "Elige la entidad a desfasar",
        filtro: (e) => ["linea", "polilinea", "circulo", "arco"].includes(e.tipo),
        queja: "El desfase funciona con líneas, polilíneas, círculos y arcos.",
      });
      const ent = await api(`/api/entidad/${id}`);
      const p = await Entrada.pedirPunto({ mensaje: "¿De qué lado?" });

      // De qué lado quedó el clic respecto de la entidad
      let lado = 1;
      if (ent.tipo === "linea") {
        const dx = ent.p2[0] - ent.p1[0], dy = ent.p2[1] - ent.p1[1];
        lado = Math.sign((p[0] - ent.p1[0]) * -dy + (p[1] - ent.p1[1]) * dx) || 1;
      } else if (ent.tipo === "circulo" || ent.tipo === "arco") {
        lado = Math.hypot(p[0] - ent.centro[0], p[1] - ent.centro[1]) > ent.radio ? 1 : -1;
      } else if (ent.tipo === "polilinea") {
        const prims = estado.geometria.filter((pr) => pr.id === id && pr.tipo === "seg");
        let mejor = null;
        for (const pr of prims) {
          const q = Osnap.sobre(pr, p);
          const dd = Math.hypot(q[0] - p[0], q[1] - p[1]);
          if (!mejor || dd < mejor.d) mejor = { pr, d: dd };
        }
        if (mejor) {
          const dx = mejor.pr.b[0] - mejor.pr.a[0], dy = mejor.pr.b[1] - mejor.pr.a[1];
          lado = Math.sign((p[0] - mejor.pr.a[0]) * -dy + (p[1] - mejor.pr.a[1]) * dx) || 1;
        }
      }

      const nuevo = desfasar(ent, d, lado);
      if (!nuevo) return Comandos.eco("El desfase dejaría la figura sin tamaño.", "malo");
      await aplicarOperacion({ accion: "Desfase", agregar: [nuevo] });
      Seleccion.limpiar();
    });
  },
});

/* ===================================================================== */
/* 38 · Recortar y extender                                              */
/* ===================================================================== */
/* Se recorta contra **todo lo que hay**, como el TRIM moderno de AutoCAD: pedir
 * primero los bordes de corte y luego los trozos era el paso que más se
 * saltaba y el que más confundía. Funciona con líneas y arcos; una polilínea se
 * explota antes (todavía no) — lo dice y no lo intenta a medias. */
function paramEnSeg(pr, p) {
  const dx = pr.b[0] - pr.a[0], dy = pr.b[1] - pr.a[1];
  const L2 = dx * dx + dy * dy;
  return L2 < 1e-18 ? 0 : ((p[0] - pr.a[0]) * dx + (p[1] - pr.a[1]) * dy) / L2;
}

async function recortarOExtender(extender) {
  await repetir(async () => {
    const id = await Seleccion.pedirUna({
      mensaje: extender ? "Elige la línea a extender" : "Elige el trozo a quitar",
      icono: extender ? "extender" : "tijera",
      filtro: (e) => ["linea", "arco"].includes(e.tipo) || (!extender && e.tipo === "polilinea"),
      queja: extender ? "Por ahora se extienden líneas y arcos." : "Por ahora se recortan líneas, arcos y polilíneas.",
    });
    const ent = await api(`/api/entidad/${id}`);
    const p = [estado.cursor.x, estado.cursor.y];

    if (ent.tipo === "polilinea") { await recortarPolilinea(ent, p); Seleccion.limpiar(); return; }

    // cruces con todo lo demás
    const mias = estado.geometria.filter((pr) => pr.id === id);
    const otras = estado.geometria.filter((pr) => pr.id !== id);
    const cruces = [];
    for (const a of mias) {
      for (const b of otras) {
        for (const q of Osnap.interseccion(extender ? alargada(a) : a, b)) cruces.push(q);
      }
    }
    if (!cruces.length) {
      return Comandos.eco(extender
        ? "No hay nada hacia donde extender."
        : "Esa entidad no cruza con ninguna otra: no hay dónde recortar.", "malo");
    }

    if (ent.tipo === "linea") {
      const pr = { tipo: "seg", a: ent.p1, b: ent.p2 };
      const ts = cruces.map((q) => paramEnSeg(pr, q)).sort((x, y) => x - y);
      const tp = paramEnSeg(pr, p);
      if (extender) {
        // se alarga hasta el cruce más cercano por el lado del clic
        const candidatos = tp > 0.5 ? ts.filter((t) => t > 1) : ts.filter((t) => t < 0);
        if (!candidatos.length) return Comandos.eco("No hay cruce hacia ese lado.", "malo");
        const t = tp > 0.5 ? Math.min(...candidatos) : Math.max(...candidatos);
        const q = [pr.a[0] + t * (pr.b[0] - pr.a[0]), pr.a[1] + t * (pr.b[1] - pr.a[1])];
        await aplicarOperacion({ accion: "Extender",
          cambios: { [id]: tp > 0.5 ? { p2: q } : { p1: q } } });
      } else {
        const dentro = ts.filter((t) => t > 1e-9 && t < 1 - 1e-9);
        const antes = dentro.filter((t) => t < tp);
        const despues = dentro.filter((t) => t > tp);
        const t0 = antes.length ? Math.max(...antes) : null;
        const t1 = despues.length ? Math.min(...despues) : null;
        const en = (t) => [pr.a[0] + t * (pr.b[0] - pr.a[0]), pr.a[1] + t * (pr.b[1] - pr.a[1])];
        if (t0 === null && t1 === null) {
          return Comandos.eco("El trozo que señalaste no está entre dos cruces.", "malo");
        }
        if (t0 !== null && t1 !== null) {
          // el trozo está en medio: la línea se parte en dos
          await aplicarOperacion({
            accion: "Recortar",
            cambios: { [id]: { p2: en(t0) } },
            agregar: [{ ...ent, id: undefined, p1: en(t1), p2: ent.p2 }],
          });
        } else if (t1 !== null) {
          await aplicarOperacion({ accion: "Recortar", cambios: { [id]: { p1: en(t1) } } });
        } else {
          await aplicarOperacion({ accion: "Recortar", cambios: { [id]: { p2: en(t0) } } });
        }
      }
    } else {
      // arco: se recorta el extremo más cercano al clic hasta el cruce vecino
      const ang = (q) => (deg(Math.atan2(q[1] - ent.centro[1], q[0] - ent.centro[0])) + 360) % 360;
      const rel = (a) => (a - ent.ang_ini + 360) % 360;
      const barrido = rel(ent.ang_fin) || 360;
      const dentro = cruces.map(ang).map(rel).filter((t) => t > 1e-6 && t < barrido - 1e-6);
      if (!dentro.length) return Comandos.eco("No hay cruce dentro del arco.", "malo");
      const tp = rel(ang(p));
      const antes = dentro.filter((t) => t < tp), despues = dentro.filter((t) => t > tp);
      if (!antes.length && !despues.length) return Comandos.eco("Nada que recortar ahí.", "malo");
      if (despues.length && !antes.length) {
        await aplicarOperacion({ accion: "Recortar arco",
          cambios: { [id]: { ang_ini: (ent.ang_ini + Math.min(...despues)) % 360 } } });
      } else {
        await aplicarOperacion({ accion: "Recortar arco",
          cambios: { [id]: { ang_fin: (ent.ang_ini + Math.max(...antes)) % 360 } } });
      }
    }
    Seleccion.limpiar();
  });
}

/* ---------------------------------------------------------------------- */
/* Recortar una polilínea (Mike, 10-sep-2026; 0.20.4)                      */
/*                                                                        */
/* «Cuando uso trim sobre una polilínea, corta la polilínea en donde se     */
/* trimea, generando nuevos endpoints». Antes no se podía en absoluto (se   */
/* rechazaba con aviso). Ahora: se quita sólo el tramo entre los dos cruces */
/* que rodean el clic, y lo que queda SIGUE SIENDO POLILÍNEA: si el trozo   */
/* estaba en un extremo, la polilínea se acorta; si estaba en medio, quedan */
/* dos polilíneas (la original acortada y una nueva); si era cerrada, se    */
/* abre por ahí. Los tramos curvos (bulge) se cortan como arcos exactos,    */
/* con el bulge parcial correspondiente.                                    */
/*                                                                        */
/* Una posición sobre la polilínea es (k, t): tramo k y fracción t de ese  */
/* tramo (0 = vértice inicial, 1 = vértice final).                          */
/* ---------------------------------------------------------------------- */
function _tramosPolilinea(ent) {
  const pts = ent.puntos || [];
  const n = pts.length;
  const tramos = [];
  const m = n - 1 + (ent.cerrada && n > 2 ? 1 : 0);
  for (let k = 0; k < m; k++) {
    const p1 = pts[k], p2 = pts[(k + 1) % n];
    const b = p1.length > 2 ? +p1[2] || 0 : 0;
    tramos.push(_tramoDe([p1[0], p1[1]], [p2[0], p2[1]], b));
  }
  return tramos;
}

function _tramoDe(p1, p2, b) {
  const tr = { p1, p2, b, recto: Math.abs(b) < 1e-12 };
  if (tr.recto) return tr;
  // misma construcción que core/geometria._arco_de_bulge
  const cuerda = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
  if (cuerda < 1e-12) { tr.recto = true; tr.b = 0; return tr; }
  const ang = 4 * Math.atan(b);
  const r = cuerda / (2 * Math.sin(Math.abs(ang) / 2));
  const mx = (p1[0] + p2[0]) / 2, my = (p1[1] + p2[1]) / 2;
  const h = Math.sqrt(Math.max(r * r - (cuerda / 2) ** 2, 0));
  const dx = (p2[0] - p1[0]) / cuerda, dy = (p2[1] - p1[1]) / cuerda;
  const signo = ang > 0 ? 1 : -1;
  tr.c = [mx - signo * h * dy, my + signo * h * dx];
  tr.r = r;
  tr.ang = ang;                                   // barrido con signo, radianes
  tr.a1 = Math.atan2(p1[1] - tr.c[1], p1[0] - tr.c[0]);
  return tr;
}

function _paramEnTramo(tr, q) {
  if (tr.recto) return paramEnSeg({ a: tr.p1, b: tr.p2 }, q);
  let d = Math.atan2(q[1] - tr.c[1], q[0] - tr.c[0]) - tr.a1;
  d = tr.ang > 0 ? (d + 4 * Math.PI) % (2 * Math.PI) : -((-d + 4 * Math.PI) % (2 * Math.PI));
  return d / tr.ang;
}

function _puntoEnTramo(tr, t) {
  if (tr.recto) return [tr.p1[0] + t * (tr.p2[0] - tr.p1[0]), tr.p1[1] + t * (tr.p2[1] - tr.p1[1])];
  const a = tr.a1 + t * tr.ang;
  return [tr.c[0] + tr.r * Math.cos(a), tr.c[1] + tr.r * Math.sin(a)];
}

function _distTramo(tr, q) {
  if (tr.recto) {
    const t = Math.max(0, Math.min(1, paramEnSeg({ a: tr.p1, b: tr.p2 }, q)));
    const e = _puntoEnTramo(tr, t);
    return Math.hypot(q[0] - e[0], q[1] - e[1]);
  }
  const t = _paramEnTramo(tr, q);
  if (t >= 0 && t <= 1) return Math.abs(Math.hypot(q[0] - tr.c[0], q[1] - tr.c[1]) - tr.r);
  return Math.min(Math.hypot(q[0] - tr.p1[0], q[1] - tr.p1[1]), Math.hypot(q[0] - tr.p2[0], q[1] - tr.p2[1]));
}

// bulge del pedazo de un tramo curvo entre las fracciones t0 y t1
function _bulgeParcial(tr, t0, t1) {
  if (tr.recto) return 0;
  return Math.tan((t1 - t0) * tr.ang / 4);
}

function _vertice(p, b) {
  return Math.abs(b) < 1e-12 ? [p[0], p[1]] : [p[0], p[1], b];
}

/* El pedazo de polilínea que va de la posición A a la posición B siguiendo
 * los tramos hacia adelante (y dando la vuelta si es cerrada). */
function _pedazo(tramos, A, B, cerrada) {
  const m = tramos.length;
  const salida = [];
  const largo = cerrada && A.k === B.k && A.t > B.t;   // en cerrada: la vuelta completa
  if (A.k === B.k && !largo) {
    const tr = tramos[A.k];
    salida.push(_vertice(_puntoEnTramo(tr, A.t), _bulgeParcial(tr, A.t, B.t)));
    salida.push(_vertice(_puntoEnTramo(tr, B.t), 0));
    return salida;
  }
  const trA = tramos[A.k];
  salida.push(_vertice(_puntoEnTramo(trA, A.t), _bulgeParcial(trA, A.t, 1)));
  let k = A.k;
  do {
    k = cerrada ? (k + 1) % m : k + 1;
    const tr = tramos[k];
    if (k === B.k) {
      salida.push(_vertice(tr.p1, _bulgeParcial(tr, 0, B.t)));
      salida.push(_vertice(_puntoEnTramo(tr, B.t), 0));
    } else {
      salida.push(_vertice(tr.p1, tr.b));
    }
  } while (k !== B.k);
  return salida;
}

async function recortarPolilinea(ent, p) {
  const tramos = _tramosPolilinea(ent);
  if (!tramos.length) return Comandos.eco("Esa polilínea no tiene tramos.", "malo");
  const m = tramos.length;
  const cerrada = !!ent.cerrada && (ent.puntos || []).length > 2;

  // Dónde se picó: el tramo más cercano y la fracción dentro de él.
  let kp = 0, mejor = Infinity;
  tramos.forEach((tr, k) => { const d = _distTramo(tr, p); if (d < mejor) { mejor = d; kp = k; } });
  const pick = { k: kp, t: Math.max(0, Math.min(1, _paramEnTramo(tramos[kp], p))) };

  // Cruces con todo lo demás, como posiciones (k, t) sobre la polilínea.
  const mias = estado.geometria.filter((pr) => pr.id === ent.id);
  const otras = estado.geometria.filter((pr) => pr.id !== ent.id);
  const posiciones = [];
  for (const a of mias) {
    for (const b of otras) {
      for (const q of Osnap.interseccion(a, b)) {
        let k = 0, d0 = Infinity;
        tramos.forEach((tr, i) => { const d = _distTramo(tr, q); if (d < d0) { d0 = d; k = i; } });
        const t = _paramEnTramo(tramos[k], q);
        if (t > -1e-9 && t < 1 + 1e-9) posiciones.push({ k, t: Math.max(0, Math.min(1, t)) });
      }
    }
  }
  if (!posiciones.length) return Comandos.eco("Esa polilínea no cruza con ninguna otra entidad: no hay dónde recortar.", "malo");
  const orden = (a, b) => a.k - b.k || a.t - b.t;
  posiciones.sort(orden);
  const antes = posiciones.filter((q) => orden(q, pick) < 0);
  const despues = posiciones.filter((q) => orden(q, pick) > 0);
  let prev = antes.length ? antes[antes.length - 1] : null;
  let next = despues.length ? despues[0] : null;
  if (cerrada) {
    if (!prev) prev = posiciones[posiciones.length - 1];   // da la vuelta
    if (!next) next = posiciones[0];
    if (orden(prev, next) === 0) return Comandos.eco("Una polilínea cerrada necesita dos cruces para quitarle un trozo.", "malo");
    const puntos = _pedazo(tramos, next, prev, true);
    await aplicarOperacion({ accion: "Recortar polilínea", cambios: { [ent.id]: { puntos, cerrada: false } } });
    return;
  }
  if (!prev && !next) return Comandos.eco("El trozo que señalaste no está entre cruces.", "malo");
  const ini = { k: 0, t: 0 }, fin = { k: m - 1, t: 1 };
  if (prev && next) {
    // el trozo está en medio: quedan dos polilíneas
    const a = _pedazo(tramos, ini, prev, false);
    const b = _pedazo(tramos, next, fin, false);
    await aplicarOperacion({
      accion: "Recortar polilínea",
      cambios: { [ent.id]: { puntos: a, cerrada: false } },
      agregar: [{ ...ent, id: undefined, puntos: b, cerrada: false }],
    });
  } else if (next) {
    await aplicarOperacion({ accion: "Recortar polilínea", cambios: { [ent.id]: { puntos: _pedazo(tramos, next, fin, false), cerrada: false } } });
  } else {
    await aplicarOperacion({ accion: "Recortar polilínea", cambios: { [ent.id]: { puntos: _pedazo(tramos, ini, prev, false), cerrada: false } } });
  }
}

function alargada(pr) {
  if (pr.tipo !== "seg") return pr;
  const dx = pr.b[0] - pr.a[0], dy = pr.b[1] - pr.a[1];
  const L = Math.hypot(dx, dy) || 1;
  const k = 1e6 / L;
  return { ...pr, a: [pr.a[0] - dx * k, pr.a[1] - dy * k],
                  b: [pr.b[0] + dx * k, pr.b[1] + dy * k] };
}

Comandos.registrar({ nombre: "RECORTAR", alias: ["RC", "TR"],
  ayuda: "Quita el trozo de línea, arco o polilínea que señales", correr: () => recortarOExtender(false) });
Comandos.registrar({ nombre: "EXTENDER", alias: ["EXT", "EX"],
  ayuda: "Alarga una línea hasta lo primero que encuentre", correr: () => recortarOExtender(true) });

/* ===================================================================== */
/* 39 · Empalme y chaflán                                                */
/* ===================================================================== */
function rectaInfinita(ent) {
  return { tipo: "seg",
           a: [ent.p1[0] - (ent.p2[0] - ent.p1[0]) * 1e4, ent.p1[1] - (ent.p2[1] - ent.p1[1]) * 1e4],
           b: [ent.p2[0] + (ent.p2[0] - ent.p1[0]) * 1e4, ent.p2[1] + (ent.p2[1] - ent.p1[1]) * 1e4] };
}

async function dosLineas(mensaje) {
  const id1 = await Seleccion.pedirUna({ mensaje: mensaje + " — primera línea",
    filtro: (e) => e.tipo === "linea", queja: "Tiene que ser una línea." });
  const id2 = await Seleccion.pedirUna({ mensaje: mensaje + " — segunda línea",
    filtro: (e) => e.tipo === "linea", queja: "Tiene que ser una línea." });
  if (id1 === id2) { Comandos.eco("Son la misma línea.", "malo"); return null; }
  const [a, b] = await traer([id1, id2]);
  const cruces = Osnap.interseccion(rectaInfinita(a), rectaInfinita(b));
  if (!cruces.length) { Comandos.eco("Las dos líneas son paralelas.", "malo"); return null; }
  return { a, b, esquina: cruces[0] };
}

/** Deja en cada línea el extremo más lejano a la esquina, y devuelve
 *  la dirección desde la esquina hacia ese extremo. */
function ladoLibre(ent, esquina) {
  const d1 = Math.hypot(ent.p1[0] - esquina[0], ent.p1[1] - esquina[1]);
  const d2 = Math.hypot(ent.p2[0] - esquina[0], ent.p2[1] - esquina[1]);
  const lejos = d1 >= d2 ? ent.p1 : ent.p2;
  const campo = d1 >= d2 ? "p2" : "p1";
  const L = Math.hypot(lejos[0] - esquina[0], lejos[1] - esquina[1]) || 1;
  return { campo, dir: [(lejos[0] - esquina[0]) / L, (lejos[1] - esquina[1]) / L] };
}

Comandos.registrar({
  nombre: "EMPALME", alias: ["EM", "F"],
  ayuda: "Redondea la esquina entre dos líneas con un radio",
  correr: async () => {
    const r = await Entrada.pedirNumero({ mensaje: "Radio del empalme", valor: 0, minimo: 0 });
    const d = await dosLineas("Empalme");
    if (!d) return;
    const la = ladoLibre(d.a, d.esquina), lb = ladoLibre(d.b, d.esquina);
    if (r < 1e-9) {
      // radio 0 = simplemente juntarlas en la esquina
      await aplicarOperacion({ accion: "Empalme",
        cambios: { [d.a.id]: { [la.campo]: d.esquina }, [d.b.id]: { [lb.campo]: d.esquina } } });
      return Comandos.eco("Esquina a escuadra.");
    }
    // La tangente cae a distancia r / tan(mitad del ángulo) de la esquina.
    const cos = la.dir[0] * lb.dir[0] + la.dir[1] * lb.dir[1];
    const ang = Math.acos(Math.max(-1, Math.min(1, cos)));
    if (ang < 1e-6 || Math.abs(ang - Math.PI) < 1e-6) {
      return Comandos.eco("Las líneas están alineadas: no hay esquina que redondear.", "malo");
    }
    const t = r / Math.tan(ang / 2);
    const pa = [d.esquina[0] + la.dir[0] * t, d.esquina[1] + la.dir[1] * t];
    const pb = [d.esquina[0] + lb.dir[0] * t, d.esquina[1] + lb.dir[1] * t];
    // centro del arco: sobre la bisectriz
    const bis = [la.dir[0] + lb.dir[0], la.dir[1] + lb.dir[1]];
    const Lb = Math.hypot(bis[0], bis[1]) || 1;
    const dc = r / Math.sin(ang / 2);
    const c = [d.esquina[0] + bis[0] / Lb * dc, d.esquina[1] + bis[1] / Lb * dc];
    const angA = (deg(Math.atan2(pa[1] - c[1], pa[0] - c[0])) + 360) % 360;
    const angB = (deg(Math.atan2(pb[1] - c[1], pb[0] - c[0])) + 360) % 360;
    const barrido = (angB - angA + 360) % 360;
    await aplicarOperacion({
      accion: "Empalme",
      cambios: { [d.a.id]: { [la.campo]: pa }, [d.b.id]: { [lb.campo]: pb } },
      agregar: [{ tipo: "arco", centro: c, radio: r,
                  ang_ini: barrido <= 180 ? angA : angB,
                  ang_fin: barrido <= 180 ? angB : angA,
                  capa: d.a.capa }],
    });
    Comandos.eco(`Empalme de radio ${mm(r)} ${U()}.`);
  },
});

Comandos.registrar({
  nombre: "CHAFLAN", alias: ["CH", "CHA"],
  ayuda: "Corta la esquina entre dos líneas a una distancia",
  correr: async () => {
    const d1 = await Entrada.pedirNumero({ mensaje: "Distancia por la primera línea", minimo: 1e-6 });
    const d2 = await Entrada.pedirNumero({ mensaje: "Distancia por la segunda", valor: d1, minimo: 1e-6, recordar: false });
    const d = await dosLineas("Chaflán");
    if (!d) return;
    const la = ladoLibre(d.a, d.esquina), lb = ladoLibre(d.b, d.esquina);
    const pa = [d.esquina[0] + la.dir[0] * d1, d.esquina[1] + la.dir[1] * d1];
    const pb = [d.esquina[0] + lb.dir[0] * d2, d.esquina[1] + lb.dir[1] * d2];
    await aplicarOperacion({
      accion: "Chaflán",
      cambios: { [d.a.id]: { [la.campo]: pa }, [d.b.id]: { [lb.campo]: pb } },
      agregar: [{ tipo: "linea", p1: pa, p2: pb, capa: d.a.capa }],
    });
    Comandos.eco(`Chaflán ${mm(d1)} × ${mm(d2)} ${U()}.`);
  },
});

/* ===================================================================== */
/* 40 · Arreglo rectangular y polar                                      */
/* ===================================================================== */
Comandos.registrar({
  nombre: "ARREGLO", alias: ["AR"],
  ayuda: "ARREGLO [R rectangular · P polar]",
  correr: async (args) => {
    const ids = await Seleccion.pedir({ mensaje: "Selecciona lo que se repite" });
    if (!ids.length) return;
    const modo = ((args[0] || await Entrada.pedirTexto({
      mensaje: "¿Rectangular o Polar? R/P", valor: "R" })) || "R").toUpperCase();

    if (modo.startsWith("P")) {
      const c = await Entrada.pedirPunto({ mensaje: "Centro del arreglo" });
      const n = Math.round(await Entrada.pedirNumero({ mensaje: "¿Cuántas copias en total?", valor: 6, minimo: 2 }));
      const total = await Entrada.pedirNumero({ mensaje: "Ángulo a cubrir", valor: 360 });
      const paso = total / (Math.abs(total - 360) < 1e-9 ? n : n - 1);
      const ents = await traer(ids);
      const agregar = [];
      for (let i = 1; i < n; i++) {
        const t = T.rotar(c, paso * i);
        for (const ent of ents) {
          const cambios = transformar(ent, t);
          if (cambios) agregar.push({ ...ent, ...cambios, id: undefined });
        }
      }
      await aplicarOperacion({ accion: `Arreglo polar ×${n}`, agregar });
      Comandos.eco(`${agregar.length} copia(s) alrededor del centro.`);
    } else {
      const filas = Math.round(await Entrada.pedirNumero({ mensaje: "Filas", valor: 2, minimo: 1 }));
      const cols = Math.round(await Entrada.pedirNumero({ mensaje: "Columnas", valor: 2, minimo: 1 }));
      const dy = await Entrada.pedirNumero({ mensaje: "Separación entre filas", valor: 100 });
      const dx = await Entrada.pedirNumero({ mensaje: "Separación entre columnas", valor: 100 });
      const ents = await traer(ids);
      const agregar = [];
      for (let f = 0; f < filas; f++) {
        for (let c = 0; c < cols; c++) {
          if (!f && !c) continue;
          const t = T.mover(dx * c, dy * f);
          for (const ent of ents) {
            const cambios = transformar(ent, t);
            if (cambios) agregar.push({ ...ent, ...cambios, id: undefined });
          }
        }
      }
      await aplicarOperacion({ accion: `Arreglo ${filas}×${cols}`, agregar });
      Comandos.eco(`${agregar.length} copia(s) en ${filas} × ${cols}.`);
    }
    Seleccion.limpiar();
  },
});

/* ===================================================================== */
/* 41 · Estirar                                                          */
/* ===================================================================== */
/* Estirar es lo que hace que un mueble se pueda hacer más ancho sin volver a
 * dibujarlo: se agarra por cruce sólo un lado, y se mueven **los vértices que
 * quedaron dentro** de la ventana, no las entidades completas. Lo que quedó
 * entero dentro se mueve entero; lo que quedó a medias se estira. */
Comandos.registrar({
  nombre: "ESTIRAR", alias: ["ET", "S"],
  ayuda: "Estira lo que agarres por cruce (de derecha a izquierda)",
  correr: async () => {
    const a = await Entrada.pedirPunto({ mensaje: "Primera esquina de la ventana de cruce" });
    const b = await Entrada.pedirPunto({
      mensaje: "Esquina opuesta", base: a,
      hule: (q) => ({ tipo: "caja", a, b: q, punteado: true }),
    });
    const caja = [Math.min(a[0], b[0]), Math.min(a[1], b[1]),
                  Math.max(a[0], b[0]), Math.max(a[1], b[1])];
    const dentro = (p) => p[0] >= caja[0] && p[0] <= caja[2] && p[1] >= caja[1] && p[1] <= caja[3];

    const ids = [...new Set(estado.geometria
      .filter((pr) => {
        const c = Osnap.caja(pr);
        return !(c[2] < caja[0] || c[0] > caja[2] || c[3] < caja[1] || c[1] > caja[3]);
      }).map((pr) => pr.id))];
    if (!ids.length) return Comandos.eco("La ventana no tocó nada.", "malo");

    const base = await Entrada.pedirPunto({ mensaje: "Punto base del estirón" });
    const dest = await Entrada.pedirPunto({
      mensaje: "Destino", base,
      hule: (q) => ({ partes: [{ tipo: "caja", a, b, punteado: true },
                               { tipo: "linea", a: base, b: q }] }),
    });
    const dx = dest[0] - base[0], dy = dest[1] - base[1];
    const mover = (p) => (dentro(p) ? [p[0] + dx, p[1] + dy] : [p[0], p[1]]);

    const ents = await traer(ids);
    const cambios = {};
    for (const ent of ents) {
      if (ent.tipo === "linea") {
        const p1 = mover(ent.p1), p2 = mover(ent.p2);
        if (p1[0] !== ent.p1[0] || p1[1] !== ent.p1[1] ||
            p2[0] !== ent.p2[0] || p2[1] !== ent.p2[1]) cambios[ent.id] = { p1, p2 };
      } else if (ent.tipo === "polilinea") {
        let toco = false;
        const puntos = ent.puntos.map((v) => {
          const q = mover([v[0], v[1]]);
          if (q[0] !== v[0] || q[1] !== v[1]) toco = true;
          return [q[0], q[1], v[2] || 0];
        });
        if (toco) cambios[ent.id] = { puntos };
      } else {
        // Las figuras que no tienen vértices se mueven enteras si su punto de
        // referencia cayó dentro; estirar un círculo no significa nada.
        const ref = ent.centro || ent.p || (ent.puntos && ent.puntos[0]);
        if (ref && dentro([ref[0], ref[1]])) {
          const c = transformar(ent, T.mover(dx, dy));
          if (c) cambios[ent.id] = c;
        }
      }
    }
    const n = Object.keys(cambios).length;
    if (!n) return Comandos.eco("Nada quedó dentro de la ventana.", "malo");
    await aplicarOperacion({ accion: "Estirar", cambios });
    Comandos.eco(`${n} entidad(es) estiradas ΔX ${mm(dx)}, ΔY ${mm(dy)}.`);
    Seleccion.limpiar();
  },
});

/* ===================================================================== */
/* 44 · Igualar propiedades                                              */
/* ===================================================================== */
Comandos.registrar({
  nombre: "IGUALAR", alias: ["IG", "MA"],
  ayuda: "Copia capa, color, grosor y tipo de línea de una entidad a otras",
  correr: async () => {
    const modelo = await Seleccion.pedirUna({ mensaje: "Entidad de la que se copian las propiedades" });
    const fuente = await api(`/api/entidad/${modelo}`);
    Seleccion.limpiar();
    const ids = await Seleccion.pedir({ mensaje: "Entidades que van a igualarse" });
    if (!ids.length) return;
    const props = {
      capa: fuente.capa, color: fuente.color,
      grosor: fuente.grosor, tipo_linea: fuente.tipo_linea,
      escala_tl: fuente.escala_tl,
    };
    const cambios = {};
    for (const id of ids) if (id !== modelo) cambios[id] = { ...props };
    await aplicarOperacion({ accion: `Igualar ${Object.keys(cambios).length}`, cambios });
    Comandos.eco(`${Object.keys(cambios).length} entidad(es) igualadas a la capa «${fuente.capa}».`);
    Seleccion.limpiar();
  },
});


/* ===================================================================== */
/* Unir  ·  varias líneas y arcos en una sola polilínea                  */
/* ===================================================================== */
Comandos.registrar({
  nombre: "UNIR", alias: ["J", "UN", "JOIN"],
  ayuda: "Une líneas, arcos y polilíneas que se tocan en una sola polilínea",
  correr: async () => {
    const ids = await Seleccion.pedir({
      mensaje: "Selecciona lo que se une (líneas, arcos, polilíneas)" });
    if (ids.length < 2) {
      return Comandos.eco("Hacen falta al menos dos para unir.", "malo");
    }
    const r = await post("/api/unir", { ids });
    aplicar(r);
    if (!aplicarParche(r)) await recargarTrazos();
    Seleccion.limpiar();

    if (!r.creadas.length) {
      // Decir *por qué* no se unió, no sólo que no se unió: casi siempre es
      // que los extremos no se tocan de verdad, y eso se arregla con osnap.
      const porque = r.no_unibles.length
        ? ` No se pueden unir: ${[...new Set(r.no_unibles)].join(", ")}.`
        : " Sus extremos no se tocan; acércalos con las referencias a objetos.";
      return Comandos.eco("No se unió nada." + porque, "malo");
    }
    const total = r.creadas.reduce((a, c) => a + c.de, 0);
    const cerradas = r.creadas.filter((c) => c.cerrada).length;
    let msg = `${total} entidades → ${r.creadas.length} polilínea(s)`;
    if (cerradas) msg += `, ${cerradas} cerrada(s)`;
    if (r.sueltas) msg += `. ${r.sueltas} quedó/quedaron fuera: no tocaban`;
    Comandos.eco(msg + ".");
  },
});

/* ===================================================================== */
/* Grupos y EXPLOTAR  ·  lo pidió Mike el 4-sep                          */
/* ===================================================================== */
/* GRUPO junta lo seleccionado para que se agarre de un clic; DESAGRUPAR lo
 * suelta; EXPLOTAR deshace lo compuesto —un bloque, una polilínea, un rayado,
 * una cota o una entidad ajena— en sus partes, en su sitio. Ver
 * `core/agrupar.py`. Los tres son una sola acción en el historial. */
async function _aplicarGrupo(ruta, ids, accion) {
  const r = await post(ruta, { ids });
  aplicar(r);
  if (!aplicarParche(r)) await recargarTrazos();
  return r;
}

Comandos.registrar({
  nombre: "GRUPO", alias: ["G", "AGRUPAR", "GROUP"],
  ayuda: "Agrupa lo seleccionado: picar uno es picar todos (Ctrl+G)",
  correr: async () => {
    const ids = await Seleccion.pedir({ mensaje: "Selecciona lo que se agrupa" });
    if (ids.length < 2) return Comandos.eco("Un grupo necesita al menos dos entidades.", "malo");
    const r = await _aplicarGrupo("/api/grupo", ids);
    estado.sel = new SelSet(r.ids);
    Seleccion.refrescar();
    Comandos.eco(`Grupo «${r.grupo}» con ${r.ids.length} entidades. ` +
                 "Alt+clic pica una sola; DESAGRUPAR lo deshace.");
  },
});

Comandos.registrar({
  nombre: "DESAGRUPAR", alias: ["DG", "UNGROUP"],
  ayuda: "Deshace el grupo de lo seleccionado (Ctrl+Shift+G)",
  correr: async () => {
    const ids = await Seleccion.pedir({ mensaje: "Selecciona algo del grupo" });
    if (!ids.length) return;
    const r = await _aplicarGrupo("/api/desagrupar", ids);
    Seleccion.limpiar();
    Comandos.eco(r.ids.length ? `${r.ids.length} entidades sueltas.`
                              : "Nada de eso estaba en un grupo.");
  },
});

Comandos.registrar({
  nombre: "EXPLOTAR", alias: ["X", "EXPLODE", "DESCOMPONER"],
  ayuda: "Deshace bloques, polilíneas, rayados, cotas y entidades ajenas en sus partes",
  correr: async () => {
    const ids = await Seleccion.pedir({ mensaje: "Selecciona lo que se explota" });
    if (!ids.length) return;
    const r = await _aplicarGrupo("/api/explotar", ids);
    estado.sel = new SelSet(r.nuevos || []);
    Seleccion.refrescar();
    const partes = [];
    if (r.quitados.length) partes.push(`${r.quitados.length} explotada(s) en ${r.nuevos.length} partes`);
    if (r.dejadas.length) {
      const tipos = [...new Set(r.dejadas.map((d) => d[1]))].join(", ");
      partes.push(`${r.dejadas.length} se quedaron como estaban (${tipos}: no tienen partes)`);
    }
    Comandos.eco(partes.join(" · ") + ".");
  },
});
