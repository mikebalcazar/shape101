/* Bloques, biblioteca y referencias  ·  features 29, 30, 7 y 8.
 *
 * Un bloque es una pieza que se repite: una jaladera, una bisagra, un símbolo
 * de toma de corriente. Dibujada una vez y puesta cien veces, y si cambia la
 * definición cambian las cien.
 *
 * La biblioteca es del **taller**, no del proyecto: vive en
 * `~/Taller 101/shape101/bloques` y está en todas las cocinas. Es la misma
 * lección que los materiales de Taller 101 — el estándar es del taller.
 */

/* ===================================================================== */
/* 29 · Crear e insertar bloques                                         */
/* ===================================================================== */
Comandos.registrar({
  nombre: "BLOQUE", alias: ["BL", "B_"],
  ayuda: "Convierte lo seleccionado en un bloque",
  correr: async () => {
    const ids = await Seleccion.pedir({ mensaje: "Selecciona lo que forma el bloque" });
    if (!ids.length) return;
    const base = await Entrada.pedirPunto({
      mensaje: "Punto base del bloque (por dónde se agarra al insertarlo)" });
    const nombre = await Entrada.pedirTexto({ mensaje: "Nombre del bloque" });
    if (!nombre) return Comandos.eco("Sin nombre: no se creó el bloque.", "malo");
    try {
      aplicar(await post("/api/bloque", { nombre, ids, base }));
      await recargarTrazos();
      Seleccion.limpiar();
      Comandos.eco(`Bloque «${nombre}» con ${ids.length} entidad(es).`, "bien");
    } catch (e) { avisar(e.message, true); }
  },
});

Comandos.registrar({
  nombre: "INSERTAR", alias: ["IN", "I_"],
  ayuda: "Inserta un bloque del dibujo o de la biblioteca del taller",
  correr: async () => {
    const { documento, biblioteca } = await api("/api/bloques");
    if (!documento.length && !biblioteca.length) {
      return Comandos.eco("No hay bloques todavía. Crea uno con BLOQUE.", "malo");
    }
    for (const b of documento) Comandos.eco(`  · ${b.nombre} (${b.entidades} entidades)`);
    for (const b of biblioteca) Comandos.eco(`  · ${b.nombre} — biblioteca del taller`);

    const nombre = await Entrada.pedirTexto({ mensaje: "¿Cuál bloque?" });
    if (!nombre) return;
    const enDoc = documento.some((b) => b.nombre === nombre);
    const enBib = biblioteca.some((b) => b.nombre === nombre);
    if (!enDoc && !enBib) return Comandos.eco(`No hay ningún bloque «${nombre}».`, "malo");

    const escala = await Entrada.pedirNumero({ mensaje: "Escala", valor: 1, minimo: 1e-6 });
    const rot = await Entrada.pedirNumero({ mensaje: "Rotación", valor: 0 });
    await repetir(async () => {
      const p = await Entrada.pedirPunto({ mensaje: "¿Dónde va? (Escape termina)" });
      aplicar(await post("/api/insertar", {
        nombre, p, escala, rotacion: rot, desde_biblioteca: !enDoc }));
      await recargarTrazos();
    });
  },
});

/* ===================================================================== */
/* 30 · Biblioteca del taller                                            */
/* ===================================================================== */
Comandos.registrar({
  nombre: "GUARDARBLOQUE", alias: ["GB"],
  ayuda: "Guarda un bloque del dibujo en la biblioteca del taller",
  correr: async () => {
    const { documento } = await api("/api/bloques");
    if (!documento.length) return Comandos.eco("Este dibujo no tiene bloques.", "malo");
    for (const b of documento) Comandos.eco(`  · ${b.nombre}`);
    const nombre = await Entrada.pedirTexto({ mensaje: "¿Cuál se guarda?" });
    if (!nombre) return;
    const descripcion = await Entrada.pedirTexto({ mensaje: "Descripción", valor: "" });
    try {
      const r = await post("/api/biblioteca", { nombre, descripcion });
      Comandos.eco(`«${r.guardado}» guardado en la biblioteca del taller.`, "bien");
      avisar(`Guardado en ${r.carpeta}. Está en todos tus dibujos.`, false, 8000);
    } catch (e) { avisar(e.message, true); }
  },
});

