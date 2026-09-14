/* Herramientas de dibujo  ·  features 18 a 28.
 *
 * Cada una es corta porque el trabajo pesado ya lo hizo F1: pedir un punto con
 * referencia a objeto, ortho, coordenadas tecleadas y entrada dinámica es una
 * sola llamada. Lo que queda aquí es la conversación con el usuario —qué se
 * pregunta, en qué orden— y la geometría de cada figura.
 *
 * Dos costumbres de AutoCAD que se respetan porque el que dibuja las tiene en
 * los dedos:
 *
 *   · La herramienta **no se acaba en la primera figura**: línea sigue pidiendo
 *     puntos hasta que le dicen Escape. Dibujar veinte líneas son veinte clics,
 *     no veinte veces «L».
 *   · Cada figura terminada es **una** entrada del historial. Un Ctrl+Z borra el
 *     rectángulo completo, no un lado.
 */

/* --- Utilidades comunes ------------------------------------------------- */

async function crearEntidad(entidad, accion) {
  const r = await post("/api/entidad", { entidad, accion });
  aplicar(r);
  if (!aplicarParche(r)) await recargarTrazos();
  return r.id;
}

async function crearVarias(entidades, accion) {
  const r = await post("/api/entidades", { entidades, accion });
  aplicar(r);
  if (!aplicarParche(r)) await recargarTrazos();
  return r.ids;
}

const dist2 = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);
const angulo = (a, b) => Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;

/* Corre una herramienta una y otra vez hasta que el usuario la corta con
 * Escape. `hacer` devuelve algo si dibujó; si tira «cancelado», se acabó. */
async function repetir(hacer) {
  while (true) {
    try {
      await hacer();
    } catch (err) {
      if (err && err.message === "cancelado") return;
      throw err;
    }
  }
}

/* ===================================================================== */
/* 18 · Línea                                                            */
/* ===================================================================== */
Comandos.registrar({
  nombre: "LINEA", alias: ["L"],
  ayuda: "LINEA [M] — líneas encadenadas (Escape termina); con M, una línea dada por su punto medio",
  correr: async (args) => {
    if ((args[0] || "").toUpperCase() === "M") {
      // Por el punto medio, como en Rhino: el eje de un mueble se conoce por
      // su centro y su largo, no por dónde empieza.
      return repetir(async () => {
        const m = await Entrada.pedirPunto({ mensaje: "Punto medio de la línea" });
        const p = await Entrada.pedirPunto({
          mensaje: "Un extremo (o teclea el medio largo)", base: m, direccion: true,
          hule: (q) => ({ tipo: "linea", a: [2 * m[0] - q[0], 2 * m[1] - q[1]], b: q }),
        });
        if (dist2(m, p) < 1e-9) return Comandos.eco("Largo cero.", "malo");
        await crearEntidad({ tipo: "linea", p1: [2 * m[0] - p[0], 2 * m[1] - p[1]], p2: p }, "Línea");
        Comandos.eco(`Línea de ${mm(dist2(m, p) * 2)} ${U()}.`);
      });
    }
    let anterior = null;
    const hechas = [];
    try {
      anterior = await Entrada.pedirPunto({ mensaje: "Desde el punto" });
      while (true) {
        const p = await Entrada.pedirPunto({
          mensaje: "Al punto", base: anterior, direccion: true,
          hule: (q) => ({ tipo: "linea", a: anterior, b: q }),
        });
        hechas.push({ tipo: "linea", p1: anterior, p2: p });
        // Se manda al servidor tramo a tramo para que el dibujo se vea crecer;
        // cada tramo es su propia acción, como en AutoCAD.
        await crearEntidad({ tipo: "linea", p1: anterior, p2: p }, "Línea");
        anterior = p;
      }
    } catch (err) {
      if (err.message !== "cancelado") throw err;
      if (hechas.length) Comandos.eco(`${hechas.length} línea(s).`);
    }
  },
});

/* ===================================================================== */
/* 19 · Polilínea                                                        */
/* ===================================================================== */
Comandos.registrar({
  nombre: "POLILINEA", alias: ["PL"],
  ayuda: "Polilínea. Escribe C para cerrarla; Escape o Enter la termina.",
  correr: async () => {
    const puntos = [];
    const primero = await Entrada.pedirPunto({ mensaje: "Punto inicial" });
    puntos.push([primero[0], primero[1], 0]);
    let cerrada = false;
    try {
      while (true) {
        const p = await Entrada.pedirPunto({
          mensaje: "Siguiente punto (C cierra)",
          base: [puntos.at(-1)[0], puntos.at(-1)[1]],
          opciones: ["C"], direccion: true,
          hule: (q) => ({
            partes: [
              { tipo: "polilinea", puntos: puntos.map((v) => [v[0], v[1]]) },
              { tipo: "linea", a: [puntos.at(-1)[0], puntos.at(-1)[1]], b: q },
            ],
          }),
        });
        if (!Array.isArray(p)) { cerrada = true; break; }     // tecleó C
        puntos.push([p[0], p[1], 0]);
      }
    } catch (err) {
      if (err.message !== "cancelado") throw err;
    }
    if (puntos.length < 2) return Comandos.eco("Una polilínea necesita dos puntos.", "malo");
    await crearEntidad({ tipo: "polilinea", puntos, cerrada }, "Polilínea");
    Comandos.eco(`Polilínea de ${puntos.length} vértices${cerrada ? ", cerrada" : ""}.`);
  },
});

