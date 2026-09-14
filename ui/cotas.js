/* Herramientas de cota  ·  features 50 a 59.
 *
 * Una cota se guarda por lo que **mide**, no por lo que se ve: los puntos de
 * origen y el estilo. El dibujo lo calcula el motor (`core/cotas.py`) cada vez.
 * Por eso cambiar la altura del texto en el estilo cambia las doscientas cotas
 * del plano de un golpe, y mover la pieza mueve su cota.
 *
 * La asociatividad (feature 58) se arma aquí: cuando el punto se tomó con una
 * referencia a objeto, se apunta **de qué entidad y de qué parte suya** salió.
 * Sin ese apunte la cota sería una foto del día que se dibujó.
 */

/* --- Asociatividad: de qué parte de qué entidad salió este punto -------- */
/* Se pregunta al servidor por la entidad y se compara: si el punto coincide
 * con su p1, su centro o su tercer vértice, eso es lo que la cota va a seguir.
 * Comparar en vez de suponer evita el error de pegar la cota al vértice
 * equivocado cuando dos caen encima. */
async function ligaDe(punto, ref) {
  if (!ref || !ref.id) return null;
  let ent;
  try { ent = await api(`/api/entidad/${ref.id}`); } catch (_) { return null; }
  const igual = (p) => p && Math.hypot(p[0] - punto[0], p[1] - punto[1]) < 1e-6;

  for (const campo of ["p1", "p2", "centro", "p"]) {
    if (igual(ent[campo])) return { id: ent.id, campo, indice: null };
  }
  if (Array.isArray(ent.puntos)) {
    for (let i = 0; i < ent.puntos.length; i++) {
      if (igual([ent.puntos[i][0], ent.puntos[i][1]])) {
        return { id: ent.id, campo: "puntos", indice: i };
      }
    }
  }
  // Un punto medio o una intersección no son "una parte" de nada que se pueda
  // seguir: la cota se queda quieta ahí, y es lo honesto.
  return null;
}

/** Pide un punto y, de paso, apunta a qué se enganchó. */
async function puntoConLiga(opciones) {
  const p = await Entrada.pedirPunto(opciones);
  if (!Array.isArray(p)) return { p, liga: null };
  const liga = await ligaDe(p, estado.ref);
  return { p, liga };
}

/* En qué capa cae una cota **no lo decide la interfaz**: lo decide el motor,
 * que las manda todas a la capa COTAS sin importar en cuál se esté trabajando.
 * Ver `core/cotas.py`. Aquí no se pone `capa` a propósito — si se pusiera,
 * habría dos sitios donde se decide lo mismo y tarde o temprano dirían cosas
 * distintas. */
async function crearCota(datos, accion) {
  return crearEntidad({ estilo: "T101", ...datos }, accion);
}

/* ===================================================================== */
/* La previa de una cota: lo mismo que va a quedar, siguiendo al ratón       */
/* ===================================================================== */
/* Mike, 6-sep: *«cuando trazo una cota recta, en vez de líneas punteadas
 * directo al mouse, predibuja la cota. Que se vea la vista previa de cómo va
 * a quedar»*. Es la misma geometría que `_lineal` en core/cotas.py —líneas
 * de extensión con su hueco y su sobresalida, línea de cota, palomitas y la
 * cifra— calculada aquí para no ir al motor sesenta veces por segundo. El
 * estilo se pide una vez al arrancar la herramienta. */
let _estiloCota = null;
async function estiloCotaActual() {
  try {
    const r = await api("/api/estilos_cota");
    _estiloCota = { ...((r.estilos || {})[r.activo || "T101"] || {}) };
  } catch (_) { _estiloCota = _estiloCota || {}; }
  return _estiloCota;
}

