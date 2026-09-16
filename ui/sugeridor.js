/* Sugeridor de comandos  ·  lo pidió Mike el 16-sep.
 *
 * «Si tecleas C, que sugiera COPIAR o CIRCULO o lo que empiece con C.»
 *
 * Al teclear en la consola sale una lista con lo que empieza así: el nombre,
 * sus atajos y para qué sirve. Las flechas eligen y Enter corre.
 *
 * **Las flechas ya tenían dueño**: suben y bajan por el historial de comandos.
 * El reparto es por lo que hay escrito. Con la caja vacía siguen siendo el
 * historial, como siempre; en cuanto hay algo tecleado y hay sugerencias, las
 * flechas eligen entre ellas. De paso se arregla algo feo: hasta ahora, teclear
 * «C» y apretar la flecha borraba lo escrito.
 *
 * El truco que hace esto sencillo: al elegir con las flechas, **el nombre se
 * escribe en la caja**. Así Enter no necesita saber que el sugeridor existe —
 * corre lo que está escrito, como toda la vida—. Menos piezas enteradas unas de
 * otras, menos formas de romperse.
 *
 * Se busca por el nombre y por los atajos, y en español y en inglés, porque el
 * programa acepta las dos cosas: quien teclea CIRCLE encuentra CIRCULO.
 */

const Sugeridor = (() => {
  const TOPE = 8;                 // más que esto tapa el dibujo y no ayuda
  let lista = null, elegido = -1, opciones = [];

  function campo() {
    return document.getElementById("cmd");
  }

  function armar() {
    if (lista) return;
    lista = document.createElement("div");
    lista.id = "sugerencias";
    Object.assign(lista.style, {
      position: "absolute", display: "none", zIndex: "40",
      background: "#1d1f22", color: "#eee", border: "1px solid #3a3d42",
      borderRadius: "6px", overflow: "hidden", minWidth: "320px",
      boxShadow: "0 8px 24px rgba(0,0,0,0.45)", font: "13px system-ui, sans-serif",
    });
    document.body.appendChild(lista);
  }

  function colocar() {
    const c = campo();
    if (!c) return;
    const r = c.getBoundingClientRect();
    lista.style.left = `${r.left}px`;
    lista.style.width = `${Math.max(320, r.width)}px`;
    // Sale ARRIBA de la caja: la consola vive abajo y una lista que baje se
    // sale de la ventana.
    lista.style.bottom = `${window.innerHeight - r.top + 4}px`;
  }

  /** Los comandos cuyo nombre o atajo empieza con lo tecleado. */
  function buscar(texto) {
    const t = String(texto || "").trim().toUpperCase();
    if (!t || typeof Comandos === "undefined") return [];
    const todos = Comandos.lista || [];
    const porNombre = [], porAlias = [];
    for (const cmd of todos) {
      const nombre = String(cmd.nombre || "");
      if (nombre.startsWith(t)) { porNombre.push({ cmd, como: nombre }); continue; }
      const alias = (cmd.alias || []).find((a) => String(a).toUpperCase().startsWith(t));
      if (alias) porAlias.push({ cmd, como: String(alias).toUpperCase() });
    }
    // Lo que Enter correría **ahora mismo** va primero. Si tecleas «C», el
    // programa corre CIRCULO —ése es su atajo—, así que CIRCULO tiene que
    // encabezar la lista. Una sugerencia que no coincide con lo que de verdad
    // va a pasar es peor que no sugerir nada.
    const exacto = (o) => o.cmd.nombre === t || (o.cmd.alias || []).some((a) => String(a).toUpperCase() === t);
    const orden = (a, b) => (exacto(b) - exacto(a)) || (a.cmd.nombre.length - b.cmd.nombre.length);
    porNombre.sort(orden);
    porAlias.sort(orden);
    return [...porNombre, ...porAlias].sort((a, b) => exacto(b) - exacto(a)).slice(0, TOPE);
  }

  function pintar() {
    lista.innerHTML = "";
    opciones.forEach((o, i) => {
      const fila = document.createElement("div");
      Object.assign(fila.style, {
        padding: "5px 10px", cursor: "pointer", display: "flex", gap: "10px",
        alignItems: "baseline",
        background: i === elegido ? "#3a3d42" : "transparent",
      });
      const nom = document.createElement("b");
      nom.textContent = o.cmd.nombre;
      nom.style.minWidth = "7em";
      const ayuda = document.createElement("span");
      ayuda.style.color = "#9b9da3";
      ayuda.style.fontSize = "12px";
      const atajos = (o.cmd.alias || []).join(", ");
      ayuda.textContent = (o.cmd.ayuda || "") + (atajos ? `   ·   ${atajos}` : "");
      fila.append(nom, ayuda);
      fila.onmousedown = (e) => { e.preventDefault(); escoger(i); correrElegido(); };
      lista.appendChild(fila);
    });
    colocar();
    lista.style.display = opciones.length ? "block" : "none";
  }

  function escoger(i) {
    elegido = i;
    const c = campo();
    if (c && opciones[i]) c.value = opciones[i].cmd.nombre;
    pintar();
  }

  function correrElegido() {
    const c = campo();
    if (!c) return;
    cerrar();
    if (typeof Comandos !== "undefined") Comandos.correr(c.value);
    c.value = "";
  }

  function cerrar() {
    elegido = -1;
    opciones = [];
    if (lista) lista.style.display = "none";
  }

  function alTeclear() {
    armar();
    const c = campo();
    opciones = buscar(c ? c.value : "");
    elegido = -1;
    pintar();
  }

  /** La llama `comandos.js` antes de tocar el historial. Devuelve `true` si el
   *  sugeridor se quedó con la flecha, y entonces el historial no se mueve. */
  function mover(paso) {
    if (!opciones.length) return false;
    escoger((elegido + paso + opciones.length + (elegido < 0 && paso < 0 ? 1 : 0)) % opciones.length);
    return true;
  }

  function conectar() {
    armar();
    const c = campo();
    if (!c) return;
    c.addEventListener("input", alTeclear);
    c.addEventListener("blur", () => setTimeout(cerrar, 120));
    window.addEventListener("resize", () => { if (opciones.length) colocar(); });
    // Enter, espacio y Escape los maneja la consola; aquí sólo se recoge la lista.
    c.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === "Escape" || e.key === " ") cerrar();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", conectar);
  } else {
    conectar();
  }

  return { mover, cerrar, conectar, buscar };
})();