/* ===================================================================== */
/* 20 · Rectángulo                                                       */
/* ===================================================================== */
Comandos.registrar({
  nombre: "RECTANGULO", alias: ["REC", "RECT"],
  ayuda: "RECTANGULO [C · 3P · M] — dos esquinas; por el centro; tres puntos (girado); por medidas",
  correr: async (args) => repetir(async () => {
    const modo = (args[0] || "").toUpperCase();
    if (modo === "C") {
      // Por el centro: como Rhino. Un mueble se coloca por su eje la mitad de
      // las veces —centrado en un vano, en una pared— y desde la esquina hay
      // que restar la mitad de cabeza.
      const c = await Entrada.pedirPunto({ mensaje: "Centro del rectángulo" });
      const q = await Entrada.pedirPunto({
        mensaje: "Una esquina", base: c,
        hule: (p) => ({ tipo: "caja", a: [2 * c[0] - p[0], 2 * c[1] - p[1]], b: p }),
      });
      const a = [2 * c[0] - q[0], 2 * c[1] - q[1]];
      if (Math.abs(q[0] - a[0]) < 1e-9 || Math.abs(q[1] - a[1]) < 1e-9) return Comandos.eco("Un rectángulo de lado cero no se dibuja.", "malo");
      const puntos = [[a[0], a[1], 0], [q[0], a[1], 0], [q[0], q[1], 0], [a[0], q[1], 0]];
      await crearEntidad({ tipo: "polilinea", puntos, cerrada: true }, "Rectángulo");
      return Comandos.eco(`Rectángulo de ${mm(Math.abs(q[0] - a[0]))} × ${mm(Math.abs(q[1] - a[1]))} ${U()}.`);
    }
    if (modo === "3P") {
      // Tres puntos: un lado y la altura. Es el rectángulo girado, el de la
      // barra en diagonal o el mueble que sigue una pared que no es recta.
      const a = await Entrada.pedirPunto({ mensaje: "Primera esquina" });
      const b = await Entrada.pedirPunto({ mensaje: "Segunda esquina (el lado)", base: a, direccion: true,
                                           hule: (q) => ({ tipo: "linea", a, b: q }) });
      const L = dist2(a, b);
      if (L < 1e-9) return Comandos.eco("Lado cero.", "malo");
      const n = [-(b[1] - a[1]) / L, (b[0] - a[0]) / L];
      const esquinas = (q) => {
        const h = (q[0] - b[0]) * n[0] + (q[1] - b[1]) * n[1];
        return [[a[0], a[1], 0], [b[0], b[1], 0], [b[0] + n[0] * h, b[1] + n[1] * h, 0], [a[0] + n[0] * h, a[1] + n[1] * h, 0]];
      };
      const q = await Entrada.pedirPunto({
        mensaje: "Altura (o teclea la medida)", base: b,
        hule: (p) => ({ tipo: "polilinea", puntos: [...esquinas(p), [a[0], a[1]]] }),
      });
      const puntos = esquinas(q);
      const h = Math.hypot(puntos[2][0] - b[0], puntos[2][1] - b[1]);
      if (h < 1e-9) return Comandos.eco("Altura cero.", "malo");
      await crearEntidad({ tipo: "polilinea", puntos, cerrada: true }, "Rectángulo");
      return Comandos.eco(`Rectángulo de ${mm(L)} × ${mm(h)} ${U()}.`);
    }
    const a = await Entrada.pedirPunto({ mensaje: "Primera esquina" });
    if (modo === "M") {
      // Por medidas, directo: esquina y luego ancho y alto tecleados.
      const ancho = await Entrada.pedirNumero({ mensaje: "Ancho", minimo: 1e-6 });
      const alto = await Entrada.pedirNumero({ mensaje: "Alto", minimo: 1e-6 });
      const sx = estado.cursor.x < a[0] ? -1 : 1;
      const sy = estado.cursor.y < a[1] ? -1 : 1;
      const b = [a[0] + sx * Math.abs(ancho), a[1] + sy * Math.abs(alto)];
      const puntos = [[a[0], a[1], 0], [b[0], a[1], 0], [b[0], b[1], 0], [a[0], b[1], 0]];
      await crearEntidad({ tipo: "polilinea", puntos, cerrada: true }, "Rectángulo");
      return Comandos.eco(`Rectángulo de ${mm(Math.abs(ancho))} × ${mm(Math.abs(alto))} ${U()}.`);
    }

    /* Dos caminos, y ninguno más (Mike, 9-sep-2026):
     *
     *  · **A)** clic en la esquina opuesta, con la caja de goma siguiendo al
     *    ratón.
     *  · **B)** teclear el **ancho**, Enter, el **alto**, Enter — en la cajita
     *    dinámica (X / Y) o en la línea de comandos: si tras el origen se
     *    teclea un número, es el ancho; el siguiente, el alto. Crece hacia
     *    donde esté el cursor. Ver `Entrada.fijarLargo` (dinámica "xy").
     *
     * Sin opción M ni preguntas intermedias. Las otras formas (por el centro,
     * tres puntos, por medidas) siguen como argumento: REC C, REC 3P, REC M. */
    const b = await Entrada.pedirPunto({
      mensaje: "Esquina opuesta (o teclea ancho, Enter, alto, Enter)", base: a,
      hule: (q) => ({ tipo: "caja", a, b: q }),
      dinamica: "xy",
    });

    if (Math.abs(b[0] - a[0]) < 1e-9 || Math.abs(b[1] - a[1]) < 1e-9) {
      return Comandos.eco("Un rectángulo de lado cero no se dibuja.", "malo");
    }
    const puntos = [[a[0], a[1], 0], [b[0], a[1], 0], [b[0], b[1], 0], [a[0], b[1], 0]];
    await crearEntidad({ tipo: "polilinea", puntos, cerrada: true }, "Rectángulo");
    Comandos.eco(`Rectángulo de ${mm(Math.abs(b[0] - a[0]))} × ${mm(Math.abs(b[1] - a[1]))} ${U()}.`);
  }),
});

/* Polígono regular, como el POLYGON de AutoCAD: centro, número de lados y un
 * vértice (inscrito en ese círculo) o, con L, el punto medio de un lado
 * (circunscrito). Sale como polilínea cerrada, que es lo que es. */
