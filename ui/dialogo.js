/* Cuadros de diálogo  ·  un solo constructor para todos.
 *
 * Hasta ahora todo lo que pedía varios datos —el pie de plano, el estilo de
 * cota, una hoja nueva— se preguntaba **campo por campo en la línea de
 * comandos**. Mike lo dijo claro sobre las hojas: *«hacer más amigable la
 * creación de planos/hojas, no en la línea de comandos»*. Preguntar en fila
 * tiene un problema que no es de gusto: no puedes ver lo que ya contestaste,
 * no puedes corregir el tercer campo sin cancelar los siete, y no sabes cuántos
 * faltan.
 *
 * Así que aquí se arma un formulario de verdad, y se arma **desde una lista de
 * campos** para no escribir el mismo HTML cuatro veces:
 *
 *     const v = await Dialogo.abrir({
 *       titulo: "Hoja nueva",
 *       campos: [
 *         {clave: "formato", etiqueta: "Formato", tipo: "lista",
 *          opciones: [["A3", "A3 · 420 × 297"], …], valor: "A3"},
 *         {clave: "ancho", etiqueta: "Ancho", tipo: "numero", valor: 420,
 *          visible: (v) => v.formato === "CUSTOM"},
 *       ],
 *     });
 *     if (!v) return;            // canceló
 *
 * Devuelve un objeto con los valores, o `null` si se canceló. Esc cancela,
 * Enter acepta —salvo en un área de texto—, y el foco entra en el primer campo.
 */

