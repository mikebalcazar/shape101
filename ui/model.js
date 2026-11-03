/* El grupo **model**  ·  las funciones que hacen un sólido de la nada.
 *
 * Mike, 19-sep, partiendo el programa en cuatro grupos: *«model — funciones
 * básicas para generar sólidos nuevos, extrude, revolve, sweep, loft, etc.»*,
 * y aparte *«extrude face que es un sólido nuevo a partir de una cara nueva:
 * no sería estirar la cara, sería aumentar un sólido a partir del perfil de la
 * cara»*.
 *
 * EXTRUIR ya vivía en `tresd.js` desde la 0.4.0 y no se toca. Aquí van los
 * cuatro que faltaban. Los tres primeros trabajan igual que EXTRUIR: señalas
 * en el dibujo lo que hace falta y das el comando. Quién es el perfil y quién
 * el eje o el camino lo reparte el servidor por lo que cada entidad dice de sí
 * misma —cerrada o abierta—, no por el orden en que se señaló: el orden de una
 * selección es de la selección, y nadie lo mira al hacerla.
 *
 * CRECER es el cuarto y no sale del dibujo sino de una cara ya señalada en 3D,
 * como JALAR.
 */

(function () {
  "use strict";

  function seleccion() {
    return [...(typeof estado !== "undefined" && estado.sel ? estado.sel : [])];
  }

  /* Lo que las tres hacen igual: mandar, refrescar y contar cómo quedó. Que
   * viva en un solo sitio es lo que hace que las tres den el mismo aviso y que
   * un arreglo valga para las tres. */
  async function pedir(ruta, cuerpo, comando) {
    try {
      const m = await fetch(`/api/cuerpo/${ruta}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      }).then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || r.status); return j; });
      await Cuerpos.refrescar();
      // Igual que EXTRUIR: si se estaba mirando desde arriba se gira, porque en
      // planta una pieza recién nacida se ve idéntica al contorno del que salió.
      if (typeof Camara !== "undefined" && Camara.enPlanta()) Camara.ver("ISO");
      const cuanto = m.es_superficie
        ? `superficie de ${m.caja[0]} × ${m.caja[1]} × ${m.caja[2]} mm · ${(m.area_mm2 / 100).toFixed(1)} cm²`
        : `pieza de ${m.caja[0]} × ${m.caja[1]} × ${m.caja[2]} mm · ${(m.volumen_mm3 / 1000).toFixed(1)} cm³`;
      Comandos.eco(cuanto + (m.ms !== undefined ? ` · el motor tardó ${m.ms} ms` : ""));
      return true;
    } catch (e) {
      Comandos.eco(`No se pudo ${comando.toLowerCase()}: ` + e.message, "malo");
      return false;
    }
  }

  Comandos.registrar({
    nombre: "REVOLVER", alias: ["REVOLUCIONAR", "TORNEAR", "REVOLVE"],
    ayuda: "REVOLVER [grados] · gira el contorno señalado alrededor de la línea de eje; con una curva abierta deja una superficie",
    correr: async (args) => {
      const ids = seleccion();
      if (ids.length < 2) {
        Comandos.eco("Señala el contorno cerrado y la línea que hace de eje, y vuelve a dar REVOLVER.", "malo");
        return;
      }
      let grados = parseFloat(args[0]);
      if (!isFinite(grados)) {
        if (typeof Entrada === "undefined" || !Entrada.pedirNumero) grados = 360;
        else grados = await Entrada.pedirNumero({ mensaje: "Cuántos grados gira", valor: 360, clave: "revolver-grados" });
      }
      if (!isFinite(grados) || grados <= 0 || grados > 360) {
        Comandos.eco("Un revolucionado gira entre 0 y 360 grados.", "malo");
        return;
      }
      await pedir("revolver", { ids, grados }, "REVOLVER");
    },
  });

  Comandos.registrar({
    nombre: "BARRER", alias: ["BARRIDO", "SWEEP"],
    ayuda: "BARRER · lleva el contorno cerrado por el camino abierto; con un perfil abierto (el primero que señales) deja una superficie",
    correr: async () => {
      const ids = seleccion();
      if (ids.length < 2) {
        Comandos.eco("Señala el contorno cerrado y el camino por donde va, y vuelve a dar BARRER. "
          + "Pueden estar en ventanas distintas: el perfil en la Frontal y el camino en la Superior.", "malo");
        return;
      }
      await pedir("barrer", { ids }, "BARRER");
    },
  });

  Comandos.registrar({
    nombre: "LOFT", alias: ["PIEL", "TRANSICION"],
    ayuda: "LOFT [separación] · una piel que pasa por las secciones que señalaste, en ese orden: con contornos cerrados un sólido, con curvas abiertas una superficie",
    correr: async (args) => {
      const ids = seleccion();
      if (ids.length < 2) {
        Comandos.eco("Señala al menos dos secciones y vuelve a dar LOFT.", "malo");
        return;
      }
      let sep = parseFloat(args[0]);
      if (!isFinite(sep)) {
        if (typeof Entrada === "undefined" || !Entrada.pedirNumero) sep = 0;
        else sep = await Entrada.pedirNumero({
          mensaje: "Separación entre secciones (0 si las dibujaste en ventanas distintas)",
          valor: 100, clave: "loft-separacion",
        });
      }
      if (!isFinite(sep)) sep = 0;
      await pedir("loft", { ids, separacion: sep }, "LOFT");
    },
  });

  /* Barrido por dos rieles (fase D1b): el perfil toca con sus puntas el
   * arranque de los dos rieles; se señalan las tres en cualquier orden. */
  Comandos.registrar({
    nombre: "BARRER2", alias: ["SWEEP2", "DOSRIELES"],
    ayuda: "BARRER2 · una superficie: el perfil recorre dos rieles tocando los dos (señala las tres curvas)",
    correr: async () => {
      const ids = seleccion();
      if (ids.length !== 3) {
        Comandos.eco("Señala el perfil y los dos rieles (tres curvas abiertas) y vuelve a dar BARRER2.", "malo");
        return;
      }
      await pedir("barrer2", { ids }, "BARRER2");
    },
  });

  /* Superficie por su borde (fase D1): las curvas señaladas cierran un lazo
   * punta con punta y el parche pasa por todas. El NetworkSrf de Rhino. */
  Comandos.registrar({
    // «RED» no: ése es el alias de REDONDEAR desde antes, y ganaba él (t058).
    nombre: "PARCHE", alias: ["NETWORKSRF", "EDGESRF"],
    ayuda: "PARCHE · una superficie que cierra el borde de las curvas señaladas (se tocan punta con punta)",
    correr: async () => {
      const ids = seleccion();
      if (ids.length < 2) {
        Comandos.eco("Señala las curvas que cierran el borde (al menos dos) y vuelve a dar PARCHE.", "malo");
        return;
      }
      await pedir("red", { ids }, "PARCHE");
    },
  });

  Comandos.registrar({
    nombre: "CRECER", alias: ["EXTRUIRCARA", "EXTRUDEFACE"],
    ayuda: "CRECER · levanta material nuevo con el perfil de la cara señalada (no estira la cara)",
    correr: async (args) => {
      const cara = (typeof TresD !== "undefined" && TresD.senalada) ? TresD.senalada() : null;
      if (!cara) {
        Comandos.eco("Primero señala una cara: teclea 3D y dale un clic a la cara de la que quieres que crezca.", "malo");
        return;
      }
      let mm = parseFloat(args[0]);
      if (!isFinite(mm)) {
        if (typeof Entrada === "undefined" || !Entrada.pedirNumero) {
          Comandos.eco("CRECER necesita una medida.", "malo");
          return;
        }
        mm = await Entrada.pedirNumero({ mensaje: `Cuánto crece desde «${cara.cara}» (mm)`, valor: 20, clave: "crecer-mm" });
      }
      if (!isFinite(mm) || mm === 0) return;
      try {
        await fetch(`/api/cuerpo/${cara.id}/crecer-cara`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cara: cara.cara, mm, unir: true }),
        }).then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || r.status); return j; });
        await Cuerpos.refrescar();
        if (typeof Historial !== "undefined" && Historial.traer) Historial.traer();
        Comandos.eco(`creció ${mm} mm desde «${cara.cara}»`);
      } catch (e) { Comandos.eco("No se pudo crecer: " + e.message, "malo"); }
    },
  });
})();