Comandos.registrar({
  nombre: "POLIGONO", alias: ["POL", "POLYGON"],
  ayuda: "POLIGONO [lados] — polígono regular por centro y vértice (L: por el medio de un lado)",
  correr: async (args) => repetir(async () => {
    let n = parseInt(args[0], 10);
    if (!(n >= 3)) n = await Entrada.pedirNumero({ mensaje: "Número de lados", valor: 6, minimo: 3 });
    n = Math.max(3, Math.round(n));
    const c = await Entrada.pedirPunto({ mensaje: "Centro del polígono" });
    const vertices = (q, porLado) => {
      let r = dist2(c, q), ang0 = angDe(c, q) * Math.PI / 180;
      if (porLado) { r = r / Math.cos(Math.PI / n); ang0 += Math.PI / n; }
      const pts = [];
      for (let i = 0; i < n; i++) {
        const t = ang0 + i * 2 * Math.PI / n;
        pts.push([c[0] + r * Math.cos(t), c[1] + r * Math.sin(t), 0]);
      }
      return pts;
    };
    let porLado = false;
    let q = await Entrada.pedirPunto({
      mensaje: "Un vértice (o L para dar el punto medio de un lado)", base: c, opciones: ["L"],
      hule: (p) => ({ tipo: "polilinea", puntos: [...vertices(p, false), vertices(p, false)[0]] }),
    });
    if (!Array.isArray(q)) {
      porLado = true;
      q = await Entrada.pedirPunto({
        mensaje: "Punto medio de un lado", base: c,
        hule: (p) => ({ tipo: "polilinea", puntos: [...vertices(p, true), vertices(p, true)[0]] }),
      });
    }
    if (dist2(c, q) < 1e-9) return Comandos.eco("Radio cero.", "malo");
    const puntos = vertices(q, porLado);
    await crearEntidad({ tipo: "polilinea", puntos, cerrada: true }, "Polígono");
    Comandos.eco(`Polígono de ${n} lados, ${mm(Math.hypot(puntos[1][0] - puntos[0][0], puntos[1][1] - puntos[0][1]))} ${U()} por lado.`);
  }),
});

/* ===================================================================== */
/* 21 · Círculo                                                          */
/* ===================================================================== */
Comandos.registrar({
  nombre: "CIRCULO", alias: ["C"],
  ayuda: "CIRCULO [2P · 3P · D] — centro y radio; dos puntos del diámetro; tres puntos; centro y diámetro",
  correr: async (args) => repetir(async () => {
    const modo = (args[0] || "").toUpperCase();
    if (modo === "3P") {
      // Por tres puntos de la circunferencia: el círculo que pasa por tres
      // sitios concretos, sin saber dónde queda el centro.
      const a = await Entrada.pedirPunto({ mensaje: "Primer punto del círculo" });
      const b = await Entrada.pedirPunto({ mensaje: "Segundo punto", base: a,
                                           hule: (q) => ({ tipo: "linea", a, b: q }) });
      const c3 = await Entrada.pedirPunto({
        mensaje: "Tercer punto",
        hule: (q) => { const cc = circunscrito(a, b, q); return cc ? { tipo: "circulo", c: cc.centro, r: cc.radio } : { tipo: "linea", a, b }; },
      });
      const cc = circunscrito(a, b, c3);
      if (!cc) return Comandos.eco("Los tres puntos están en línea recta: no hay círculo.", "malo");
      await crearEntidad({ tipo: "circulo", centro: cc.centro, radio: cc.radio }, "Círculo");
      return Comandos.eco(`Círculo de ⌀${mm(cc.radio * 2)} ${U()}.`);
    }
    if (modo === "D") {
      // Centro y diámetro: lo que se teclea es el diámetro, que es la medida
      // que trae el catálogo de una tarja o de un bote de basura.
      const c = await Entrada.pedirPunto({ mensaje: "Centro del círculo" });
      const p = await Entrada.pedirPunto({
        mensaje: "Diámetro (o teclea la medida)", base: c,
        hule: (q) => ({ tipo: "circulo", c, r: dist2(c, q) / 2 }),
      });
      const r = dist2(c, p) / 2;
      if (r < 1e-9) return Comandos.eco("Diámetro cero.", "malo");
      await crearEntidad({ tipo: "circulo", centro: c, radio: r }, "Círculo");
      return Comandos.eco(`Círculo de ⌀${mm(r * 2)} ${U()}.`);
    }
    if (modo === "2P") {
      const a = await Entrada.pedirPunto({ mensaje: "Primer punto del diámetro" });
      const b = await Entrada.pedirPunto({
        mensaje: "Segundo punto del diámetro", base: a,
        hule: (q) => ({ tipo: "circulo", c: [(a[0] + q[0]) / 2, (a[1] + q[1]) / 2], r: dist2(a, q) / 2 }),
      });
      const r = dist2(a, b) / 2;
      if (r < 1e-9) return Comandos.eco("Radio cero.", "malo");
      await crearEntidad({ tipo: "circulo", centro: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], radio: r }, "Círculo");
      return Comandos.eco(`Círculo de ⌀${mm(r * 2)} ${U()}.`);
    }
    const c = await Entrada.pedirPunto({ mensaje: "Centro del círculo" });
    const p = await Entrada.pedirPunto({
      mensaje: "Radio (o teclea la medida)", base: c,
      hule: (q) => ({ tipo: "circulo", c, r: dist2(c, q) }),
    });
    const r = dist2(c, p);
    if (r < 1e-9) return Comandos.eco("Radio cero.", "malo");
    await crearEntidad({ tipo: "circulo", centro: c, radio: r }, "Círculo");
    Comandos.eco(`Círculo de ⌀${mm(r * 2)} ${U()}.`);
  }),
});

/* ===================================================================== */
/* 22 · Arco                                                             */
/* ===================================================================== */
/* Por tres puntos: inicio, un punto por el que pasa, y final. Es la forma que
 * más se usa en un plano de mueble —un arco que tiene que tocar tres sitios
 * concretos— y la única que no obliga a pensar en ángulos. */