const Dialogo = (() => {
  let abierto = null;

  function cerrar(valor) {
    if (!abierto) return;
    const { caja, resolver } = abierto;
    abierto = null;
    caja.remove();
    document.removeEventListener("keydown", alTeclear, true);
    resolver(valor);
  }

  function alTeclear(e) {
    if (!abierto) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cerrar(null); }
    else if (e.key === "Enter" && e.target.tagName === "TEXTAREA" && e.target.dataset.enterAcepta) {
      // El texto de párrafo (Mike, 9-sep-2026): **Enter termina y guarda**;
      // **Alt+Enter** (o Shift+Enter) mete el renglón nuevo.
      if (e.altKey || e.shiftKey) {
        e.preventDefault(); e.stopPropagation();
        const t = e.target, i = t.selectionStart, j = t.selectionEnd;
        t.value = t.value.slice(0, i) + "\n" + t.value.slice(j);
        t.selectionStart = t.selectionEnd = i + 1;
        t.dispatchEvent(new Event("input", { bubbles: true }));
      } else { e.preventDefault(); e.stopPropagation(); aceptar(); }
    }
    else if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") {
      e.preventDefault(); e.stopPropagation(); aceptar();
    }
    // En un campo numérico el espacio no sirve de nada: acepta, como Enter.
    else if (e.key === " " && e.target.tagName === "INPUT" && e.target.inputMode === "decimal") {
      e.preventDefault(); e.stopPropagation(); aceptar();
    }
  }

  function leer() {
    // El cuadro puede haberse cerrado ya: un `input` o un `change` que se
    // dispara al soltar el foco llega después de `cerrar()`, y leer campos de
    // un cuadro que ya no está tiraba un error a la consola.
    if (!abierto) return {};
    const v = {};
    for (const c of abierto.campos) {
      const el = abierto.caja.querySelector(`[data-clave="${c.clave}"]`);
      if (!el) { v[c.clave] = c.valor; continue; }
      if (c.tipo === "nota") continue;
      if (c.tipo === "casilla") v[c.clave] = el.checked;
      else if (c.tipo === "numero") {
        const n = parseFloat(el.value.replace(",", "."));
        v[c.clave] = isFinite(n) ? n : c.valor;
      } else v[c.clave] = el.value;
    }
    return v;
  }

  /* Los campos que sólo aplican a veces —el ancho a la medida sólo si el
   * formato es CUSTOM— se esconden en vez de desaparecer del resultado: quien
   * llama recibe siempre las mismas llaves. */
  function refrescarVisibles() {
    if (!abierto) return;
    const v = leer();
    for (const c of abierto.campos) {
      if (!c.visible) continue;
      const fila = abierto.caja.querySelector(`[data-fila="${c.clave}"]`);
      if (fila) fila.hidden = !c.visible(v);
    }
  }

  function aceptar() {
    if (!abierto) return;
    const v = leer();
    if (abierto.validar) {
      const queja = abierto.validar(v);
      if (queja) {
        const av = abierto.caja.querySelector(".queja");
        av.textContent = queja;
        av.hidden = false;
        return;
      }
    }
    cerrar(v);
  }

  function control(c) {
    if (c.tipo === "lista") {
      const s = document.createElement("select");
      for (const o of c.opciones) {
        const op = document.createElement("option");
        op.value = Array.isArray(o) ? o[0] : o;
        op.textContent = Array.isArray(o) ? o[1] : o;
        s.appendChild(op);
      }
      s.value = c.valor;
      return s;
    }
    // Un párrafo necesita renglones de verdad. Enter dentro del área es un
    // renglón nuevo y no acepta el cuadro: eso ya lo distingue `alTeclear`.
    // Un bloque de texto de sólo lectura (licencias, avisos): se lee, no se
    // captura. `leer()` lo salta.
    if (c.tipo === "nota") {
      const n = document.createElement("div");
      n.className = "nota" + (c.alto ? " alta" : "");
      n.textContent = c.valor ?? "";
      if (c.html) n.innerHTML = c.html;
      return n;
    }
    if (c.tipo === "area") {
      const t = document.createElement("textarea");
      t.rows = c.renglones || 4;
      t.value = c.valor ?? "";
      if (c.marcador) t.placeholder = c.marcador;
      if (c.enterAcepta) t.dataset.enterAcepta = "1";
      return t;
    }
    const i = document.createElement("input");
    if (c.tipo === "casilla") { i.type = "checkbox"; i.checked = !!c.valor; }
    else if (c.tipo === "color") { i.type = "color"; i.value = c.valor || "#000000"; }
    else if (c.tipo === "numero") { i.type = "text"; i.value = String(c.valor ?? ""); i.inputMode = "decimal"; }
    else { i.type = "text"; i.value = c.valor ?? ""; }
    if (c.marcador) i.placeholder = c.marcador;
    return i;
  }

  /** Abre el cuadro y devuelve una promesa con los valores, o null. */
  function abrir({ titulo, pista, campos, aceptar: etAceptar = "Aceptar",
                   cancelar: etCancelar = "Cancelar", validar, ancho, extra = null }) {
    if (abierto) cerrar(null);
    const caja = document.createElement("div");
    caja.className = "dlg";
    const panel = document.createElement("div");
    panel.className = "panel";
    if (ancho) panel.style.width = ancho;
    caja.appendChild(panel);

    const h = document.createElement("div");
    h.className = "cab";
    h.innerHTML = `<b></b>`;
    h.querySelector("b").textContent = titulo;
    panel.appendChild(h);

    if (pista) {
      const p = document.createElement("div");
      p.className = "pista";
      p.textContent = pista;
      panel.appendChild(p);
    }

    const cuerpo = document.createElement("div");
    cuerpo.className = "cuerpo";
    panel.appendChild(cuerpo);

    for (const c of campos) {
      if (c.tipo === "titulo") {
        const t = document.createElement("div");
        t.className = "seccion";
        t.textContent = c.etiqueta;
        cuerpo.appendChild(t);
        continue;
      }
      const fila = document.createElement("label");
      fila.className = "fila" + (c.tipo === "casilla" ? " casilla" : "");
      fila.dataset.fila = c.clave;
      const et = document.createElement("span");
      et.className = "et";
      et.textContent = c.etiqueta;
      const ctl = control(c);
      ctl.dataset.clave = c.clave;
      if (c.tipo === "casilla") { fila.appendChild(ctl); fila.appendChild(et); }
      else { fila.appendChild(et); fila.appendChild(ctl); }
      if (c.sufijo) {
        const s = document.createElement("span");
        s.className = "suf";
        s.textContent = c.sufijo;
        fila.appendChild(s);
      }
      cuerpo.appendChild(fila);
      if (c.pista) {
        const p = document.createElement("div");
        p.className = "subpista";
        p.textContent = c.pista;
        p.dataset.fila = c.clave;
        cuerpo.appendChild(p);
      }
      ctl.addEventListener("input", () => { refrescarVisibles(); if (c.alCambiar) c.alCambiar(leer(), caja); });
      ctl.addEventListener("change", () => { refrescarVisibles(); if (c.alCambiar) c.alCambiar(leer(), caja); });
    }

    const queja = document.createElement("div");
    queja.className = "queja";
    queja.hidden = true;
    panel.appendChild(queja);

    const pie = document.createElement("div");
    pie.className = "pie";
    const bCan = document.createElement("button");
    bCan.className = "gh";
    bCan.textContent = etCancelar;
    bCan.onclick = () => cerrar(null);
    const bOk = document.createElement("button");
    bOk.className = "pri";
    bOk.textContent = etAceptar;
    bOk.onclick = aceptar;
    // Un tercer botón, a la izquierda, que hace algo **sin cerrar** el cuadro
    // (la vista previa de impresión): recibe los valores de ese momento.
    if (extra && extra.etiqueta) {
      const bX = document.createElement("button");
      bX.className = "gh extra";
      bX.textContent = extra.etiqueta;
      bX.onclick = () => { if (abierto) extra.accion(leer()); };
      pie.append(bX);
      bX.style.marginRight = "auto";
    }
    // `cancelar: null` → sólo un botón (cuadros de sólo lectura).
    if (etCancelar === null) pie.append(bOk); else pie.append(bCan, bOk);
    panel.appendChild(pie);

    // Clic fuera del panel = cancelar. Es lo que espera cualquiera, y evita
    // dejar un cuadro clavado encima del dibujo.
    caja.addEventListener("mousedown", (e) => { if (e.target === caja) cerrar(null); });

    document.body.appendChild(caja);
    document.addEventListener("keydown", alTeclear, true);

    return new Promise((resolver) => {
      abierto = { caja, campos, resolver, validar };
      refrescarVisibles();
      const primero = caja.querySelector(".cuerpo [data-clave]");
      // Se enfoca dos veces a propósito. Cuando el cuadro se abre justo
      // después de un clic en el lienzo —que es el caso del texto: se pica
      // dónde va y sale el cuadro— el navegador todavía tiene pendiente la
      // acción por omisión de ese `mousedown`, que manda el foco al `body` y
      // se lleva por delante el `focus()` de aquí. Entonces lo que se teclea
      // se va a la línea de comandos y parece que el cuadro no deja escribir,
      // que es exactamente lo que reportó Mike del comando TEXTO.
      const enfocar = () => {
        if (!abierto || !primero) return;
        primero.focus();
        if (primero.select) primero.select();
      };
      enfocar();
      requestAnimationFrame(enfocar);
    });
  }

  const activo = () => !!abierto;

  return { abrir, cerrar, activo };
})();
