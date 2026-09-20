/* El historial de una pieza, visible y editable  ·  0.15.0
 *
 * Mike, el 19-sep: *«la parametrización del modelo me interesa muchísimo. El
 * mantener algo de historial de cómo se generó un barreno (ej. se hace un
 * trazo de un cilindro y se resta al volumen), pero después se quiere agrandar
 * o achicar: sólo se podría incrementar o disminuir el diámetro del cilindro
 * original sin necesidad de trazarlo todo de nuevo»*.
 *
 * Eso el motor lo hacía desde el primer día —una pieza **es** su lista de
 * operaciones, y regenerar es volver a correrlas—. Lo que faltaba era
 * enseñarlo. Este panel es todo lo nuevo: lista los pasos en palabras del
 * taller y deja tocar sus números.
 *
 * **Cada número que se toca va al motor y la pieza se rehace entera.** No se
 * parcha la geometría: se vuelve a construir desde el contorno. Por eso un
 * redondeo hecho después de un barreno sigue ahí cuando el barreno cambia de
 * diámetro, y sigue ahí incluso si el barreno se borra del historial.
 *
 * Si un cambio deja la pieza imposible, el motor deshace y lo dice. El peor
 * caso de tocar un número es que no pase nada, y por eso se puede tocar sin
 * miedo.
 */