function circunscrito(a, b, c) {
  const d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]));
  if (Math.abs(d) < 1e-12) return null;         // los tres en línea recta
  const ua = a[0] * a[0] + a[1] * a[1];
  const ub = b[0] * b[0] + b[1] * b[1];
  const uc = c[0] * c[0] + c[1] * c[1];
  const cx = (ua * (b[1] - c[1]) + ub * (c[1] - a[1]) + uc * (a[1] - b[1])) / d;
  const cy = (ua * (c[0] - b[0]) + ub * (a[0] - c[0]) + uc * (b[0] - a[0])) / d;
  return { centro: [cx, cy], radio: Math.hypot(a[0] - cx, a[1] - cy) };
}

function arcoPorTres(a, m, b) {
  const cc = circunscrito(a, m, b);
  if (!cc) return null;
  const ang = (p) => (Math.atan2(p[1] - cc.centro[1], p[0] - cc.centro[0]) * 180 / Math.PI + 360) % 360;
  const a0 = ang(a), am = ang(m), a1 = ang(b);
  // El arco va de a0 a a1 en sentido antihorario si el punto de en medio cae
  // dentro de ese barrido; si no, al revés — y entonces se intercambian.
  const dentro = ((am - a0 + 360) % 360) <= ((a1 - a0 + 360) % 360);
  return dentro
    ? { centro: cc.centro, radio: cc.radio, ang_ini: a0, ang_fin: a1 }
    : { centro: cc.centro, radio: cc.radio, ang_ini: a1, ang_fin: a0 };
}

const angDe = (c, p) => (Math.atan2(p[1] - c[1], p[0] - c[0]) * 180 / Math.PI + 360) % 360;

/* Las otras maneras de dar un arco, las tres que más se usan en AutoCAD y en
 * Rhino después de la de tres puntos. Todas salen como el mismo `arco` —
 * centro, radio, ángulo inicial y final, en sentido antihorario. */
async function arcoCentroInicioFin() {
  const c = await Entrada.pedirPunto({ mensaje: "Centro del arco" });
  const a = await Entrada.pedirPunto({ mensaje: "Inicio del arco", base: c,
                                       hule: (q) => ({ tipo: "linea", a: c, b: q }) });
  const r = dist2(c, a);
  if (r < 1e-9) return Comandos.eco("Radio cero.", "malo");
  const b = await Entrada.pedirPunto({
    mensaje: "Final del arco (antihorario)", base: c,
    hule: (q) => ({ tipo: "arco", c, r, a0: angDe(c, a), a1: angDe(c, q) }),
  });
  const arc = { centro: c, radio: r, ang_ini: angDe(c, a), ang_fin: angDe(c, b) };
  await crearEntidad({ tipo: "arco", ...arc }, "Arco");
  Comandos.eco(`Arco de radio ${mm(r)} ${U()}.`);
}

async function arcoInicioFinRadio() {
  const a = await Entrada.pedirPunto({ mensaje: "Inicio del arco" });
  const b = await Entrada.pedirPunto({ mensaje: "Final del arco", base: a,
                                       hule: (q) => ({ tipo: "linea", a, b: q }) });
  const cuerda = dist2(a, b);
  if (cuerda < 1e-9) return Comandos.eco("Los dos extremos son el mismo punto.", "malo");
  const m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const nrm = [-(b[1] - a[1]) / cuerda, (b[0] - a[0]) / cuerda];     // normal a la cuerda
  // El arco panza hacia donde esté el cursor: el centro va del lado contrario.
  const armar = (r, hacia) => {
    r = Math.max(r, cuerda / 2);
    const h = Math.sqrt(Math.max(0, r * r - cuerda * cuerda / 4));
    const lado = (hacia[0] - m[0]) * nrm[0] + (hacia[1] - m[1]) * nrm[1] >= 0 ? 1 : -1;
    const c = [m[0] - nrm[0] * h * lado, m[1] - nrm[1] * h * lado];
    // Antihorario de a a b, o de b a a: el que pase por el lado del cursor.
    const a0 = angDe(c, a), a1 = angDe(c, b);
    const medio = ((a1 - a0 + 360) % 360) / 2 + a0;
    const pm = [c[0] + r * Math.cos(medio * Math.PI / 180), c[1] + r * Math.sin(medio * Math.PI / 180)];
    const bien = ((pm[0] - m[0]) * nrm[0] + (pm[1] - m[1]) * nrm[1]) * lado >= 0;
    return bien ? { centro: c, radio: r, ang_ini: a0, ang_fin: a1 }
                : { centro: c, radio: r, ang_ini: a1, ang_fin: a0 };
  };
  const p = await Entrada.pedirPunto({
    mensaje: "Radio (o teclea la medida); el arco panza hacia el cursor", base: m,
    hule: (q) => { const x = armar(dist2(m, q), q); return { tipo: "arco", c: x.centro, r: x.radio, a0: x.ang_ini, a1: x.ang_fin }; },
  });
  const arc = armar(dist2(m, p), [estado.cursor.x, estado.cursor.y]);
  await crearEntidad({ tipo: "arco", ...arc }, "Arco");
  Comandos.eco(`Arco de radio ${mm(arc.radio)} ${U()}.`);
}

async function arcoInicioCentroAngulo() {
  const a = await Entrada.pedirPunto({ mensaje: "Inicio del arco" });
  const c = await Entrada.pedirPunto({ mensaje: "Centro del arco", base: a,
                                       hule: (q) => ({ tipo: "linea", a, b: q }) });
  const r = dist2(c, a);
  if (r < 1e-9) return Comandos.eco("Radio cero.", "malo");
  const a0 = angDe(c, a);
  const ang = await Entrada.pedirNumero({ mensaje: "Ángulo del arco en grados (antihorario; negativo, horario)", valor: 90 });
  if (!ang) return Comandos.eco("Ángulo cero.", "malo");
  const arc = ang > 0 ? { centro: c, radio: r, ang_ini: a0, ang_fin: (a0 + ang) % 360 }
                      : { centro: c, radio: r, ang_ini: (a0 + ang + 720) % 360, ang_fin: a0 };
  await crearEntidad({ tipo: "arco", ...arc }, "Arco");
  Comandos.eco(`Arco de radio ${mm(r)} ${U()} y ${Math.abs(ang)}°.`);
}

