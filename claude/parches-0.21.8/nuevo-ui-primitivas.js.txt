/* Sólidos directos  ·  PRISMA, CILINDRO, CONO, ESFERA, PIRAMIDE  ·  0.21.8
 *
 * Mike, 25-sep: «necesito los comandos para generar sólidos directo (prisma,
 * cilindro, pirámide, etc.)». Nacen sin boceto: se marcan dos puntos en la
 * ventana donde se está —la base, como si fuera un rectángulo o un círculo,
 * con su hule— y luego se teclea el alto. La pieza queda apoyada en el plano
 * de esa ventana (suelo, pared frontal o pared lateral) y crece hacia el lado
 * desde donde se mira, igual que EXTRUIR. Las medidas quedan en el historial
 * de la pieza y se pueden cambiar ahí.
 *
 * Los dos puntos se piden con `Entrada.pedirPunto`, así que valen el osnap,
 * las coordenadas tecleadas y la distancia directa, como en cualquier
 * herramienta de dibujo.
 */

(function () {
  "use strict";

  const mm = (typeof window.mm === "function") ? window.mm : (n) => String(Math.round(n * 100) / 100);

  function plano() {
    return (typeof Entrada !== "undefined" && Entrada.planoComando && Entrada.planoComando())
      || (estado.vista && estado.vista.plano) || "XY";
  }

  function capa() {
    return (estado.resumen && estado.resumen.capa_activa) || "0";
  }

  function dist(a, b) { return Math.hypot(b[0] - a[0], b[1] - a[1]); }

  async function alto(mensaje, clave) {
    const h = await Entrada.pedirNumero({ mensaje, valor: 100, minimo: 0.01, clave });
    return isFinite(h) ? h : null;
  }

  async function mandar(cuerpo, comando, contar) {
    try {
      const m = await fetch("/api/cuerpo/primitiva", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      }).then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || r.status); return j; });
      await Cuerpos.refrescar();
      if (typeof Camara !== "undefined" && Camara.enPlanta && Camara.enPlanta()) Camara.ver("ISO");
      Comandos.eco(`${contar} · ${(m.volumen_mm3 / 1000).toFixed(1)} cm³`
        + (m.ms !== undefined ? ` · el motor tardó ${m.ms} ms` : ""));
      return true;
    } catch (e) {
      Comandos.eco(`No se pudo hacer el ${comando.toLowerCase()}: ` + e.message, "malo");
      return false;
    }
  }

  /* Dos esquinas de la base, como RECTANGULO. Devuelve {base:[u,v], ancho, fondo}. */
  async function baseRectangular(que) {
    const a = await Entrada.pedirPunto({ mensaje: `Primera esquina de la base ${que}` });
    if (!Array.isArray(a)) return null;
    const b = await Entrada.pedirPunto({
      mensaje: "Esquina opuesta (o teclea ancho,fondo)", base: a, dinamica: "xy",
      hule: (p) => ({ tipo: "caja", a, b: p }),
    });
    if (!Array.isArray(b)) return null;
    const ancho = Math.abs(b[0] - a[0]), fondo = Math.abs(b[1] - a[1]);
    if (ancho < 1e-9 || fondo < 1e-9) { Comandos.eco("Una base de lado cero no hace pieza.", "malo"); return null; }
    return { base: [Math.min(a[0], b[0]), Math.min(a[1], b[1])], ancho, fondo };
  }

  /* Centro y radio, como CIRCULO. Devuelve {base:[u,v], radio}. */
  async function baseRedonda(que) {
    const c = await Entrada.pedirPunto({ mensaje: `Centro de la base ${que}` });
    if (!Array.isArray(c)) return null;
    const p = await Entrada.pedirPunto({
      mensaje: "Radio (o teclea la medida)", base: c,
      hule: (q) => ({ tipo: "circulo", c, r: dist(c, q) }),
    });
    if (!Array.isArray(p)) return null;
    const radio = dist(c, p);
    if (radio < 1e-9) { Comandos.eco("Radio cero.", "malo"); return null; }
    return { base: c, radio };
  }

  Comandos.registrar({
    nombre: "PRISMA", alias: ["CAJA", "BLOQUE", "BOX"],
    ayuda: "PRISMA · una caja: dos esquinas de la base en la ventana donde estás y el alto",
    correr: async () => {
      const b = await baseRectangular("del prisma");
      if (!b) return;
      const P = plano();
      const h = await alto("Alto del prisma", "prisma-alto");
      if (h === null) return;
      await mandar({ forma: "caja", plano: P, base: b.base, ancho: b.ancho, fondo: b.fondo, alto: h, capa: capa() },
                   "PRISMA", `Prisma de ${mm(b.ancho)} × ${mm(b.fondo)} × ${mm(h)} mm sobre ${P}`);
    },
  });

  Comandos.registrar({
    nombre: "PIRAMIDE", alias: ["PYRAMID"],
    ayuda: "PIRAMIDE · base rectangular con dos esquinas y el alto hasta la punta",
    correr: async () => {
      const b = await baseRectangular("de la pirámide");
      if (!b) return;
      const P = plano();
      const h = await alto("Alto de la pirámide", "piramide-alto");
      if (h === null) return;
      await mandar({ forma: "piramide", plano: P, base: b.base, ancho: b.ancho, fondo: b.fondo, alto: h, capa: capa() },
                   "PIRAMIDE", `Pirámide de ${mm(b.ancho)} × ${mm(b.fondo)} × ${mm(h)} mm sobre ${P}`);
    },
  });

  Comandos.registrar({
    nombre: "CILINDRO", alias: ["CYLINDER"],
    ayuda: "CILINDRO · centro y radio de la base en la ventana donde estás, y el alto",
    correr: async () => {
      const b = await baseRedonda("del cilindro");
      if (!b) return;
      const P = plano();
      const h = await alto("Alto del cilindro", "cilindro-alto");
      if (h === null) return;
      await mandar({ forma: "cilindro", plano: P, base: b.base, radio: b.radio, alto: h, capa: capa() },
                   "CILINDRO", `Cilindro r${mm(b.radio)} × ${mm(h)} mm sobre ${P}`);
    },
  });

  Comandos.registrar({
    nombre: "CONO", alias: ["CONE"],
    ayuda: "CONO · centro y radio de la base, y el alto hasta la punta",
    correr: async () => {
      const b = await baseRedonda("del cono");
      if (!b) return;
      const P = plano();
      const h = await alto("Alto del cono", "cono-alto");
      if (h === null) return;
      await mandar({ forma: "cono", plano: P, base: b.base, radio: b.radio, alto: h, capa: capa() },
                   "CONO", `Cono r${mm(b.radio)} × ${mm(h)} mm sobre ${P}`);
    },
  });

  Comandos.registrar({
    nombre: "ESFERA", alias: ["BOLA", "SPHERE"],
    ayuda: "ESFERA · centro y radio; queda apoyada en el plano de la ventana donde estás",
    correr: async () => {
      const b = await baseRedonda("de la esfera (donde se apoya)");
      if (!b) return;
      const P = plano();
      await mandar({ forma: "esfera", plano: P, base: b.base, radio: b.radio, capa: capa() },
                   "ESFERA", `Esfera r${mm(b.radio)} mm apoyada en ${P}`);
    },
  });

  /* --- ESTILO  ·  el estilo de vista de las piezas (0.21.8) ---------------- */
  const NOMBRES = { basico: "básico", alambrico: "alámbrico fantasma", renderizado: "renderizado" };
  Comandos.registrar({
    nombre: "ESTILO", alias: ["VISTA3D", "SHADE", "RENDER"],
    ayuda: "ESTILO [basico|alambrico|renderizado] · cómo se ven las piezas; sin nada, pasa al siguiente",
    correr: async (args) => {
      const lista = Cuerpos.ESTILOS;
      const actual = Cuerpos.estilo();
      let pedido = String(args && args[0] || "").toLowerCase()
        .normalize("NFD").replace(/\p{M}/gu, "");
      if (pedido === "b" || pedido === "basica") pedido = "basico";
      if (pedido === "a" || pedido === "wireframe" || pedido === "fantasma") pedido = "alambrico";
      if (pedido === "r" || pedido === "render" || pedido === "renderizada") pedido = "renderizado";
      const nuevo = lista.includes(pedido) ? pedido : lista[(lista.indexOf(actual) + 1) % lista.length];
      if (typeof guardarPrefs === "function") await guardarPrefs({ estilo_3d: nuevo });
      else estado.prefs.estilo_3d = nuevo;
      if (window.invalidarPlano) window.invalidarPlano();
      if (window.pintar) window.pintar();
      Comandos.eco(`Estilo de vista: ${NOMBRES[nuevo]}.`);
    },
  });
})();
