/* Puente con la suite  ·  features 6 y 69 a 74, y los extras de F9.
 *
 * shape101 no es una isla: la cocina se modela en Taller 101, se dibuja aquí y
 * se manda a SUPERVISOR. Lo que va de una app a otra son archivos, no llamadas:
 * un archivo se puede mirar, guardar y volver a abrir el mes que viene.
 */

Comandos.registrar({
  nombre: "IMPORTART101X", alias: ["T101X", "COCINA"],
  ayuda: "Trae una cocina de Taller 101 y le dibuja plantas y alzados",
  correr: async () => {
    const ruta = await pedirRuta("abrir", [
      { name: "Proyecto Taller 101", extensions: ["t101x"] }]);
    if (!ruta) return;
    let resumen;
    try {
      resumen = await post("/api/t101x/resumen", { ruta });
    } catch (e) { return avisar(e.message, true, 9000); }

    Comandos.eco(`«${resumen.nombre}» · ${resumen.cliente}`);
    Comandos.eco(`${resumen.gabinetes} mueble(s): ${resumen.bajos} bajo(s), ` +
                 `${resumen.aereos} aéreo(s) — ${resumen.nombres.join(", ")}`);
    const acotar = !(await Entrada.pedirTexto({
      mensaje: "¿Acotar automáticamente? S/N", valor: "S" })).toUpperCase().startsWith("N");

    try {
      const r = await post("/api/t101x/importar", { ruta, acotar });
      aplicar(r);
      await recargarTrazos();
      encuadrar();
      Comandos.eco(`${r.gabinetes} mueble(s) dibujados, ${r.cotas} cota(s).`, "bien");
      avisar(`Cocina importada: ${r.gabinetes} muebles, cada uno como bloque. ` +
             "Si cambias el proyecto en Taller 101, usa ACT para rehacerlos.", false, 11000);
    } catch (e) { avisar(e.message, true, 11000); }
  },
});

Comandos.registrar({
  // Ojo con el nombre: REGENERAR (alias RE) ya es el de refrescar la pantalla,
  // como en AutoCAD. Éste es otro trabajo y necesita otro nombre.
  nombre: "ACTUALIZARMUEBLES", alias: ["ACT", "REGENT101X"],
  ayuda: "Vuelve a leer el .t101x y rehace los muebles, sin tocar tus anotaciones",
  correr: async () => {
    try {
      const r = await post("/api/t101x/regenerar");
      aplicar(r);
      await recargarTrazos();
      Comandos.eco(`${r.gabinetes} mueble(s) rehechos; ${r.borradas} entidad(es) ` +
                   "generadas antes se reemplazaron.", "bien");
      avisar("Muebles actualizados. Lo que dibujaste o anotaste a mano sigue ahí.",
             false, 9000);
    } catch (e) { avisar(e.message, true, 10000); }
  },
});

Comandos.registrar({
  nombre: "HOJASPORMUEBLE", alias: ["HPM", "DESPIECE"],
  ayuda: "Una hoja de impresión por cada mueble importado",
  correr: async () => {
    try {
      const r = await post("/api/hojas_por_mueble");
      await Papel.pintarPestanas();
      Comandos.eco(`${r.hojas.length} hoja(s): ${r.hojas.join(", ")}`, "bien");
      avisar(`${r.hojas.length} hojas creadas, una por mueble. ` +
             "IMPRIMIR TODO las saca en un solo PDF.", false, 9000);
    } catch (e) { avisar(e.message, true, 9000); }
  },
});

Comandos.registrar({
  nombre: "SUPERVISOR", alias: ["ENVIAR", "PAQUETE"],
  ayuda: "Deja el PDF, el DXF y el manifiesto en una carpeta para SUPERVISOR",
  correr: async () => {
    const carpeta = await Entrada.pedirTexto({
      mensaje: "¿En qué carpeta se deja el paquete?",
      valor: (estado.resumen.ruta || "").replace(/[^\\/]*$/, "") + "supervisor" });
    if (!carpeta) return;
    try {
      const r = await post("/api/paquete_supervisor", { carpeta });
      Comandos.eco(`Paquete en ${r.carpeta}`, "bien");
      Comandos.eco(`  · ${Object.values(r.archivos).length} archivo(s) + manifiesto.json`);
      avisar(`Listo para SUPERVISOR: ${r.muebles.length} mueble(s), ` +
             `${r.hojas.length} hoja(s), en ${r.carpeta}`, false, 11000);
    } catch (e) { avisar(e.message, true, 9000); }
  },
});