Comandos.registrar({
  nombre: "ARCO", alias: ["A"],
  ayuda: "ARCO [CIF · IFR · ICA] — tres puntos; centro-inicio-fin; inicio-fin-radio; inicio-centro-ángulo",
  correr: async (args) => repetir(async () => {
    const modo = (args[0] || "").toUpperCase();
    if (modo === "CIF") return arcoCentroInicioFin();
    if (modo === "IFR") return arcoInicioFinRadio();
    if (modo === "ICA") return arcoInicioCentroAngulo();
    const a = await Entrada.pedirPunto({ mensaje: "Inicio del arco" });
    const b = await Entrada.pedirPunto({
      mensaje: "Final del arco", base: a,
      hule: (q) => ({ tipo: "linea", a, b: q }),
    });
    const m = await Entrada.pedirPunto({
      mensaje: "Punto por el que pasa",
      hule: (q) => {
        const arc = arcoPorTres(a, q, b);
        return arc ? { tipo: "arco", c: arc.centro, r: arc.radio, a0: arc.ang_ini, a1: arc.ang_fin }
                   : { tipo: "linea", a, b };
      },
    });
    const arc = arcoPorTres(a, m, b);
    if (!arc) return Comandos.eco("Los tres puntos están en línea recta: no hay arco.", "malo");
    await crearEntidad({ tipo: "arco", centro: arc.centro, radio: arc.radio,
                         ang_ini: arc.ang_ini, ang_fin: arc.ang_fin }, "Arco");
    Comandos.eco(`Arco de radio ${mm(arc.radio)} ${U()}.`);
  }),
});

/* ===================================================================== */
/* 23 · Elipse                                                           */
/* ===================================================================== */
Comandos.registrar({
  nombre: "ELIPSE", alias: ["EL"],
  ayuda: "ELIPSE [E] — por centro, extremo del eje y semieje menor; con E, por los dos extremos del eje",
  correr: async (args) => repetir(async () => {
    let c, a;
    if ((args[0] || "").toUpperCase() === "E") {
      // Por los dos extremos del eje, como el ELLIPSE de AutoCAD por omisión:
      // la elipse que cabe en un vano se da por sus bordes, no por su centro.
      const e1 = await Entrada.pedirPunto({ mensaje: "Un extremo del eje" });
      const e2 = await Entrada.pedirPunto({ mensaje: "El otro extremo del eje", base: e1, direccion: true,
                                            hule: (q) => ({ tipo: "linea", a: e1, b: q }) });
      c = [(e1[0] + e2[0]) / 2, (e1[1] + e2[1]) / 2];
      a = e2;
    } else {
      c = await Entrada.pedirPunto({ mensaje: "Centro de la elipse" });
      a = await Entrada.pedirPunto({
        mensaje: "Extremo del eje mayor", base: c,
        hule: (q) => ({ tipo: "linea", a: c, b: q }),
      });
    }
    const eje = [a[0] - c[0], a[1] - c[1]];
    const mayor = Math.hypot(eje[0], eje[1]);
    if (mayor < 1e-9) return Comandos.eco("Eje de largo cero.", "malo");
    const b = await Entrada.pedirPunto({
      mensaje: "Semieje menor", base: c,
      hule: (q) => {
        // distancia perpendicular al eje mayor
        const d = Math.abs((q[0] - c[0]) * (-eje[1]) + (q[1] - c[1]) * eje[0]) / mayor;
        return { tipo: "linea", a: c, b: [c[0] - eje[1] / mayor * d, c[1] + eje[0] / mayor * d] };
      },
    });
    const menor = Math.abs((b[0] - c[0]) * (-eje[1]) + (b[1] - c[1]) * eje[0]) / mayor;
    if (menor < 1e-9) return Comandos.eco("Semieje menor cero.", "malo");
    await crearEntidad({ tipo: "elipse", centro: c, eje_mayor: eje,
                         razon: menor / mayor }, "Elipse");
    Comandos.eco(`Elipse de ${mm(mayor * 2)} × ${mm(menor * 2)} ${U()}.`);
  }),
});

/* ===================================================================== */
/* 24 · Spline                                                           */
/* ===================================================================== */
Comandos.registrar({
  nombre: "SPLINE", alias: ["SPL"],
  ayuda: "SPLINE [CV] — curva que pasa por los puntos que le des; con CV, curva jalada por puntos de control (Bézier). Escape termina.",
  correr: async (args) => {
    // CV: la curva «orgánica» de Illustrator y de Rhino. No pasa por los
    // puntos, se deja jalar por ellos; el motor la evalúa como B-spline de
    // verdad (core/dibujo.py) y al DXF sale con sus puntos de control.
    const control = (args[0] || "").toUpperCase() === "CV";
    const puntos = [];
    try {
      while (true) {
        const p = await Entrada.pedirPunto({
          mensaje: (control ? "Punto de control" : "Punto de la curva") + (puntos.length < 2 ? "" : " (Escape termina)"),
          base: puntos.length ? puntos.at(-1) : null,
          hule: (q) => ({ tipo: "polilinea", puntos: [...puntos, q] }),
        });
        puntos.push(p);
      }
    } catch (err) {
      if (err.message !== "cancelado") throw err;
    }
    if (puntos.length < 3) return Comandos.eco("Una spline necesita al menos tres puntos.", "malo");
    if (control) {
      await crearEntidad({ tipo: "spline", puntos_control: puntos, grado: 3 }, "Spline");
      return Comandos.eco(`Spline con ${puntos.length} puntos de control.`);
    }
    await crearEntidad({ tipo: "spline", puntos_ajuste: puntos, grado: 3 }, "Spline");
    Comandos.eco(`Spline por ${puntos.length} puntos.`);
  },
});

/* ===================================================================== */
/* 25 · Punto                                                            */
/* ===================================================================== */
Comandos.registrar({
  nombre: "PUNTO", alias: ["PU"],
  ayuda: "Marca un punto (sirve de nodo para las referencias)",
  correr: async () => repetir(async () => {
    const p = await Entrada.pedirPunto({ mensaje: "Ubicación del punto" });
    await crearEntidad({ tipo: "punto", p }, "Punto");
  }),
});