Comandos.registrar({
  nombre: "BIBLIOTECA", alias: ["BIB"],
  ayuda: "Enseña los bloques del dibujo y los del taller",
  correr: async () => {
    const { documento, biblioteca } = await api("/api/bloques");
    Comandos.eco(`En este dibujo: ${documento.length} bloque(s).`);
    for (const b of documento) Comandos.eco(`  · ${b.nombre} (${b.entidades} entidades)`);
    Comandos.eco(`En la biblioteca del taller: ${biblioteca.length}.`);
    for (const b of biblioteca) {
      Comandos.eco(`  · ${b.nombre}${b.descripcion ? " — " + b.descripcion : ""}`);
    }
  },
});

/* ===================================================================== */
/* 7 · PDF vectorial de fondo                                            */
/* ===================================================================== */
Comandos.registrar({
  nombre: "PDFFONDO", alias: ["PDFF", "FONDO"],
  ayuda: "Trae las líneas de un PDF de arquitecto para calcar encima",
  correr: async () => {
    const ruta = await pedirRuta("abrir", [{ name: "PDF", extensions: ["pdf"] }]);
    if (!ruta) return;
    let paginas;
    try {
      ({ paginas } = await post("/api/pdf_paginas", { ruta }));
    } catch (e) { return avisar(e.message, true); }

    for (const p of paginas) {
      Comandos.eco(`  página ${p.numero}: ${p.ancho}×${p.alto} mm · ${p.trazos} trazos`);
    }
    const n = Math.round(await Entrada.pedirNumero({ mensaje: "¿Qué página?", valor: 1, minimo: 1 }));
    // La escala es la del plano impreso: un PDF a 1:50 se trae con 50 para que
    // quede a tamaño real, que es como hay que medirlo.
    const escala = await Entrada.pedirNumero({
      mensaje: "¿A qué escala está impreso? (1:__)", valor: 50, minimo: 0.001 });
    try {
      const r = await post("/api/pdf_fondo", { ruta, pagina: n, escala, origen: [0, 0] });
      aplicar(r);
      await recargarTrazos();
      encuadrar();
      Comandos.eco(`${r.entidades} líneas en la capa ${r.capa}, bloqueada.`, "bien");
      avisar(`Fondo importado: ${r.entidades} líneas. La capa ${r.capa} está ` +
             "bloqueada y no imprime — es referencia, no dibujo.", false, 10000);
    } catch (e) {
      avisar(e.message, true, 12000);
      if (/escaneo|vectores/i.test(e.message)) {
        Comandos.eco("Prueba con IMAGENREF para meterlo como imagen y calcar encima.");
      }
    }
  },
});

/* ===================================================================== */
/* 8 · Imagen de referencia                                              */
/* ===================================================================== */
Comandos.registrar({
  nombre: "IMAGENREF", alias: ["IMG", "REFIMG"],
  ayuda: "Pone una foto o un escaneo debajo del dibujo, para calcar",
  correr: async () => {
    const ruta = await pedirRuta("abrir", [
      { name: "Imágenes", extensions: ["png", "jpg", "jpeg", "webp", "bmp"] }]);
    if (!ruta) return;
    const a = await Entrada.pedirPunto({ mensaje: "Esquina inferior izquierda" });
    const b = await Entrada.pedirPunto({
      mensaje: "Esquina superior derecha", base: a,
      hule: (q) => ({ tipo: "caja", a, b: q }),
    });
    const ancho = Math.abs(b[0] - a[0]), alto = Math.abs(b[1] - a[1]);
    if (ancho < 1e-6 || alto < 1e-6) return Comandos.eco("Ese rectángulo no tiene tamaño.", "malo");
    await crearEntidad({
      tipo: "imagen", archivo: ruta,
      p: [Math.min(a[0], b[0]), Math.min(a[1], b[1])],
      ancho, alto, opacidad: 0.6,
      capa: estado.resumen.capas.some((c) => c.nombre === "T101-AUXILIAR")
        ? "T101-AUXILIAR" : estado.resumen.capa_activa,
    }, "Imagen de referencia");
    Comandos.eco("Imagen puesta. No viaja al DXF: es referencia, no dibujo.");
  },
});