const Historial = (() => {
  let idActual = null;
  let pasos = [];
  /** Las peticiones del panel van **en fila, no a empujones**.
   *
   *  Antes había una bandera «pidiendo» y el que llegaba con una en vuelo se
   *  daba media vuelta sin traer nada. Eso deja el panel con los pasos viejos
   *  justo cuando más importa: señalas una pieza y en seguida le cambias un
   *  número, y el segundo `traer()` —el que trae los pasos nuevos— era el que
   *  se perdía. Con una fila, todos los que piden acaban pidiendo, y en orden.
   *  (Cazado el 19-sep por la prueba de la etapa B, que fallaba una vez de
   *  cada tres.) */
  let fila = Promise.resolve();

  const $ = (s) => document.querySelector(s);

  function caja() { return $("#props-historial"); }
  function lista() { return $("#hist-pasos"); }

  // --- traer y pintar ------------------------------------------------------

  async function alSenalar(senalada) {
    const id = senalada ? senalada.id : null;
    if (id === idActual) return;
    idActual = id;
    await traer();
  }

  function traer() {
    fila = fila.then(_traer, _traer);
    return fila;
  }

  async function _traer() {
    if (!idActual) { pasos = []; pintar(); return; }
    const id = idActual;
    try {
      const r = await fetch(`/api/cuerpo/${id}/historial`);
      const j = await r.json();
      // Si mientras se pedía se señaló otra pieza, lo que llegó ya no es de
      // ésta: se tira. Lo trae el siguiente de la fila.
      if (id !== idActual) return;
      pasos = r.ok ? (j.pasos || []) : [];
    } catch (e) { if (id === idActual) pasos = []; }
    pintar();
  }

  function pintar() {
    const c = caja(), l = lista();
    if (!c || !l) return;
    if (!idActual || !pasos.length) { c.hidden = true; l.innerHTML = ""; return; }
    c.hidden = false;
    l.innerHTML = "";
    for (const p of pasos) l.appendChild(filaDe(p));
  }

  function filaDe(p) {
    const bloque = document.createElement("div");
    bloque.className = "paso";

    const cab = document.createElement("div");
    cab.className = "paso-cab";
    const t = document.createElement("b");
    t.textContent = p.titulo;
    t.title = `paso ${p.i} · ${p.op}`;
    cab.appendChild(t);
    if (!p.de_nacimiento) {
      const x = document.createElement("button");
      x.className = "cerrar";
      x.textContent = "×";
      x.title = "Quitar este paso del historial";
      x.onclick = () => quitar(p.i);
      cab.appendChild(x);
    }
    bloque.appendChild(cab);

    for (const campo of p.campos || []) {
      const fila = document.createElement("div");
      fila.className = "fila";
      const et = document.createElement("label");
      et.textContent = campo.etiqueta;
      const con = document.createElement("div");
      con.className = "con-suf";
      const inp = document.createElement("input");
      inp.type = "text";
      inp.inputMode = "decimal";
      inp.value = campo.valor;
      // Enter aplica y Escape devuelve el valor de antes: es lo que hacen
      // todas las cajitas del programa, y las manos ya lo saben.
      inp.onkeydown = (e) => {
        e.stopPropagation();
        if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
        if (e.key === "Escape") { inp.value = campo.valor; inp.blur(); }
      };
      inp.onchange = () => aplicar(p.i, campo, inp);
      const suf = document.createElement("span");
      suf.className = "suf";
      suf.textContent = campo.unidad || "";
      con.appendChild(inp);
      con.appendChild(suf);
      fila.appendChild(et);
      fila.appendChild(con);
      bloque.appendChild(fila);
    }
    return bloque;
  }

  // --- tocar ---------------------------------------------------------------

  function numero(texto) {
    // Coma o punto, como en todo el programa: un taller mexicano teclea las dos.
    const v = parseFloat(String(texto).replace(",", "."));
    return isFinite(v) ? v : null;
  }

  async function aplicar(i, campo, inp) {
    const v = numero(inp.value);
    if (v === null) { inp.value = campo.valor; return; }
    if (campo.minimo !== null && campo.minimo !== undefined && v < campo.minimo) {
      Comandos.eco(`${campo.etiqueta} no puede ser menor que ${campo.minimo}.`, "malo");
      inp.value = campo.valor;
      return;
    }
    if (v === campo.valor) return;
    try {
      const r = await fetch(`/api/cuerpo/${idActual}/paso/${i}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ campos: { [campo.clave]: v } }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.status);
      await trasCambiar(j, `${campo.etiqueta} = ${v}`);
    } catch (e) {
      // El motor ya deshizo: la pieza sigue como estaba y la cajita también.
      inp.value = campo.valor;
      Comandos.eco("No se pudo: " + e.message, "malo");
    }
  }

  async function quitar(i) {
    try {
      const r = await fetch(`/api/cuerpo/${idActual}/paso/${i}`, { method: "DELETE" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.status);
      await trasCambiar(j, "paso quitado");
    } catch (e) {
      Comandos.eco("No se pudo quitar: " + e.message, "malo");
    }
  }

  /** Lo que hay que hacer siempre que el historial cambió: rehacer la malla,
   *  olvidar los tiradores (los puntos de la pieza son otros) y volver a
   *  traer los pasos, porque un cambio puede renombrar lo de abajo. */
  async function trasCambiar(malla, que) {
    if (window.Tiradores) Tiradores.olvidar(idActual);
    if (window.Cuerpos) await Cuerpos.refrescarUna(idActual);
    if (window.Tiradores) Tiradores.cargar(idActual);
    await traer();
    if (malla && malla.caja) {
      Comandos.eco(`${que} · ahora ${malla.caja[0]} × ${malla.caja[1]} × ${malla.caja[2]}`);
    }
  }

  return { alSenalar, traer, pintar, trasCambiar,
           get id() { return idActual; }, get pasos() { return pasos; } };
})();

if (typeof window !== "undefined") window.Historial = Historial;
if (typeof module !== "undefined") module.exports = Historial;

/* --- los dos comandos que el motor ya sabía y nadie podía llamar ---------- */

if (typeof Comandos !== "undefined") {
  Comandos.registrar({
    nombre: "BARRENO", alias: ["BAR", "HOLE"],
    ayuda: "BARRENO — un barreno pasante en la pieza señalada: se pica el centro y se da el diámetro",
    correr: async () => {
      const id = (typeof Cuerpos !== "undefined" && Cuerpos.senalada) ? Cuerpos.senalada.id : null;
      if (!id) {
        Comandos.eco("Pica primero una cara de la pieza donde quieres el barreno.", "malo");
        return;
      }
      const p = await Entrada.pedirPunto({
        mensaje: "Centro del barreno",
        hule: (q) => ({ tipo: "circulo", c: q, r: 10 }),
      });
      if (!p) return;
      const d = await Entrada.pedirNumero({
        mensaje: "Diámetro", valor: 8, minimo: 0.02, clave: "barreno-diametro" });
      if (!isFinite(d) || d <= 0) return;
      try {
        // El punto llega en el plano de la ventana activa; se lleva al mundo,
        // que es lo que el motor sabe girar al plano de la pieza.
        const m = typeof Planos !== "undefined" && estado.vista
          ? Planos.aMundo(estado.vista.plano || "XY", p[0], p[1], 0) : [p[0], p[1], 0];
        const r = await fetch(`/api/cuerpo/${id}/barreno`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ centro: m, radio: d / 2 }),
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || r.status);
        await Historial.trasCambiar(j, `barreno ⌀${d}`);
      } catch (e) { Comandos.eco("No se pudo barrenar: " + e.message, "malo"); }
    },
  });

  Comandos.registrar({
    nombre: "REDONDEAR", alias: ["RED", "FILLET"],
    ayuda: "REDONDEAR [r] — redondea las aristas elegidas con Ctrl+clic; si no elegiste ninguna, las verticales",
    correr: async (args) => {
      const id = (typeof Cuerpos !== "undefined" && Cuerpos.senalada) ? Cuerpos.senalada.id : null;
      if (!id) {
        Comandos.eco("Pica primero una cara de la pieza que quieres redondear.", "malo");
        return;
      }
      let r = parseFloat(args[0]);
      if (!isFinite(r)) {
        r = await Entrada.pedirNumero({
          mensaje: "Radio del redondeo", valor: 3, minimo: 0.02, clave: "redondeo-radio" });
      }
      if (!isFinite(r) || r <= 0) return;
      try {
        // Las que se eligieron con Ctrl+clic mandan. Si no se eligió ninguna,
        // se toman las verticales —las que separan dos lados—, que son las que
        // un taller redondea cuando no dice otra cosa.
        let aristas = (typeof Tiradores !== "undefined") ? Tiradores.aristasElegidas(id) : [];
        const aMano = aristas.length > 0;
        if (!aMano) {
          const refs = await fetch(`/api/cuerpo/${id}/referencias`).then((x) => x.json());
          aristas = (refs.aristas || []).filter((a) => (a.match(/lado\[/g) || []).length === 2);
        }
        if (!aristas.length) {
          Comandos.eco("Esta pieza no tiene aristas verticales que redondear. "
            + "Elige las que quieras con Ctrl+clic sobre el círculo de en medio.", "malo");
          return;
        }
        const resp = await fetch(`/api/cuerpo/${id}/redondear`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ aristas, r }),
        });
        const j = await resp.json();
        if (!resp.ok) throw new Error(j.detail || resp.status);
        // Ya se usaron: se sueltan, o el siguiente REDONDEAR repetiría éstas
        // sin que nadie se lo pidiera.
        if (aMano && typeof Tiradores !== "undefined") Tiradores.soltarElegidas(id);
        await Historial.trasCambiar(j, `${aristas.length} arista(s) redondeada(s) r${r}`
          + (aMano ? " (las elegidas)" : " (las verticales)"));
      } catch (e) { Comandos.eco("No se pudo redondear: " + e.message, "malo"); }
    },
  });
}