/* ===================================================================== */
/* 26 · Rayado                                                           */
/* ===================================================================== */
/* Se raya **eligiendo el contorno**, no picando dentro. Detectar el contorno a
 * partir de un clic interior exige rastrear islas y aristas sueltas, y en un
 * plano de obra medio dibujado eso falla más de lo que acierta. Elegir la
 * polilínea o el círculo que hace de borde siempre da el resultado que el
 * usuario esperaba. */
/* La galería de patrones  ·  0.20.0.
 *
 * Mike (9-sep-2026): «cuando cree un hatch, antes de cerrar el comando pídeme
 * seleccionar un patrón y abre una pequeña galería; mouse over predibuja en
 * el modelo; Enter para confirmar». Sale junto al cursor con una miniatura de
 * cada patrón (dibujada aquí mismo, en canvas); al pasar por encima se pide
 * al motor la previa —las mismas rayas que va a crear— y se pinta como hule.
 * Enter o clic confirman el resaltado; las flechas lo mueven; Esc cancela. Se
 * recuerda el último patrón elegido. */
const Galeria = (() => {
  let caja = null;
  const MINIS = {   // cómo se dibuja cada miniatura: familias (ángulo, paso px, guion)
    SOLID: "solido", ANSI31: [[45, 7]], ANSI32: [[45, 9], [45, 9, 3]], ANSI33: [[45, 8, 0, [6, 3]], [45, 8, 4, [6, 3]]],
    ANSI34: [[45, 12], [45, 12, 3], [45, 12, 6], [45, 12, 9]], ANSI37: [[45, 7], [135, 7]], LINE: [[0, 7]], VERT: [[90, 7]],
    NET: [[0, 7], [90, 7]], NET3: [[0, 8], [90, 8], [45, 8]], DOTS: "puntos", BRICK: "ladrillo",
    "AR-CONC": "concreto", "AR-SAND": "arena", EARTH: [[0, 8, 4, [8, 8]], [90, 8, 4, [8, 8]]],
    STEEL: [[45, 6], [45, 6, 2]], WOOD: [[0, 7, 0, [14, 4]], [0, 7, 3, [5, 12]]],
    INSUL: [[0, 9], [0, 9, 3, [9, 9]], [0, 9, 6, [9, 9]]], GLASS: [[45, 10, 0, [8, 4]], [45, 10, 5, [3, 9]]],
    HEX: [[0, 7, 0, [5, 8]], [120, 7, 0, [5, 8]], [60, 7, 4, [5, 8]]],
  };

  function miniatura(nombre) {
    const cv = document.createElement("canvas");
    cv.width = 88; cv.height = 88;
    const c = cv.getContext("2d");
    c.fillStyle = "#fff"; c.fillRect(0, 0, 88, 88);
    c.strokeStyle = "#1A1F27"; c.fillStyle = "#1A1F27"; c.lineWidth = 1.4;
    const fam = MINIS[nombre] || [[45, 7]];
    if (fam === "solido") { c.fillRect(8, 8, 72, 72); return cv; }
    c.save(); c.beginPath(); c.rect(6, 6, 76, 76); c.clip();
    if (fam === "puntos") {
      for (let y = 10; y < 84; y += 6) for (let x = 10 + ((y / 6) % 2) * 3; x < 84; x += 6) c.fillRect(x, y, 1.6, 1.6);
    } else if (fam === "ladrillo") {
      for (let y = 8, k = 0; y < 84; y += 12, k++) {
        c.beginPath(); c.moveTo(6, y); c.lineTo(82, y); c.stroke();
        for (let x = 6 + (k % 2) * 12; x < 84; x += 24) { c.beginPath(); c.moveTo(x, y); c.lineTo(x, y + 12); c.stroke(); }
      }
    } else if (fam === "concreto") {
      c.setLineDash([4, 9]);
      for (const [a, s] of [[50, 12], [355, 11], [100, 13]]) rayas(c, a, s, (a * 7) % s);
      c.setLineDash([]);
      for (let i = 0; i < 26; i++) { const x = 10 + (i * 37) % 70, y = 10 + (i * 53) % 70; c.fillRect(x, y, 1.5, 1.5); }
    } else if (fam === "arena") {
      for (let i = 0; i < 90; i++) { const x = 8 + (i * 37) % 72, y = 8 + (i * 59) % 72; c.fillRect(x, y, 1.5, 1.5); }
    } else {
      for (const [a, s, d, g] of fam) { if (g) c.setLineDash(g); else c.setLineDash([]); rayas(c, a, s, d || 0); }
    }
    c.restore();
    return cv;
  }
  function rayas(c, ang, paso, des) {
    const r = ang * Math.PI / 180, dx = Math.cos(r), dy = -Math.sin(r), nx = -dy, ny = dx;
    c.beginPath();
    for (let m = -20; m <= 20; m++) {
      const ox = 44 + nx * m * paso, oy = 44 + ny * m * paso;
      c.moveTo(ox - dx * 80 + dx * (des || 0), oy - dy * 80 + dy * (des || 0));
      c.lineTo(ox + dx * 80 + dx * (des || 0), oy + dy * 80 + dy * (des || 0));
    }
    c.stroke();
  }

  /** Abre la galería y devuelve el patrón elegido, o null si se canceló. */
  function elegir(patrones, inicial, alResaltar) {
    cerrar();
    return new Promise((resolver) => {
      caja = document.createElement("div");
      caja.className = "galeria-rayado";
      const hd = document.createElement("div"); hd.className = "hd"; hd.textContent = Tr("Patrón del rayado");
      caja.appendChild(hd);
      const rej = document.createElement("div"); rej.className = "rejilla";
      const botones = [];
      let elegido = Math.max(0, patrones.findIndex((p) => p.nombre === inicial));
      const marcar = (i, previa = true) => {
        elegido = i;
        botones.forEach((b, k) => b.classList.toggle("elegido", k === i));
        if (previa) alResaltar(patrones[i].nombre);
      };
      const terminar = (v) => { cerrar(); resolver(v); };
      patrones.forEach((p, i) => {
        const b = document.createElement("div");
        b.className = "pat"; b.title = `${p.nombre} · ${Tr(p.descripcion)}`;
        b.appendChild(miniatura(p.nombre));
        const et = document.createElement("span"); et.textContent = Tr(p.descripcion); b.appendChild(et);
        b.onmouseenter = () => marcar(i);
        b.onclick = () => terminar(patrones[i].nombre);
        rej.appendChild(b); botones.push(b);
      });
      caja.appendChild(rej);
      const pie = document.createElement("div"); pie.className = "pie";
      pie.textContent = Tr("Pasa el ratón para ver la previa · Enter o clic confirma · Esc cancela");
      caja.appendChild(pie);
      caja.style.visibility = "hidden";
      document.body.appendChild(caja);
      const r = caja.getBoundingClientRect();
      const lc = lienzo.getBoundingClientRect();
      const px = lc.left + (estado.cursor ? estado.cursor.px : 0), py = lc.top + (estado.cursor ? estado.cursor.py : 0);
      caja.style.left = Math.max(8, Math.min(px + 14, window.innerWidth - r.width - 8)) + "px";
      caja.style.top = Math.max(8, Math.min(py + 14, window.innerHeight - r.height - 8)) + "px";
      caja.style.visibility = "";
      marcar(elegido);
      const tecla = (e) => {
        const n = patrones.length, cols = 4;
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); terminar(null); }
        else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); terminar(patrones[elegido].nombre); }
        else if (e.key === "ArrowRight") { e.preventDefault(); marcar((elegido + 1) % n); }
        else if (e.key === "ArrowLeft") { e.preventDefault(); marcar((elegido - 1 + n) % n); }
        else if (e.key === "ArrowDown") { e.preventDefault(); marcar(Math.min(n - 1, elegido + cols)); }
        else if (e.key === "ArrowUp") { e.preventDefault(); marcar(Math.max(0, elegido - cols)); }
        else return;
        e.stopPropagation();
      };
      const fuera = (e) => { if (caja && !caja.contains(e.target)) terminar(null); };
      caja._quitar = () => { document.removeEventListener("keydown", tecla, true); document.removeEventListener("mousedown", fuera, true); };
      document.addEventListener("keydown", tecla, true);
      setTimeout(() => document.addEventListener("mousedown", fuera, true), 0);
    });
  }
  function cerrar() { if (!caja) return; if (caja._quitar) caja._quitar(); caja.remove(); caja = null; }
  return { elegir, cerrar, miniatura, get abierta() { return !!caja; } };
})();
window.Galeria = Galeria;

