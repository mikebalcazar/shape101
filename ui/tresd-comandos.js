/* Los comandos del 3D que faltaban  ·  para que la rueda tenga qué ofrecer.
 *
 * `tresd.js` trajo EXTRUIR y la vista. Aquí van los tres que hacían falta para
 * que el 3D se pueda usar **sin teclear y sin arrastrar**:
 *
 * - `JALAR`: mueve la cara señalada una medida exacta. Arrastrar da la
 *   sensación; teclear da el milímetro. En un taller hacen falta los dos: se
 *   arrastra para ver cómo queda y se teclea para que quede bien.
 * - `STEP` y `STL`: sacar la pieza. STEP para que la abra otro CAD, STL para
 *   imprimirla.
 *
 * Van en archivo aparte para no volver a mover `tresd.js`, que ya está probado.
 * Cada archivo que se toca es un archivo que se puede romper.
 */

Comandos.registrar({
  nombre: "JALAR", alias: ["EMPUJAR", "PUSHPULL"],
  ayuda: "JALAR · mueve la cara señalada los milímetros que le digas (+ afuera, − adentro)",
  correr: async (args) => {
    const cara = TresD.senalada && TresD.senalada();
    if (!cara) {
      Comandos.eco("Primero señala una cara: teclea 3D y dale un clic a la cara que quieras mover.", "malo");
      return;
    }
    let mm = parseFloat(args[0]);
    if (!isFinite(mm)) {
      if (typeof Entrada === "undefined" || !Entrada.pedirNumero) {
        Comandos.eco("JALAR necesita una medida.", "malo");
        return;
      }
      mm = await Entrada.pedirNumero({ mensaje: `Mover «${cara.cara}» (mm)`, valor: 10, clave: "jalar-cara" });
    }
    if (!isFinite(mm) || mm === 0) return;
    await TresD.jalar(cara.id, cara.cara, mm);
  },
});

for (const [nombre, formato, ext, para] of [
  ["STEP", "step", "step", "para abrirla en otro CAD"],
  ["STL", "stl", "stl", "para imprimirla en 3D"],
]) {
  Comandos.registrar({
    nombre, alias: [`EXPORTAR${nombre}`],
    ayuda: `${nombre} · saca la pieza en ${nombre} (${para})`,
    correr: async () => {
      const id = TresD.primerCuerpo && TresD.primerCuerpo();
      if (!id) {
        Comandos.eco("No hay ninguna pieza en 3D que sacar. Levanta un contorno con EXTRUIR.", "malo");
        return;
      }
      // El diálogo de guardar es del escritorio: en un navegador suelto no hay.
      if (typeof escritorio === "undefined" || !escritorio || !escritorio.guardar) {
        Comandos.eco(`${nombre} sólo funciona en el programa instalado.`, "malo");
        return;
      }
      const ruta = await escritorio.guardar(`pieza.${ext}`, ext);
      if (!ruta) return;
      try {
        const r = await fetch(`/api/cuerpo/${id}/exportar`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ formato, ruta }),
        }).then(async (res) => { const j = await res.json(); if (!res.ok) throw new Error(j.detail || res.status); return j; });
        Comandos.eco(`${nombre} guardado en ${r.ruta} (${Math.round(r.bytes / 1024)} KB)`);
      } catch (e) {
        Comandos.eco(`No se pudo sacar el ${nombre}: ` + e.message, "malo");
      }
    },
  });
}