function previaCotaLineal(p1, p2, q, ang, est) {
  est = est || {};
  // Sobre una hoja el estilo no se escala (ver core/cotas.py, `geometria`).
  const escala = estado.modo === "papel" ? 1 : (parseFloat(est.factor_escala) || 1);
  const r = ang * Math.PI / 180, d = [Math.cos(r), Math.sin(r)], n = [-d[1], d[0]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1];
  const sum = (a, b, k) => [a[0] + b[0] * k, a[1] + b[1] * k];
  const t1 = dot([p1[0] - q[0], p1[1] - q[1]], d), t2 = dot([p2[0] - q[0], p2[1] - q[1]], d);
  const q1 = sum(q, d, t1), q2 = sum(q, d, t2);
  const medida = Math.abs(t2 - t1);
  const hueco = (est.hueco_origen ?? 0.625) * escala, sobra = (est.ext_linea ?? 1.25) * escala;
  const partes = [];
  for (const [o, qq] of [[p1, q1], [p2, q2]]) {
    const v = [qq[0] - o[0], qq[1] - o[1]], l = Math.hypot(v[0], v[1]);
    if (l < 1e-9) continue;
    const u = [v[0] / l, v[1] / l];
    partes.push({ tipo: "linea", a: sum(o, u, hueco), b: sum(qq, u, sobra) });
  }
  partes.push({ tipo: "linea", a: q1, b: q2 });
  // palomitas (o flechas) hacia afuera
  const tam = (est.tam_flecha ?? 2.5) * escala, tipo = String(est.flecha || "ARCHTICK").toUpperCase();
  const signo = t2 >= t1 ? 1 : -1;
  for (const [pt, dir] of [[q1, [-d[0] * signo, -d[1] * signo]], [q2, [d[0] * signo, d[1] * signo]]]) {
    if (tipo === "ARCHTICK") {
      const c = Math.SQRT1_2, vx = dir[0] * c - dir[1] * c, vy = dir[0] * c + dir[1] * c;
      partes.push({ tipo: "linea", a: sum(pt, [vx, vy], -tam / 2), b: sum(pt, [vx, vy], tam / 2) });
    } else {
      const nx = -dir[1], ny = dir[0], base = sum(pt, dir, tam);
      const a = sum(base, [nx, ny], tam * 0.18), b = sum(base, [nx, ny], -tam * 0.18);
      partes.push({ tipo: "linea", a: pt, b: a }, { tipo: "linea", a, b }, { tipo: "linea", a: b, b: pt });
    }
  }
  // la cifra
  const altura = (est.altura_texto ?? 2.5) * escala;
  const medio = [(q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2];
  let angTexto = ((ang % 360) + 360) % 360;
  if (angTexto > 90 && angTexto <= 270) angTexto = (angTexto + 180) % 360;
  const fm = parseFloat(est.factor_medida) || 1;
  const dec = parseInt(est.decimales ?? 0, 10) || 0;
  const texto = (medida * fm).toFixed(dec) + (est.sufijo || "");
  partes.push({ tipo: "texto", p: sum(medio, n, altura * 0.45), texto, altura, rotacion: angTexto, alineacion: "CENTRO" });
  return { partes, punteado: false };
}

/* ===================================================================== */
/* 50 · Cota lineal    51 · Cota alineada                                */
/* ===================================================================== */
async function cotaLineal(clase, rotacionFija = null) {
  const est = await estiloCotaActual();
  return repetir(async () => {
    const a = await puntoConLiga({ mensaje: "Primer punto de la medida" });
    const b = await puntoConLiga({
      mensaje: "Segundo punto de la medida", base: a.p,
      hule: (q) => ({ tipo: "linea", a: a.p, b: q }),
    });
    let rot = rotacionFija;
    // Cota recta: **el tercer punto decide** si mide en X o en Y (Mike,
    // 9-sep-2026: «se queda atorada sobre X»). Como DIMLINEAR de AutoCAD: si
    // el ratón se aleja de los dos puntos en vertical, la cota es horizontal
    // (mide X); si se aleja en horizontal, es vertical (mide Y). La previa
    // cambia en vivo. COTAH y COTAV siguen forzadas.
    const rotDe = (q) => {
      if (rot !== null) return rot;
      const dx = q[0] - (a.p[0] + b.p[0]) / 2, dy = q[1] - (a.p[1] + b.p[1]) / 2;
      // Con los dos puntos alineados en un eje no hay duda: se mide el otro.
      if (Math.abs(b.p[0] - a.p[0]) < 1e-9) return 90;
      if (Math.abs(b.p[1] - a.p[1]) < 1e-9) return 0;
      return Math.abs(dy) >= Math.abs(dx) ? 0 : 90;
    };
    const angPrevia = (q) => clase === "alineada"
      ? Math.atan2(b.p[1] - a.p[1], b.p[0] - a.p[0]) * 180 / Math.PI : rotDe(q);
    // Con osnap sobre las líneas de cota de otras cotas (Mike, 9-sep): así
    // una fila de cotas cae en el mismo renglón sin tantear.
    const pl = await Entrada.pedirPunto({
      mensaje: "¿Dónde va la línea de cota?", osnapCotas: true,
      hule: (q) => previaCotaLineal(a.p, b.p, q, angPrevia(q), est),
    });
    if (clase === "lineal") rot = rotDe(pl);
    await crearCota({
      tipo: "cota", clase, puntos: [a.p, b.p, pl],
      rotacion: clase === "lineal" ? rot : 0,
      liga: [a.liga, b.liga, null],
    }, "Cota");
    Comandos.eco("Cota puesta." + (a.liga || b.liga ? " Sigue a la pieza." : ""));
  });
}

Comandos.registrar({
  nombre: "COTA", alias: ["CO_", "DIMLIN"],
  ayuda: "Cota lineal (horizontal o vertical según los puntos)",
  correr: () => cotaLineal("lineal"),
});
Comandos.registrar({
  nombre: "COTAH", ayuda: "Cota horizontal forzada",
  correr: () => cotaLineal("lineal", 0),
});
Comandos.registrar({
  nombre: "COTAV", ayuda: "Cota vertical forzada",
  correr: () => cotaLineal("lineal", 90),
});
Comandos.registrar({
  nombre: "COTAALINEADA", alias: ["CAL", "DAL"],
  ayuda: "Cota paralela al segmento medido",
  correr: () => cotaLineal("alineada"),
});

/* ===================================================================== */
/* 52 · Cota continua y línea base                                       */
/* ===================================================================== */
/* Las dos encadenan cotas a partir de la última: la continua arranca donde
 * terminó la anterior, la de línea base repite siempre el mismo origen. Son las
 * que hacen legible una fila de gabinetes; ponerlas a mano una por una es donde
 * se cuelan los errores de suma. */
async function cadena(desdeBase) {
  const a = await puntoConLiga({ mensaje: "Origen de la cadena" });
  const b = await puntoConLiga({
    mensaje: "Primer punto", base: a.p,
    hule: (q) => ({ tipo: "linea", a: a.p, b: q }),
  });
  const rot = Math.abs(b.p[0] - a.p[0]) >= Math.abs(b.p[1] - a.p[1]) ? 0 : 90;
  const est = await estiloCotaActual();
  const pl = await Entrada.pedirPunto({ mensaje: "¿Dónde va la línea de cota?", osnapCotas: true,
                                        hule: (q) => previaCotaLineal(a.p, b.p, q, rot, est) });
  await crearCota({ tipo: "cota", clase: "lineal", puntos: [a.p, b.p, pl],
                    rotacion: rot, liga: [a.liga, b.liga, null] }, "Cota");

  let anterior = b, n = 1;
  const salto = (rot === 0 ? Math.abs(pl[1] - a.p[1]) : Math.abs(pl[0] - a.p[0]));
  try {
    while (true) {
      const c = await puntoConLiga({
        mensaje: `Siguiente punto (${desdeBase ? "línea base" : "continua"})`,
        base: anterior.p,
        hule: (q) => ({ tipo: "linea", a: (desdeBase ? a.p : anterior.p), b: q }),
      });
      const origen = desdeBase ? a : anterior;
      // Cada cota de línea base se separa un escalón más, o quedarían todas
      // encimadas sobre la misma raya.
      const paso = desdeBase ? (n * (rot === 0 ? 1 : 1)) : 0;
      const linea = rot === 0
        ? [pl[0], pl[1] + Math.sign(pl[1] - a.p[1] || 1) * paso * salto * 0.6]
        : [pl[0] + Math.sign(pl[0] - a.p[0] || 1) * paso * salto * 0.6, pl[1]];
      await crearCota({ tipo: "cota", clase: "lineal",
                        puntos: [origen.p, c.p, linea], rotacion: rot,
                        liga: [origen.liga, c.liga, null] }, "Cota");
      anterior = c;
      n++;
    }
  } catch (err) {
    if (err.message !== "cancelado") throw err;
  }
  Comandos.eco(`Cadena de ${n} cota(s).`);
}

Comandos.registrar({ nombre: "COTACONTINUA", alias: ["CC", "DCO"],
  ayuda: "Cotas encadenadas una tras otra", correr: () => cadena(false) });
Comandos.registrar({ nombre: "COTABASE", alias: ["CB", "DBA"],
  ayuda: "Cotas desde un mismo origen", correr: () => cadena(true) });

/* ===================================================================== */
/* 53 · Cota angular                                                     */
/* ===================================================================== */
Comandos.registrar({
  nombre: "COTAANGULAR", alias: ["CAN", "DAN"],
  ayuda: "Mide el ángulo entre dos direcciones",
  correr: () => repetir(async () => {
    const v = await puntoConLiga({ mensaje: "Vértice del ángulo" });
    const p1 = await Entrada.pedirPunto({ mensaje: "Punto del primer lado", base: v.p,
      hule: (q) => ({ tipo: "linea", a: v.p, b: q }) });
    const p2 = await Entrada.pedirPunto({ mensaje: "Punto del segundo lado", base: v.p,
      hule: (q) => ({ partes: [{ tipo: "linea", a: v.p, b: p1 },
                               { tipo: "linea", a: v.p, b: q }] }) });
    const pa = await Entrada.pedirPunto({ mensaje: "¿Por dónde pasa el arco?" });
    await crearCota({ tipo: "cota", clase: "angular", puntos: [v.p, p1, p2, pa],
                      liga: [v.liga, null, null, null] }, "Cota angular");
  }),
});

/* ===================================================================== */
/* 54 · Radio y diámetro                                                 */
/* ===================================================================== */
async function cotaRadial(clase) {
  return repetir(async () => {
    const id = await Seleccion.pedirUna({
      mensaje: `Elige el círculo o arco a acotar`,
      filtro: (e) => ["circulo", "arco"].includes(e.tipo),
      queja: "El radio y el diámetro se miden sobre círculos y arcos.",
    });
    const ent = await api(`/api/entidad/${id}`);
    const p = await Entrada.pedirPunto({ mensaje: "¿Hacia dónde sale la cota?" });
    const v = [p[0] - ent.centro[0], p[1] - ent.centro[1]];
    const L = Math.hypot(v[0], v[1]) || 1;
    const borde = [ent.centro[0] + v[0] / L * ent.radio,
                   ent.centro[1] + v[1] / L * ent.radio];
    await crearCota({ tipo: "cota", clase, puntos: [ent.centro, borde],
                      liga: [{ id, campo: "centro", indice: null }, null] },
                    clase === "radio" ? "Cota de radio" : "Cota de diámetro");
    Seleccion.limpiar();
  });
}

Comandos.registrar({ nombre: "COTARADIO", alias: ["CR", "DRA"],
  ayuda: "Acota el radio de un círculo o arco", correr: () => cotaRadial("radio") });
Comandos.registrar({ nombre: "COTADIAMETRO", alias: ["CD", "DDI"],
  ayuda: "Acota el diámetro de un círculo", correr: () => cotaRadial("diametro") });

/* ===================================================================== */
/* 55 · Directriz con texto                                              */
/* ===================================================================== */
Comandos.registrar({
  nombre: "DIRECTRIZ", alias: ["DIR", "LE"],
  ayuda: "Flecha con una nota al final",
  correr: async () => {
    const a = await Entrada.pedirPunto({ mensaje: "¿A qué apunta?" });
    const b = await Entrada.pedirPunto({ mensaje: "Codo de la flecha", base: a,
      hule: (q) => ({ tipo: "linea", a, b: q }) });
    const c = await Entrada.pedirPunto({ mensaje: "Final de la directriz", base: b,
      hule: (q) => ({ partes: [{ tipo: "linea", a, b }, { tipo: "linea", a: b, b: q }] }) });
    const texto = await Entrada.pedirTexto({ mensaje: "Nota" });
    if (!texto) return Comandos.eco("Sin nota: no se creó la directriz.");
    await crearCota({ tipo: "cota", clase: "directriz", puntos: [a, b, c],
                      texto, liga: [null, null, null] }, "Directriz");
  },
});

/* ===================================================================== */
/* 56 · Estilo de cota    59 · Escala                                    */
/* ===================================================================== */
/* El estilo de cota se toca en un cuadro, no preguntando campo por campo:
 * ver ui/ajustes.js. Aquí sólo queda la nota de dónde vive, porque es lo
 * primero que uno busca al abrir este archivo. */