Comandos.registrar({
  nombre: "RAYADO", alias: ["H", "SOMBREADO"],
  ayuda: "Raya una polilínea cerrada o un círculo: se elige el patrón en una galería con previa",
  correr: async (args) => {
    const id = await Seleccion.pedirUna({
      mensaje: "Elige el contorno cerrado a rayar",
      filtro: (e) => (e.tipo === "polilinea" && e.cerrada) || e.tipo === "circulo",
      queja: "El contorno tiene que ser una polilínea cerrada o un círculo.",
    });
    const ent = await api(`/api/entidad/${id}`);
    let rutas;
    if (ent.tipo === "circulo") {
      // el círculo se pasa como dos medios arcos: es como el DXF guarda un
      // contorno circular en una ruta de polilínea
      rutas = [[[ent.centro[0] - ent.radio, ent.centro[1], 1],
                [ent.centro[0] + ent.radio, ent.centro[1], 1]]];
    } else {
      rutas = [ent.puntos.map((p) => [p[0], p[1], p[2] || 0])];
    }
    // El patrón: por argumento (RAYADO ANSI31) o en la galería, con previa.
    let patron = (args[0] || "").toUpperCase();
    let ultimo = "SOLID";
    try { ultimo = localStorage.getItem("ultimo_rayado") || "SOLID"; } catch (_) {}
    if (!patron) {
      const { patrones } = await api("/api/rayados");
      Comandos.pedir("Elige el patrón en la galería (Enter confirma)");
      estado.sel.clear(); estado.sel.add(id); Seleccion.refrescar();
      let vez = 0;
      const previa = async (nombre) => {
        const mia = ++vez;
        try {
          const r = await post("/api/rayado/previa", { rutas, patron: nombre, escala: 1, angulo: 0 });
          if (mia !== vez || !Galeria.abierta) return;
          estado.hule = { punteado: false, partes: r.solido
            ? [{ tipo: "relleno", poligonos: r.poligonos }]
            : [{ tipo: "lineas", lineas: r.lineas }] };
          pintar();
        } catch (_) {}
      };
      patron = await Galeria.elegir(patrones, ultimo, previa);
      vez++;
      estado.hule = null;
      Seleccion.limpiar();
      if (!patron) return Comandos.eco("Cancelado.");
    }
    try { localStorage.setItem("ultimo_rayado", patron); } catch (_) {}
    await crearEntidad({
      tipo: "rayado", rutas, patron,
      solido: patron === "SOLID", escala: 1, angulo: 0, asociado: [id],
      capa: estado.resumen.capas.some((c) => c.nombre === "T101-RAYADO")
        ? "T101-RAYADO" : estado.resumen.capa_activa,
    }, "Rayado");
    Comandos.eco(`Rayado ${patron.toLowerCase()}.`);
  },
});

/* ===================================================================== */
/* 27 · Texto  ·  28 · Texto de párrafo                                  */
/* ===================================================================== */
// Mike (7-sep-2026): «el default que sea 3 veces lo que es ahorita»: 2.5 → 7.5 mm.
// Se recuerda entre sesiones (Entrada.ultimoValor).
// En unidades del dibujo: 7.5 mm (0.75 cm en un dibujo en cm, que es la unidad
// de la casa desde 0.20.1). Cuando hay un valor recordado, ése manda.
let ultimaAlturaTexto = null;
const alturaTextoOmision = () => 7.5 / mmPorUnidad();