/* ===================================================================== */
/* 76 · Tabla de cantidades desde bloques                                */
/* ===================================================================== */
Comandos.registrar({
  nombre: "CANTIDADES", alias: ["TABLA", "CONTAR"],
  ayuda: "Cuenta cuántas veces está insertado cada bloque",
  correr: async () => {
    const ids = [...new Set(estado.geometria.map((g) => g.id))];
    const cuenta = new Map();
    for (const t of estado.trazos) {
      if (t.bloque) cuenta.set(t.bloque, (cuenta.get(t.bloque) || 0) + 1);
    }
    // El conteo bueno se hace sobre las entidades, no sobre los trazos: un
    // bloque con veinte líneas contaría veinte veces.
    const ents = await Promise.all(ids.map((id) => api(`/api/entidad/${id}`).catch(() => null)));
    const tabla = new Map();
    for (const e of ents) {
      if (e && e.tipo === "insercion") tabla.set(e.bloque, (tabla.get(e.bloque) || 0) + 1);
    }
    if (!tabla.size) return Comandos.eco("No hay bloques insertados en el dibujo.", "malo");
    Comandos.eco("Cantidades:");
    let total = 0;
    for (const [nombre, n] of [...tabla].sort()) {
      Comandos.eco(`  ${String(n).padStart(4)} × ${nombre}`);
      total += n;
    }
    Comandos.eco(`  ${String(total).padStart(4)} en total`, "bien");
  },
});

/* ===================================================================== */
/* 77 · Referencia externa                                               */
/* ===================================================================== */
/* Un xref trae el dibujo de otro archivo a una capa bloqueada, recordando de
 * dónde vino para poder recargarlo. No se enlaza en vivo: un plano que cambia
 * solo mientras lo miras es un plano en el que no se puede confiar. Se recarga
 * cuando uno lo pide, y entonces se ve qué cambió. */
Comandos.registrar({
  nombre: "REFEXT", alias: ["XREF"],
  ayuda: "Trae otro DXF como fondo bloqueado, y lo puede recargar",
  correr: async () => {
    const ruta = await pedirRuta("abrir", [
      { name: "Dibujos", extensions: ["dxf", "t101d"] }]);
    if (!ruta) return;
    try {
      const r = await post("/api/refext", { ruta });
      aplicar(r);
      await recargarTrazos();
      Comandos.eco(`${r.entidades} entidad(es) desde ${r.capa}, capa bloqueada.`, "bien");
    } catch (e) { avisar(e.message, true, 9000); }
  },
});

/* ===================================================================== */
/* 78 · Comparar dos versiones                                           */
/* ===================================================================== */
Comandos.registrar({
  nombre: "COMPARAR", alias: ["DIFF"],
  ayuda: "Compara este dibujo con otro archivo y dice qué cambió",
  correr: async () => {
    const ruta = await pedirRuta("abrir", [
      { name: "Dibujos", extensions: ["t101d", "dxf"] }]);
    if (!ruta) return;
    try {
      const r = await post("/api/comparar", { ruta });
      Comandos.eco(`Contra ${ruta}:`, "bien");
      Comandos.eco(`  ${r.solo_aqui} entidad(es) sólo en este dibujo`);
      Comandos.eco(`  ${r.solo_alla} entidad(es) sólo en el otro`);
      Comandos.eco(`  ${r.iguales} iguales en los dos`);
      for (const linea of r.detalle) Comandos.eco("  · " + linea);
      avisar(`Diferencias: +${r.solo_aqui} / −${r.solo_alla}. ` +
             "Las que sólo están aquí quedaron seleccionadas.", false, 10000);
      estado.sel = new SelSet(r.ids_solo_aqui);
      Seleccion.alternar(null, true);
    } catch (e) { avisar(e.message, true, 9000); }
  },
});

/* ===================================================================== */
/* 80 · Atajos configurables                                             */
/* ===================================================================== */
Comandos.registrar({
  nombre: "ATAJO", alias: ["ALIAS"],
  ayuda: "ATAJO <letra> <comando> — inventa tu propio alias",
  correr: async (args) => {
    const atajos = { ...(estado.prefs.atajos || {}) };
    if (!args.length) {
      const hay = Object.entries(atajos);
      if (!hay.length) return Comandos.eco("No tienes atajos propios. Ej: ATAJO Q CIRCULO");
      for (const [k, v] of hay) Comandos.eco(`  ${k} → ${v}`);
      return;
    }
    const clave = args[0].toUpperCase();
    const destino = (args[1] || "").toUpperCase();
    if (!destino) {
      delete atajos[clave];
      await guardarPrefs({ atajos });
      Comandos.aplicarAtajos(atajos);
      return Comandos.eco(`Atajo ${clave} quitado.`);
    }
    if (!Comandos.existe(destino)) {
      return Comandos.eco(`No existe el comando ${destino}.`, "malo");
    }
    atajos[clave] = destino;
    await guardarPrefs({ atajos });
    Comandos.aplicarAtajos(atajos);
    Comandos.eco(`${clave} → ${destino}. Se queda guardado.`, "bien");
  },
});