let ultimaRotacionTexto = 0;

/* El texto se pregunta en un cuadro, no en fila por la línea de comandos.
 *
 * Antes eran tres preguntas seguidas —altura, rotación y hasta el final el
 * texto— y Mike se atoró en la primera: al picar el punto, lo siguiente que uno
 * quiere escribir es el rótulo, pero el programa estaba pidiendo un número y
 * rechazaba «MESA DE TRABAJO» una y otra vez sin decir que la pregunta era
 * otra. Se veía como que el texto simplemente no dejaba escribir.
 *
 * En un cuadro se ven las tres cosas a la vez, el foco entra en el texto —que
 * es lo que se quiere escribir— y la altura y la rotación se quedan como
 * estaban la vez pasada. */
/* **Un solo tipo de texto: párrafo** (Mike, 9-sep-2026). Se quitaron las dos
 * opciones (TEXTO / TEXTOM): queda una. **Enter termina y guarda**; **Alt+Enter**
 * mete renglón nuevo. La entidad es `texto` con renglones (`\n`): tiene
 * rotación y justificación, y al DXF sale como MTEXT si lleva más de un
 * renglón. Los alias MT/TM siguen llegando aquí; un `textom` de un archivo
 * ajeno se edita igual (doble clic). */
const JUSTIFICADOS = [["IZQ", "Izquierda del origen"], ["CENTRO", "Centrado en el origen"], ["DER", "Derecha del origen"]];
let ultimaJustificacion = "IZQ";

function camposTexto(e) {
  return [
    { clave: "texto", etiqueta: "Texto", tipo: "area", valor: e ? (e.texto || "") : "",
      renglones: 3, marcador: "MESA DE TRABAJO", enterAcepta: true },
    { clave: "altura", etiqueta: "Altura de letra", tipo: "numero",
      valor: e ? e.altura : Entrada.ultimoValor("altura_texto", ultimaAlturaTexto ?? alturaTextoOmision()), sufijo: U() },
    { clave: "rotacion", etiqueta: "Rotación", tipo: "numero",
      valor: e ? (e.rotacion || 0) : Entrada.ultimoValor("rotacion_texto", ultimaRotacionTexto), sufijo: "°" },
    // Mike (9-sep): justificado a la izquierda, al centro o a la derecha del
    // origen. Cambiarlo no mueve el origen: el texto se reacomoda alrededor.
    { clave: "alineacion", etiqueta: "Justificado", tipo: "lista",
      valor: e ? (e.alineacion || "IZQ") : ultimaJustificacion,
      opciones: JUSTIFICADOS.map(([v, t]) => [v, Tr(t)]) },
  ];
}

const validarTexto = (v) => {
  if (!String(v.texto).trim()) return "Escribe el texto.";
  if (!(v.altura > 0)) return "La altura tiene que ser mayor que cero.";
  return null;
};

Comandos.registrar({
  nombre: "TEXTO", alias: ["T", "DT", "MT", "TM", "TEXTOM"],
  ayuda: "Texto (uno o varios renglones): Enter guarda, Alt+Enter hace renglón nuevo",
  correr: async () => {
    const p = await Entrada.pedirPunto({ mensaje: "Punto de inserción del texto" });
    const v = await Dialogo.abrir({
      titulo: "Texto",
      pista: "Enter guarda · Alt+Enter hace renglón nuevo.",
      campos: camposTexto(null),
      validar: validarTexto,
    });
    if (!v) return Comandos.eco("Cancelado.");
    ultimaAlturaTexto = v.altura;
    ultimaRotacionTexto = v.rotacion;
    ultimaJustificacion = v.alineacion || "IZQ";
    Entrada.recordarValor("altura_texto", v.altura);
    Entrada.recordarValor("rotacion_texto", v.rotacion);
    await crearEntidad({ tipo: "texto", p, texto: v.texto, altura: v.altura,
                         rotacion: v.rotacion, alineacion: v.alineacion || "IZQ", estilo: "T101" }, "Texto");
    Comandos.eco(`Texto «${v.texto.split("\n")[0]}${v.texto.includes("\n") ? "…" : ""}».`);
  },
});


/* ===================================================================== */
/* Editar un texto que ya está puesto                                    */
/* ===================================================================== */
/* Lo usa el doble clic en el lienzo (ver `ui/vista.js`). Devuelve `true` si la
 * entidad era un texto y se atendió —aunque se cancele el cuadro—, para que
 * quien llamó sepa que ese doble clic ya tuvo dueño y no encuadre encima. */
const Dibujar = {
  async editarTexto(id) {
    let e;
    try {
      e = await api(`/api/entidad/${id}`);
    } catch (_) {
      return false;
    }
    if (!e || (e.tipo !== "texto" && e.tipo !== "textom")) return false;

    // Un `textom` de un archivo ajeno no tiene justificación ni rotación
    // propia editable aquí; se le edita texto y altura.
    const parrafoAjeno = e.tipo === "textom";
    const campos = parrafoAjeno
      ? [{ clave: "texto", etiqueta: "Texto", tipo: "area", valor: e.texto || "", renglones: 4, enterAcepta: true },
         { clave: "altura", etiqueta: "Altura de letra", tipo: "numero", valor: e.altura, sufijo: U() }]
      : camposTexto(e);
    const v = await Dialogo.abrir({
      titulo: "Editar texto",
      pista: "Enter guarda · Alt+Enter hace renglón nuevo.",
      campos,
      validar: validarTexto,
    });
    if (!v) return true;                 // canceló, pero el doble clic fue suyo

    const cambios = { texto: v.texto, altura: v.altura };
    if (!parrafoAjeno) { cambios.rotacion = v.rotacion; cambios.alineacion = v.alineacion || "IZQ"; }
    const r = await patch(`/api/entidad/${id}`, { cambios });
    aplicar(r);
    if (!aplicarParche(r)) await recargarTrazos();
    Comandos.eco(`Texto cambiado a «${v.texto.split("\n")[0]}».`);
    return true;
  },
};
window.Dibujar = Dibujar;
