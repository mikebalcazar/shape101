/* shape101 — documento, capas y archivo.
 *
 * El lienzo y la navegación están en vista.js; las referencias a objetos en
 * osnap.js; la toma de puntos en entrada.js; la línea de comando en
 * comandos.js. Aquí queda lo que tiene que ver con el documento: el panel de
 * capas, abrir y guardar, deshacer, y el arranque.
 */

/* ===================================================================== */
/* Panel de capas                                                        */
/* ===================================================================== */
function cuentaPorCapa() {
  const c = {};
  for (const t of estado.trazos) c[t.capa] = (c[t.capa] || 0) + 1;
  return c;
}

function pintarCapas() {
  const r = estado.resumen;
  if (!r) return;
  const caja = $("#capas");
  const cuentas = cuentaPorCapa();
  const oscuro = document.documentElement.dataset.tema === "oscuro";
  caja.innerHTML = "";

  for (const capa of r.capas) {
    const fila = document.createElement("div");
    fila.className = "capa" + (capa.nombre === r.capa_activa ? " activa" : "");
    fila.title = capa.descripcion || capa.nombre;

    const ojo = document.createElement("button");
    ojo.className = "ojo" + (capa.visible ? "" : " off");
    ojo.textContent = capa.visible ? "◉" : "○";
    ojo.title = capa.visible ? "Apagar la capa" : "Encender la capa";
    ojo.onclick = (ev) => { ev.stopPropagation(); cambiarCapa(capa.nombre, { visible: !capa.visible }); };

    const llave = document.createElement("button");
    llave.className = "llave" + (capa.bloqueada ? " on" : "");
    llave.textContent = capa.bloqueada ? "🔒" : "🔓";
    llave.title = capa.bloqueada ? "Desbloquear" : "Bloquear";
    llave.onclick = (ev) => { ev.stopPropagation(); cambiarCapa(capa.nombre, { bloqueada: !capa.bloqueada }); };

    const muestra = document.createElement("div");
    muestra.className = "muestra";
    muestra.style.background = colorVisible(capa.color, oscuro);

    const nom = document.createElement("div");
    nom.className = "nom";
    nom.innerHTML = `${capa.nombre}<small>${capa.grosor / 100} mm · ${capa.tipo_linea.toLowerCase()}${capa.imprime ? "" : " · no imprime"}</small>`;

    const cuenta = document.createElement("div");
    cuenta.className = "cuenta";
    cuenta.textContent = cuentas[capa.nombre] || "";

    fila.append(ojo, llave, muestra, nom, cuenta);
    // Un clic la enseña; **dos** la ponen a trabajar  ·  punto 11.
    // Mike: cambiar de capa de trabajo sin querer, mientras se dibuja, manda
    // los siguientes trazos a la capa equivocada y no se nota hasta imprimir.
    // Ver sus propiedades no cuesta nada; cambiar dónde caen los trazos sí.
    fila.onclick = () => { estado.seleccion = capa.nombre; pintarCapas(); };
    fila.ondblclick = () => activarCapa(capa.nombre);
    // Clic derecho: sus propiedades, flotantes (Mike, 9-sep-2026: «el panel
    // de propiedades de la capa fuera de la vista; sólo con clic derecho»).
    fila.oncontextmenu = (ev) => { ev.preventDefault(); estado.seleccion = capa.nombre; pintarCapas(); PropsCapa.abrir(ev.clientX, ev.clientY); };
    caja.appendChild(fila);
  }
  pintarProps();
}

/* --- Propiedades de la capa, flotantes  ·  0.20.0 ----------------------- */
const PropsCapa = (() => {
  let abierto = false;
  function abrir(x, y) {
    const caja = $("#props");
    if (!caja) return;
    pintarProps();
    caja.hidden = false;
    abierto = true;
    const w = caja.offsetWidth || 270, h = caja.offsetHeight || 200;
    caja.style.left = Math.max(8, Math.min(x - w + 16, window.innerWidth - w - 8)) + "px";
    caja.style.top = Math.max(8, Math.min(y + 8, window.innerHeight - h - 8)) + "px";
    setTimeout(() => {
      document.addEventListener("mousedown", fuera, true);
      document.addEventListener("keydown", tecla, true);
    }, 0);
  }
  function cerrar() {
    const caja = $("#props");
    if (caja) caja.hidden = true;
    abierto = false;
    document.removeEventListener("mousedown", fuera, true);
    document.removeEventListener("keydown", tecla, true);
  }
  function fuera(e) { const caja = $("#props"); if (caja && !caja.contains(e.target)) cerrar(); }
  function tecla(e) { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cerrar(); } }
  return { abrir, cerrar, get abierto() { return abierto; } };
})();
window.PropsCapa = PropsCapa;
{ const b = $("#p-cerrar"); if (b) b.onclick = () => PropsCapa.cerrar(); }

function capaSel() {
  const r = estado.resumen;
  return r.capas.find((c) => c.nombre === estado.seleccion)
      || r.capas.find((c) => c.nombre === r.capa_activa);
}

function pintarProps() {
  const c = capaSel();
  if (!c) return;
  const tit = $("#p-titulo");
  if (tit) tit.textContent = `${Tr("Capa")} ${c.nombre}`;
  $("#p-nombre").value = c.nombre;
  $("#p-nombre").disabled = c.nombre === "0";
  $("#p-color").value = c.color.length === 7 ? c.color : "#ffffff";

  const g = $("#p-grosor");
  g.innerHTML = "";
  for (const v of estado.resumen.grosores) {
    const o = document.createElement("option");
    o.value = v; o.textContent = (v / 100).toFixed(2) + " mm";
    g.appendChild(o);
  }
  g.value = c.grosor;

  const tl = $("#p-tl");
  tl.innerHTML = "";
  const tipos = { ...estado.resumen.tipos_linea };
  // Un archivo ajeno puede traer tipos de línea que no son de la casa. No se
  // esconden: se enseñan, o el desplegable saldría vacío y el usuario creería
  // que la capa no tiene ninguno.
  if (!(c.tipo_linea in tipos)) tipos[c.tipo_linea] = c.tipo_linea + " (del archivo)";
  for (const [k, desc] of Object.entries(tipos)) {
    const o = document.createElement("option");
    o.value = k; o.textContent = desc;
    tl.appendChild(o);
  }
  tl.value = c.tipo_linea;

  $("#p-imprime").checked = c.imprime;
  $("#p-imprime-txt").textContent = c.imprime ? "sí" : "no";
}

/** La pone a trabajar: los trazos nuevos caen aquí. Doble clic, o el comando
 *  CAPA. */
async function activarCapa(nombre) {
  estado.seleccion = nombre;
  try {
    aplicar(await post(`/api/capa_activa/${encodeURIComponent(nombre)}`));
    Comandos.eco(`Capa de trabajo: ${nombre}`);
  } catch (e) { avisar(e.message, true); }
}

/* El nombre viejo sigue existiendo porque lo llaman los comandos y las
 * pruebas, y ahí «seleccionar una capa» sí quiere decir activarla. */
const seleccionarCapa = activarCapa;

async function cambiarCapa(nombre, cambios) {
  try {
    const r = await patch(`/api/capa/${encodeURIComponent(nombre)}`, { cambios });
    aplicar(r);
    if (!aplicarParche(r)) await recargarTrazos();
  } catch (e) { avisar(e.message, true); }
}

/* ===================================================================== */
/* Estado y refresco                                                     */
/* ===================================================================== */
function aplicar(resumen) {
  estado.resumen = resumen;
  if (!estado.seleccion || !resumen.capas.some((c) => c.nombre === estado.seleccion)) {
    estado.seleccion = resumen.capa_activa;
  }
  $("#nombre-doc").textContent = resumen.nombre;
  $("#ruta-doc").textContent = resumen.ruta ? "· " + resumen.ruta : "";
  const fu = $("#f-unidades");
  if (fu && fu.textContent !== (resumen.unidades || "mm")) fu.textContent = resumen.unidades || "mm";
  $("#sucio").classList.toggle("si", resumen.sucio);
  if (window.Marco) Marco.pintarDocs(resumen.escritorio);
  $("#f-entidades").textContent = resumen.entidades;
  $("#f-capas").textContent = resumen.capas.length;
  $("#f-activa").textContent = resumen.capa_activa;
  // El DWG ya no depende de que instalen nada: los motores van dentro. Lo
  // que se dice es *con cuál* se está leyendo, porque el ODA es más fiel.
  const dwg = resumen.dwg || {};
  $("#f-dwg").textContent =
    dwg.oda ? "DWG · ODA File Converter"
    : dwg.empotrado ? "DWG · motor propio"
    : "DWG no disponible";
  $("#f-dwg").title =
    (dwg.oda ? "Se usa el ODA File Converter, que es el más fiel."
    : dwg.empotrado ? "LibreDWG y acad-ts, dentro del programa. Instalar el ODA File Converter (gratuito) convierte más rápido y más fiel."
    : "No se encontró con qué leer DWG en esta máquina.") + "\nClic: instalar o actualizar el ODA.";
  $("#f-dwg").style.cursor = "pointer";
  $("#f-dwg").onclick = () => window.Ajustes && Ajustes.oda();

  const b1 = $("#b-deshacer"), b2 = $("#b-rehacer");
  b1.disabled = !resumen.puede_deshacer;
  b2.disabled = !resumen.puede_rehacer;
  b1.title = resumen.puede_deshacer ? `Deshacer «${resumen.nombre_deshacer}» (Ctrl+Z)` : "Nada que deshacer";
  b2.title = resumen.puede_rehacer ? `Rehacer «${resumen.nombre_rehacer}» (Ctrl+Y)` : "Nada que rehacer";

  const inf = resumen.informe;
  const pres = inf ? Object.values(inf.preservadas || {}).reduce((a, b) => a + b, 0) : 0;
  $("#f-preservadas").textContent = pres
    ? `(${pres} preservadas: ${Object.keys(inf.preservadas).join(", ").toLowerCase()})` : "";

  pintarCapas();
  PanelCotas.pintar();
}

/* --- Cotas del documento  ·  0.20.0 --------------------------------------
 *
 * Mike (9-sep-2026): «un panel pequeño a la derecha con el tamaño de las cotas
 * de todo el documento (altura del texto y marcadores/flechas) para
 * ajustarlas de un jalón». Se enseñan **en unidades del dibujo** —lo que mide
 * el texto en el modelo—, que es lo que uno ve; por dentro es el estilo T101
 * (altura en mm de papel × DIMSCALE), el mismo que toca ESTILOCOTA. */
const PanelCotas = (() => {
  let estilo = null;
  let pidiendo = null;
  async function traer() {
    try {
      const r = await api("/api/estilos_cota");
      estilo = { ...((r.estilos || {})[r.activo || "T101"] || {}) };
    } catch (_) { estilo = estilo || {}; }
    return estilo;
  }
  function enDibujo(v) { return (parseFloat(v) || 0) * (parseFloat(estilo && estilo.factor_escala) || 1); }
  function pintar() {
    const caja = $("#props-cotas");
    if (!caja) return;
    const u = U();
    $("#pc-u1").textContent = u; $("#pc-u2").textContent = u;
    // El resumen trae el estilo activo: es la fuente más fresca (cambia con
    // ESTILOCOTA y al entrar a una hoja).
    if (estado.resumen && estado.resumen.estilo_cota) estilo = { ...estado.resumen.estilo_cota };
    if (!estilo) {
      if (!pidiendo) pidiendo = traer().then(() => { pidiendo = null; pintar(); });
      return;
    }
    const t = $("#pc-texto"), f = $("#pc-flecha");
    if (document.activeElement !== t) t.value = mm(enDibujo(estilo.altura_texto ?? 2.5));
    if (document.activeElement !== f) f.value = mm(enDibujo(estilo.tam_flecha ?? 2.0));
  }
  async function cambiar(clave, texto) {
    const n = parseFloat(String(texto).replace(",", "."));
    if (!(n > 0)) { avisar(Tr("El tamaño tiene que ser mayor que cero."), true); pintar(); return; }
    if (!estilo) await traer();
    const k = parseFloat(estilo.factor_escala) || 1;
    const cambios = { [clave]: n / k };
    try {
      const r = await post("/api/estilo_cota", { nombre: "T101", cambios });
      estilo = { ...estilo, ...(r.estilo || cambios) };
      aplicar(r);
      if (!aplicarParche(r)) await recargarTrazos();
      Comandos.eco(`${Tr(clave === "altura_texto" ? "Texto de las cotas" : "Flechas de las cotas")}: ${mm(n)} ${U()}.`);
    } catch (e) { avisar(e.message, true); }
    pintar();
  }
  function olvidar() { estilo = null; }
  function conectar() {
    const t = $("#pc-texto"), f = $("#pc-flecha"), b = $("#pc-estilo");
    if (!t) return;
    t.onchange = () => cambiar("altura_texto", t.value);
    f.onchange = () => cambiar("tam_flecha", f.value);
    for (const el of [t, f]) el.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); el.blur(); } e.stopPropagation(); };
    b.onclick = async () => { await Comandos.correr("ESTILOCOTA"); olvidar(); pintar(); };
  }
  return { pintar, conectar, olvidar, traer, get estilo() { return estilo; } };
})();
window.PanelCotas = PanelCotas;

async function recargarTrazos() {
  const d = await api("/api/trazos");
  if (!Array.isArray(d.trazos)) throw new Error("El motor no devolvió el dibujo (respuesta incompleta).");
  if (window.Bloques) Bloques.olvidar();     // las definiciones son de este dibujo
  // Y las piezas 3D también son de este dibujo. Hasta la 0.12.1 nadie las
  // pedía al abrir: había que teclear 3D para que aparecieran, y un archivo
  // guardado con piezas se veía vacío de piezas. No se espera a que lleguen:
  // el kernel puede tardar y el plano ya está listo; cuando llegan, se pintan.
  if (window.Cuerpos) { Cuerpos.olvidar(); if (window.Tiradores) Tiradores.olvidar(); Cuerpos.refrescar(); }
  estado.trazos = d.trazos;
  estado.geometria = d.geometria || [];
  if (estado.resumen) estado.resumen.extension = d.extension;
  pintarCapas();
  pintar();
}

/* Aplica el parche que devuelve una operación, en vez de volver a pedir el
 * dibujo entero.
 *
 * **Ésta es la diferencia entre 20 milisegundos y tres segundos.** Pedir todo
 * cuesta lo que mide el plano: en uno de 1 850 entidades son 6 MB y más de un
 * segundo sólo de red y de parseo, para enterarse de que se borró una línea.
 * El parche cuesta lo que mide **lo que cambió**, y eso no crece con el plano.
 *
 * Devuelve false si el servidor no mandó parche —una versión vieja, o una
 * operación que toca demasiado— y entonces el que llama recarga entero. Nunca
 * se queda a medias: entre pintar rápido y pintar bien, gana pintar bien.
 */
function aplicarParche(r) {
  const p = r && r.parche;
  if (!p || !Array.isArray(p.quitar)) return false;
  const fuera = new Set(p.quitar);
  let trazos = estado.trazos, geometria = estado.geometria;
  if (fuera.size) {
    trazos = trazos.filter((t) => !fuera.has(t.id));
    geometria = geometria.filter((g) => !fuera.has(g.id));
  }
  if (p.trazos && p.trazos.length) trazos = trazos.concat(p.trazos);
  if (p.geometria && p.geometria.length) geometria = geometria.concat(p.geometria);
  // El índice se parcha con lo mismo, en vez de rearmarse entero (ver
  // Indice.parchar): es él quien pone los arreglos nuevos en `estado`.
  if (typeof Indice !== "undefined" && Indice.parchar) Indice.parchar(p, trazos, geometria);
  else { estado.trazos = trazos; estado.geometria = geometria; }
  if (estado.resumen) estado.resumen.extension = p.extension;
  // Algo cambió de verdad: el parpadeo de «sí pasó» (Mike, 9-sep). Un parche
  // vacío —una operación que no tocó nada— no parpadea, y ése es el punto.
  if ((fuera.size || (p.trazos && p.trazos.length) || (p.geometria && p.geometria.length)) &&
      typeof Parpadeo !== "undefined") Parpadeo.exito();
  // Lo borrado deja de estar seleccionado: unos grips flotando sobre algo que
  // ya no existe son la clase de fantasma que hace dudar de todo lo demás.
  if (estado.sel && estado.sel.size) {
    // Con un conjunto, no con `some`: mover 2 000 entidades en un plano de
    // 44 000 trazos hacía 88 millones de comparaciones aquí (un segundo
    // entero) para saber qué se borró de verdad.
    const quedan = new Set();
    for (const t of estado.trazos) quedan.add(t.id);
    for (const id of fuera) {
      if (!quedan.has(id)) estado.sel.delete(id);
    }
  }
  // Deshacer una extrusión llega por aquí, no por `recargarTrazos`: si nadie
  // volviera a preguntar qué piezas hay, la pieza deshecha se quedaría pintada
  // encima de un contorno que ya nadie levantó. Preguntar cuesta una llamada
  // que no toca el kernel; sólo se piden las mallas que faltan.
  if (window.Cuerpos && (fuera.size || (p.trazos && p.trazos.length) ||
      (p.geometria && p.geometria.length))) Cuerpos.refrescar();
  pintarCapas();
  pintar();
  return true;
}

async function refrescar(encuadra = false) {
  aplicar(await api("/api/estado"));
  await recargarTrazos();
  if (encuadra) encuadrar(false);
}

/* ===================================================================== */
/* Interruptores del pie  ·  features 12, 13, 14, 15                     */
/* ===================================================================== */
const INTERRUPTORES = [
  ["sw-rejilla", "rejilla", "REJILLA"],
  ["sw-snap", "snap_rejilla", "SNAP"],
  ["sw-ortho", "ortho", "ORTHO"],
  ["sw-ref", "osnap", "REFERENCIAS"],
  ["sw-din", "dinamica", "DINAMICA"],
];

function pintarInterruptores() {
  const p = estado.prefs || {};
  for (const [id, clave] of INTERRUPTORES) {
    const b = $("#" + id);
    if (!b) continue;
    // ORTHO enseña lo que **está pasando**, no lo que dice la preferencia:
    // con Shift apretado está al revés, y el pie tiene que decirlo o uno cree
    // que no funcionó.
    b.classList.toggle("on", clave === "ortho" ? orthoActivo() : !!p[clave]);
  }
}

function conectarInterruptores() {
  for (const [id, , cmd] of INTERRUPTORES) {
    const b = $("#" + id);
    if (b) b.onclick = () => Comandos.correr(cmd);
  }
}

/* ===================================================================== */
/* Archivo                                                              */
/* ===================================================================== */
const enElectron = () => !!window.t101;

async function pedirRuta(modo, filtros, sugerido) {
  if (enElectron()) return window.t101[modo](filtros, sugerido);
  const r = prompt(modo === "abrir" ? "Ruta del archivo a abrir:" : "Ruta donde guardar:", sugerido || "");
  return r || null;
}

/* Abrir, guardar y dibujo nuevo viven aquí y no sueltos porque ahora los llama
 * también la pantalla de inicio, y antes eran tres `onclick` que sólo sabía
 * apretar un botón. */
const Archivo = (() => {
  /* Las extensiones, en un solo sitio. El defecto que Mike encontró el 24-sep
   * fue exactamente esto escrito tres veces y desincronizado: el motor guardaba
   * `.101s` y la interfaz seguía diciendo `.t101d`, así que sus propios
   * archivos **no aparecían** en el diálogo de Abrir y Guardar le volvía a
   * pedir la ruta cada vez. Una lista y de aquí salen todos los filtros. */
  const EXT_PROPIA = "101s";                    // lo que guarda shape101
  const EXT_DRAW = ["101d", "t101d"];           // lo que guarda draw101
  const FILTROS_ABRIR = [
    { name: "Dibujos y piezas", extensions: [EXT_PROPIA, ...EXT_DRAW, "dxf", "dwg"] },
    { name: "Pieza shape101", extensions: [EXT_PROPIA] },
    { name: "Dibujo draw101", extensions: EXT_DRAW },
    { name: "DXF", extensions: ["dxf"] },
    { name: "DWG", extensions: ["dwg"] },
  ];

  /** Trae un dibujo 2D **adentro** de la pieza que ya está abierta.
   *
   *  No es Abrir —eso reemplaza— ni REFEXT —eso entra bloqueado, para calcar—.
   *  Lo que entra por aquí se selecciona y se levanta con EXTRUIR. */
  async function importar() {
    const ruta = await pedirRuta("abrir", [
      { name: "Dibujo para importar", extensions: [...EXT_DRAW, EXT_PROPIA, "dxf", "dwg"] },
      { name: "Dibujo draw101", extensions: EXT_DRAW },
      { name: "DXF", extensions: ["dxf"] },
    ]);
    if (!ruta) return false;
    try {
      const r = await post("/api/importar", { ruta });
      aplicar(r);
      await recargarTrazos();
      const extra = [];
      if ((r.capas_nuevas || []).length) extra.push(`${r.capas_nuevas.length} capa(s) nueva(s)`);
      if (r.solidos_omitidos) extra.push(`${r.solidos_omitidos} pieza(s) 3D que no se traen`);
      Comandos.eco(`${r.importadas} entidad(es) desde ${r.archivo}, en el suelo`
        + (extra.length ? ` · ${extra.join(" · ")}` : "") + ".", "bien");
      return true;
    } catch (e) { avisar(e.message, true, 9000); return false; }
  }

  /** Abre un plano. En pestaña nueva, salvo que la de enfrente esté en blanco:
   *  abrir tres planos seguidos no debe dejar dos pestañas vacías detrás. */
  async function abrir(ruta) {
    const pestana = !(window.Marco && Marco.enBlanco());
    if (window.Marco) Marco.recordarVista();
    aplicar(await post("/api/abrir", { ruta, pestana }));
    estado.modo = "modelo";
    estado.sel.clear();
    await recargarTrazos();
    await Papel.pintarPestanas();
    encuadrar(false);
    const inf = estado.resumen.informe;
    if (inf) {
      const nat = Object.values(inf.nativas).reduce((a, b) => a + b, 0);
      const pre = Object.values(inf.preservadas).reduce((a, b) => a + b, 0);
      avisar(`Abierto: ${nat} entidades editables` +
        (pre ? ` y ${pre} que se conservan tal cual (${Object.keys(inf.preservadas).join(", ").toLowerCase()}).` : "."));
    }
    // Un DWG grande y sin ODA: se ofrece instalarlo, una sola vez en la vida
    // del programa (el motor lleva la cuenta). No se espera: el plano ya abrió.
    const mb = estado.resumen.sugerir_oda;
    if (mb && window.Ajustes) {
      setTimeout(() => Ajustes.oda({ motivo:
        `Este DWG pesa ${mb} MB. Con el ODA File Converter la primera apertura de un archivo así tarda 2 o 3 veces menos.` }), 800);
    }
    return true;
  }

  /** Pregunta la ruta y abre. Devuelve false si se canceló o falló. */
  async function pedirYAbrir() {
    const ruta = await pedirRuta("abrir", FILTROS_ABRIR);
    if (!ruta) return false;
    try { return await abrir(ruta); }
    catch (e) { avisar(e.message, true, 9000); return false; }
  }

  /** Guarda. `comoOtro` fuerza a preguntar la ruta aunque ya tenga una. */
  async function guardar(comoOtro = false) {
    let ruta = comoOtro ? null : estado.resumen.ruta;
    if (!ruta || !ruta.toLowerCase().endsWith("." + EXT_PROPIA)) {
      const base = (estado.resumen.nombre || "pieza").replace(/\.[^.]+$/, "");
      ruta = await pedirRuta("guardar",
        [{ name: "Pieza shape101", extensions: [EXT_PROPIA] }],
        base + (comoOtro ? " copia" : "") + "." + EXT_PROPIA);
    }
    if (!ruta) return false;
    try {
      aplicar(await post("/api/guardar", { ruta }));
      avisar(comoOtro ? `Guardado como ${estado.resumen.nombre}.` : "Guardado.");
      return true;
    } catch (e) { avisar(e.message, true); return false; }
  }

  return { abrir, pedirYAbrir, guardar, importar, FILTROS_ABRIR };
})();

/* Se conserva el nombre viejo: lo usan el doble clic de Windows y las pruebas. */
const abrirRuta = Archivo.abrir;

$("#b-nuevo").onclick = () => Marco.nuevoDoc();
$("#b-abrir").onclick = () => Archivo.pedirYAbrir();
const bImportar = $("#b-importar");
if (bImportar) bImportar.onclick = () => Archivo.importar();
$("#b-guardar").onclick = () => Archivo.guardar(false);
$("#b-guardar-como").onclick = () => Archivo.guardar(true);

$("#b-exportar").onclick = async () => {
  // El DWG sólo se ofrece si el conversor está instalado: ofrecer algo que no
  // se puede hacer y fallar después es peor que no ofrecerlo.
  const filtros = [{ name: "DXF R2013", extensions: ["dxf"] }];
  if ((estado.resumen.dwg || {}).puede) filtros.push({ name: "DWG R2013", extensions: ["dwg"] });
  const ruta = await pedirRuta("guardar", filtros,
    (estado.resumen.nombre || "dibujo") + ".dxf");
  if (!ruta) return;
  try {
    const r = await post("/api/exportar_dxf", { ruta });
    const formato = ruta.toLowerCase().endsWith(".dwg") ? "DWG" : "DXF";
    avisar(`${formato} exportado: ${r.escritas} entidades` +
      (r.preservadas ? `, ${r.preservadas} conservadas del original` : "") +
      (r.perdidas.length ? `. Sin escribir: ${r.perdidas.length}` : "."),
      r.perdidas.length > 0);
  } catch (e) { avisar(e.message, true); }
};

/* --- Deshacer / rehacer ------------------------------------------------ */
/* Deshacer y rehacer **siempre** vuelven a preguntar por las piezas y siempre
 * redibujan. Mike, 19-sep: «cuando das ctrl+Z, no se dibuja luego luego el
 * undo hasta que no haces otro comando».
 *
 * Por qué pasaba: lo que cambia en una pieza 3D no viaja en el parche de
 * trazos —una pieza no es un trazo—, así que deshacer una extrusión o un punto
 * movido devolvía un parche vacío. Con el parche vacío, `aplicarParche` no
 * creaba un arreglo de trazos nuevo, la llave del plano no cambiaba (ver
 * `llavePlano` en vista.js, que compara por identidad del arreglo) y el lienzo
 * reusaba el cuadro de antes. Se veía igual hasta que otro comando invalidaba
 * la caché, que es exactamente lo que Mike describió.
 *
 * Preguntar por las piezas cuesta una llamada que ni toca el kernel, y
 * deshacer no pasa sesenta veces por segundo. */
async function trasDeshacerORehacer(r, verbo) {
  aplicar(r);
  if (!aplicarParche(r)) await recargarTrazos();
  if (window.Cuerpos) {
    Cuerpos.olvidar();
    if (window.Tiradores) Tiradores.olvidar();
    Cuerpos.refrescar();
    // Deshacer también deshace pasos del historial: el panel tiene que volver
    // a preguntar, porque los pasos de la pieza ya son otros.
    if (window.Historial) Historial.traer();
  }
  if (window.invalidarPlano) window.invalidarPlano();
  pintar();
  if (r.accion) Comandos.eco(verbo + ": " + r.accion);
}
$("#b-deshacer").onclick = async () => {
  await trasDeshacerORehacer(await post("/api/deshacer"), "Deshecho");
};
$("#b-rehacer").onclick = async () => {
  await trasDeshacerORehacer(await post("/api/rehacer"), "Rehecho");
};

/* --- Capas: alta, baja y propiedades ----------------------------------- */
$("#b-capa-nueva").onclick = async () => {
  const nombre = prompt("Nombre de la capa nueva:", "T101-");
  if (!nombre) return;
  try {
    aplicar(await post("/api/capa", { nombre, color: "#0080C1", grosor: 25, tipo_linea: "CONTINUOUS" }));
    estado.seleccion = nombre.trim();
    pintarCapas();
  } catch (e) { avisar(e.message, true); }
};

$("#b-capa-borrar").onclick = async () => {
  const c = capaSel();
  if (!c) return;
  if (!confirm(`¿Borrar la capa «${c.nombre}»?`)) return;
  try {
    aplicar(await api(`/api/capa/${encodeURIComponent(c.nombre)}`, { method: "DELETE" }));
    await recargarTrazos();
  } catch (e) { avisar(e.message, true, 8000); }
};

$("#p-nombre").onchange = (e) => cambiarCapa(capaSel().nombre, { nombre: e.target.value });
$("#p-color").oninput = (e) => cambiarCapa(capaSel().nombre, { color: e.target.value.toUpperCase() });
$("#p-grosor").onchange = (e) => cambiarCapa(capaSel().nombre, { grosor: parseInt(e.target.value, 10) });
$("#p-tl").onchange = (e) => cambiarCapa(capaSel().nombre, { tipo_linea: e.target.value });
$("#p-imprime").onchange = (e) => cambiarCapa(capaSel().nombre, { imprime: e.target.checked });

/* --- Barra de herramientas --------------------------------------------- */
/* Los botones no son otra forma de hacer las cosas: **corren el mismo comando**
 * que se teclearía. Así la línea de comando enseña siempre lo que se hizo, y el
 * que quiera aprender los atajos los ve escritos cada vez que pica un botón. */
function conectarHerramientas() {
  for (const b of document.querySelectorAll("#herramientas button")) {
    b.onclick = () => Comandos.correr(b.dataset.cmd);
    // Clic derecho: las otras formas de la misma herramienta (ui/variantes.js).
    b.oncontextmenu = (e) => { e.preventDefault(); if (window.Variantes) Variantes.mostrar(b); };
  }
  if (window.Variantes) Variantes.marcar();
}

/* --- Vista y tema ------------------------------------------------------ */
$("#b-encuadrar").onclick = () => encuadrar();
$("#b-medir").onclick = () => Comandos.correr("MEDIR");
$("#b-tema").onclick = () => cambiarTema();

function cambiarTema() {
  const html = document.documentElement;
  const nuevo = html.dataset.tema === "oscuro" ? "claro" : "oscuro";
  html.dataset.tema = nuevo;
  guardarPrefs({ tema: nuevo });
  logoDelTema();
  pintarCapas();
  pintar();
}

/* El logotipo azul es para fondo claro; sobre el oscuro va el blanco. Son los
 * dos archivos que ya trae la identidad de Taller 101. */
function logoDelTema() {
  const oscuro = document.documentElement.dataset.tema === "oscuro";
  document.querySelector("header .marca img").src =
    oscuro ? "vendor/marca/shape101-blanco.png" : "vendor/marca/shape101.png";
}

/* --- Atajos ------------------------------------------------------------ */
/* En Mac los atajos van con ⌘, no con Ctrl: un mac que tenga que apretar
 * Ctrl+S se siente un programa mal portado, y además Ctrl+clic en macOS es el
 * clic derecho. Se aceptan los dos porque no chocan — ninguna máquina tiene
 * las dos teclas haciendo cosas distintas. */
const mandoPulsado = (e) => e.ctrlKey || e.metaKey;

window.addEventListener("keydown", (e) => {
  if (!mandoPulsado(e)) return;
  const k = e.key.toLowerCase();
  if (k === "z" && !e.shiftKey) { e.preventDefault(); $("#b-deshacer").click(); }
  else if (k === "y" || (k === "z" && e.shiftKey)) { e.preventDefault(); $("#b-rehacer").click(); }
  else if (k === "s" && e.shiftKey) { e.preventDefault(); $("#b-guardar-como").click(); }
  else if (k === "s") { e.preventDefault(); $("#b-guardar").click(); }
  else if (k === "o") { e.preventDefault(); $("#b-abrir").click(); }
  else if (k === "n") { e.preventDefault(); Marco.nuevoDoc(); }
  // Ctrl+P es imprimir en papel en todo el mundo; el PDF se queda en el
  // comando IMPRIMIR y en su botón.
  else if (k === "p") { e.preventDefault(); Comandos.correr("IMPRIMIRFISICO"); }
  else if (k === "g" && e.shiftKey) { e.preventDefault(); Comandos.correr("DESAGRUPAR"); }
  else if (k === "g") { e.preventDefault(); Comandos.correr("GRUPO"); }
  else if (k === "w") {
    e.preventDefault();
    // Sin escritorio todavía no hay nada que cerrar; sin la guarda, esto
    // revienta al apretarlo antes de que cargue el estado.
    if (estado.escritorio) Marco.cerrarDoc(estado.escritorio.activo);
  }
  else if (k === "tab") { e.preventDefault(); }
});

/* Ctrl+Tab pasa a la siguiente pestaña, como en cualquier programa con
 * pestañas. Va aparte porque `e.key` de Tab no llega en minúsculas al bloque
 * de arriba en todos los teclados. */
window.addEventListener("keydown", (e) => {
  if (!mandoPulsado(e) || e.key !== "Tab") return;
  const esc = estado.escritorio;
  if (!esc || esc.documentos.length < 2) return;
  e.preventDefault();
  const n = esc.documentos.length;
  const paso = e.shiftKey ? -1 : 1;
  Marco.activarDoc((esc.activo + paso + n) % n);
});

/* --- Autoguardado  ·  feature 9 ---------------------------------------- */
setInterval(async () => {
  if (!estado.resumen || !estado.resumen.sucio) return;
  try { await post("/api/autoguardar"); } catch (_) {}
}, 120000);

/* Sólo hay algo que recuperar si la vez pasada el programa **no** se cerró por
 * la X (se cayó, lo mataron, se fue la luz): el motor lo sabe por la marca de
 * sesión (core/proyecto.py). Si se cerró bien, ya no hay autoguardados. Y se
 * ofrece **una vez por dibujo**: decir que no tira todas las copias de ése. */
async function ofrecerRecuperacion() {
  try {
    for (let vuelta = 0; vuelta < 5; vuelta++) {
      const { copias } = await api("/api/recuperables");
      if (!copias.length) return;
      const c = copias[0];
      const nombre = c.origen ? c.origen.split(/[\\/]/).pop() : "un dibujo nuevo";
      if (confirm(`La vez pasada shape101 no se cerró bien y quedó trabajo sin guardar de ${nombre} (${c.cuando}).\n\n¿Recuperarlo?`)) {
        const pestana = !(window.Marco && Marco.enBlanco());
        aplicar(await post("/api/recuperar", { ruta: c.ruta, pestana }));
        estado.modo = "modelo";
        estado.sel.clear();
        await recargarTrazos();
        await Papel.pintarPestanas();
        encuadrar(false);
        avisar("Trabajo recuperado. Guárdalo con Ctrl+S para conservarlo.", false, 12000);
      } else {
        // Decir que no tira esa copia y sus hermanas: no se vuelve a ofrecer.
        await post("/api/descartar_recuperacion", { ruta: c.ruta });
      }
    }
  } catch (_) {}
}

/* --- Cierre (con Electron) --------------------------------------------- */
if (enElectron()) {
  // La página no cancela el cierre: contesta si hay cambios y el proceso
  // principal decide. Al revés, Electron cancela en silencio y el programa se
  // queda abierto sin ventana ni aviso.
  // Se cuentan **todos** los dibujos con cambios, no sólo el de enfrente: con
  // tres pestañas abiertas, cerrar por la X debe avisar de las tres.
  const sucios = () => {
    const docs = (estado.escritorio && estado.escritorio.documentos) || [];
    const n = docs.filter((d) => d.sucio).length;
    return docs.length ? n : ((estado.resumen && estado.resumen.sucio) ? 1 : 0);
  };
  window.cuantosSucios = sucios;      // lo usa el actualizador antes de cerrar
  window.t101.alPreguntarCierre(() => {
    window.t101.cerrar(sucios());
  });
  window.t101.alGuardarYSalir(async () => {
    // Guardar cada dibujo con cambios, activándolo por turno. Si el usuario
    // cancela el cuadro de «guardar como» de alguno, se queda en el programa:
    // salir con algo sin guardar después de haber dicho «guardar» es traición.
    const docs = (estado.escritorio && estado.escritorio.documentos) || [];
    const pendientes = docs.filter((d) => d.sucio).map((d) => d.indice);
    if (!pendientes.length) pendientes.push(null);
    for (const i of pendientes) {
      if (i !== null && window.Marco) await Marco.activarDoc(i);
      const ok = await Archivo.guardar(false);
      if (ok === false) return;
    }
    window.t101.cerrar(0);
  });
  window.t101.alAbrirArchivo(async (ruta) => {
    try { await abrirRuta(ruta); } catch (e) { avisar(e.message, true); }
  });
}

/* --- Arranque ---------------------------------------------------------- */
window.addEventListener("resize", ajustarLienzo);

/* **La interfaz no se agranda con Ctrl+rueda ni con Ctrl+más.** Es el zoom de
 * página del navegador, y en un CAD Ctrl está apretado la mitad del tiempo
 * (sumar a la selección): un giro de rueda con Ctrl sobre el panel dejaba
 * toda la ventana al 125 % y el pie y la consola se salían por abajo, hasta
 * que uno adivinaba Ctrl+0. El zoom de la app es el del dibujo, y ése ya lo
 * atiende el lienzo. */
window.addEventListener("wheel", (e) => {
  if (e.ctrlKey || e.metaKey) e.preventDefault();
}, { passive: false });
window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && ["=", "+", "-", "_", "0"].includes(e.key) &&
      !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    e.preventDefault();
  }
});
window.addEventListener("beforeunload", (e) => {
  if (estado.resumen && estado.resumen.sucio) { e.preventDefault(); e.returnValue = ""; }
});

/* La versión, en el pie. Antes no se veía en ningún lado y ocho instaladores
 * distintos se llamaron todos igual; ahora se puede decir por teléfono qué
 * build tiene uno delante. */
async function cargarVersion() {
  try {
    const r = await fetch("/api/version").then((x) => x.json());
    estado.version = r;
    $("#f-version").textContent = "v" + r.version;
    $("#f-version").title = `shape101 ${r.version} · ${r.fecha}\nEscribe VERSION para ver qué trae.`;
    // La portada puede haberse pintado antes de que llegara esto.
    const iv = $("#iVersion");
    if (iv) iv.textContent = `versión ${r.version}`;
  } catch (e) { /* el pie sin versión no impide dibujar */ }
}

(async function inicio() {
  const prefs = await cargarPrefs();
  Idioma.sincronizar(prefs);        // si el motor dice otro idioma, recarga
  if (window.t101 && window.t101.idioma) window.t101.idioma(Idioma.actual);
  cargarVersion();
  document.documentElement.dataset.tema = prefs.tema || "claro";
  logoDelTema();
  pintarInterruptores();
  conectarInterruptores();
  conectarHerramientas();
  Barra.conectar();
  Barra.desdePrefs(prefs);
  Comandos.conectar();
  Comandos.aplicarAtajos(prefs.atajos);
  PanelCotas.conectar();
  ajustarLienzo();
  await refrescar(true);
  await Papel.pintarPestanas();
  Comandos.eco("shape101 listo. Teclea AYUDA para la lista de comandos.");
  await ofrecerRecuperacion();
  if (enElectron() && window.t101.archivoInicial) {
    const ruta = await window.t101.archivoInicial();
    if (ruta) await abrirRuta(ruta);
  }
})();

/* ===================================================================== */
/* Propiedades del objeto  ·  feature 43                                 */
/* ===================================================================== */
/* Un panel que enseña lo que hay seleccionado y deja cambiarlo a mano. Es el
 * camino corto para lo que ninguna herramienta cubre: mover un círculo a un
 * centro exacto tecleado, cambiarle la altura a un texto, pasar tres entidades
 * de capa sin comando. */

const CAMPOS_POR_TIPO = {
  linea: [["p1", "Inicio", "punto"], ["p2", "Fin", "punto"]],
  circulo: [["centro", "Centro", "punto"], ["radio", "Radio", "numero"]],
  arco: [["centro", "Centro", "punto"], ["radio", "Radio", "numero"],
         ["ang_ini", "Ángulo inicial", "numero"], ["ang_fin", "Ángulo final", "numero"]],
  polilinea: [["cerrada", "Cerrada", "si_no"]],
  punto: [["p", "Ubicación", "punto"]],
  // Mike (9-sep-2026): «en las propiedades de texto, agregar si está
  // justificado a la izquierda, al centro o a la derecha del origen».
  texto: [["texto", "Texto", "texto"], ["altura", "Altura", "numero"],
          ["rotacion", "Rotación", "numero"],
          ["alineacion", "Justificado", "lista", [["IZQ", "Izquierda del origen"], ["CENTRO", "Centrado en el origen"], ["DER", "Derecha del origen"]]],
          ["p", "Inserción", "punto"]],
  textom: [["texto", "Texto", "texto"], ["altura", "Altura", "numero"],
           ["ancho", "Ancho", "numero"], ["p", "Inserción", "punto"]],
  elipse: [["centro", "Centro", "punto"], ["razon", "Razón ejes", "numero"]],
  insercion: [["bloque", "Bloque", "texto"], ["p", "Inserción", "punto"],
              ["rotacion", "Rotación", "numero"]],
  rayado: [["patron", "Patrón", "texto"], ["escala", "Escala", "numero"]],
  // El tamaño de la cota es un campo especial (ver `filaTamanoCota`): se
  // enseña la altura del texto en el dibujo y la opción de encadenar al base.
  cota: [["texto", "Texto", "texto"], ["_tamano", "Tamaño", "tamano_cota"], ["estilo", "Estilo", "texto"]],
};

async function pintarPropsObjeto() {
  const caja = $("#props-obj");
  const campos = $("#obj-campos");
  const n = estado.sel.size;
  if (!n) { caja.hidden = true; return; }
  caja.hidden = false;
  campos.innerHTML = "";

  const ids = [...estado.sel];
  // El encabezado sale **ya**, con lo que se sabe sin preguntar: la cuenta.
  // Lo demás llega en un instante, pero ese instante no se ve como espera.
  const previo = document.createElement("div");
  previo.className = "tipo";
  previo.textContent = n === 1 ? "…" : `${n} entidades`;
  campos.appendChild(previo);

  // Una petición para todas, no una por entidad: con 5 000 seleccionadas eran
  // 5 000 peticiones y 1.7 s de interfaz congelada. Ver `/api/entidades/varias`.
  let ents;
  const mia = (pintarPropsObjeto._vez = (pintarPropsObjeto._vez || 0) + 1);
  // Al panel le bastan unas cuantas para saber qué tienen en común.
  try { ents = (await post("/api/entidades/varias", { ids: ids.slice(0, 300) })).entidades; }
  catch (_) { return; }
  // Si mientras tanto cambió la selección, esta respuesta ya no es de nadie.
  if (mia !== pintarPropsObjeto._vez) return;
  if (!ents.length) return;
  campos.innerHTML = "";
  armarCamposObjeto(campos, ids, ents, { enVivo: false });
}

/** Arma los campos de propiedades de `ents` (ya traídas) dentro de `campos`.
 *
 *  Lo comparten el panel de la derecha y el cuadro flotante del clic derecho
 *  (0.20.0). `enVivo`: los cambios se mandan al teclear, con un pequeño
 *  retraso, en vez de al salir del campo — es lo que hace que el flotante
 *  refleje en tiempo real. */
function armarCamposObjeto(campos, ids, ents, { enVivo = false } = {}) {
  const n = ids.length;
  const tipos = [...new Set(ents.map((e) => e.tipo))];
  const cabeza = document.createElement("div");
  cabeza.className = "tipo";
  cabeza.textContent = n === 1 ? nombreTipo(ents[0].tipo)
    : `${n} entidades${tipos.length === 1 ? " · " + nombreTipo(tipos[0]) : ""}`;
  campos.appendChild(cabeza);

  // Comunes: se pueden cambiar aunque haya varias seleccionadas.
  const comunes = (clave) => {
    const v = ents[0][clave];
    return ents.every((e) => JSON.stringify(e[clave]) === JSON.stringify(v)) ? v : null;
  };
  const fila = (etiqueta, control, alCambiar) => agregarFila(campos, etiqueta, control, alCambiar, enVivo);

  fila("Capa", selectorCapa(comunes("capa")), async (val) =>
    cambiarObjetos(ids, { capa: val }));
  fila("Color", selectorColor(comunes("color")), async (val) =>
    cambiarObjetos(ids, { color: val || null }));
  fila("Grosor", selectorGrosor(comunes("grosor")), async (val) =>
    cambiarObjetos(ids, { grosor: val === "" ? null : parseInt(val, 10) }));
  // Mike (7-sep-2026): «las propiedades de línea se deben poder cambiar por
  // cada entidad de línea, no todas». El tipo de línea (y su escala) van por
  // entidad; «Por capa» es lo de siempre.
  fila("Tipo de línea", selectorTipoLinea(comunes("tipo_linea")), async (val) =>
    cambiarObjetos(ids, { tipo_linea: val || null }));
  fila("Escala del tipo", campoTexto(mm(comunes("escala_tl") ?? 1)), async (val) => {
    const x = parseFloat(String(val).replace(",", "."));
    if (!(x > 0)) return avisar("La escala del tipo de línea tiene que ser mayor que cero.", true);
    cambiarObjetos(ids, { escala_tl: x });
  });

  if (n !== 1 || tipos.length !== 1) {
    // Con varias del mismo tipo, lo que tiene sentido compartir: el tamaño
    // de las cotas (Mike quiere cambiar varias de un jalón) y la
    // justificación de textos.
    if (tipos.length === 1 && tipos[0] === "cota") filaTamanoCota(campos, ids, ents, enVivo);
    if (tipos.length === 1 && tipos[0] === "texto") {
      fila("Justificado", selectorLista(comunes("alineacion") || "", CAMPOS_POR_TIPO.texto.find((c) => c[0] === "alineacion")[3], true),
           async (val) => { if (val) cambiarObjetos(ids, { alineacion: val }); });
    }
    const nota = document.createElement("div");
    nota.className = "varias";
    nota.textContent = "La geometría se edita de una en una.";
    campos.appendChild(nota);
    return;
  }

  const ent = ents[0];
  for (const [clave, etiqueta, clase, opciones] of CAMPOS_POR_TIPO[ent.tipo] || []) {
    const valor = ent[clave];
    if (clase === "tamano_cota") { filaTamanoCota(campos, ids, ents, enVivo); continue; }
    if (clase === "punto") {
      fila(etiqueta, campoTexto(`${mm(valor[0])}, ${mm(valor[1])}`), async (val) => {
        const p = Entrada.parsearCoordenadas(val, null);
        if (!p) return avisar("Escribe las coordenadas como 100,50", true);
        cambiarObjetos(ids, { [clave]: p });
      });
    } else if (clase === "numero") {
      fila(etiqueta, campoTexto(mm(valor)), async (val) => {
        const x = parseFloat(String(val).replace(",", "."));
        if (!isFinite(x)) return avisar("Eso no es un número.", true);
        cambiarObjetos(ids, { [clave]: x });
      });
    } else if (clase === "si_no") {
      fila(etiqueta, selectorLista(valor ? "si" : "no", [["si", "sí"], ["no", "no"]]),
           async (val) => cambiarObjetos(ids, { [clave]: val === "si" }));
    } else if (clase === "lista") {
      fila(etiqueta, selectorLista(valor || opciones[0][0], opciones), async (val) => cambiarObjetos(ids, { [clave]: val }));
    } else {
      fila(etiqueta, campoTexto(String(valor ?? "")), async (val) =>
        cambiarObjetos(ids, { [clave]: val }));
    }
  }
}

/* El tamaño de una cota (o de varias): la altura del texto **en el dibujo**,
 * y si va encadenada al tamaño base del documento. Mike (9-sep-2026):
 * «tras cambiar el tamaño de una cota, opción de encadenar al tamaño base:
 * queda como proporción y si el base cambia, esa cota cambia
 * proporcionalmente con todo el documento».
 *
 * Por dentro: `factor_tamano` × base (encadenada) o `factor_tamano` a secas
 * sobre el estilo a 1:1 (suelta). Ver core/cotas.py `escala_efectiva`. */
function filaTamanoCota(campos, ids, ents, enVivo) {
  const est = (estado.resumen && estado.resumen.estilo_cota) || {};
  const altura = parseFloat(est.altura_texto) || 2.5;
  const baseDoc = parseFloat(est.factor_escala) || 1;
  const enHoja = estado.modo === "papel";
  const e0 = ents[0];
  const ft = parseFloat(e0.factor_tamano) || 1;
  const encadenada = e0.encadenada !== false;
  const escalaDe = (ent) => {
    const f = parseFloat(ent.factor_tamano) || 1;
    return (ent.encadenada !== false) ? (enHoja ? 1 : baseDoc) * f : f;
  };
  const iguales = ents.every((e) => Math.abs(escalaDe(e) - escalaDe(e0)) < 1e-9);
  const campo = campoTexto(iguales ? mm(altura * escalaDe(e0)) : "");
  campo.placeholder = iguales ? "" : "(varias)";
  const casilla = document.createElement("input");
  casilla.type = "checkbox";
  casilla.checked = encadenada;
  casilla.title = "Encadenada al tamaño base del documento: si el base cambia, esta cota cambia en proporción.";
  const aplicar_ = async (texto, cadena) => {
    const x = parseFloat(String(texto).replace(",", "."));
    if (!(x > 0)) return avisar("El tamaño tiene que ser mayor que cero.", true);
    const escala = x / altura;                       // sobre el estilo a 1:1
    const cambios = cadena
      ? { factor_tamano: escala / (enHoja ? 1 : baseDoc), encadenada: true }
      : { factor_tamano: escala, encadenada: false };
    await cambiarObjetos(ids, cambios);
  };
  agregarFila(campos, `Tamaño (${U()})`, campo, (val) => aplicar_(val, casilla.checked), enVivo);
  const cont = document.createElement("div");
  cont.className = "check";
  const et = document.createElement("span");
  et.textContent = Tr("encadenar al base");
  et.style.fontSize = "11.5px";
  cont.append(casilla, et);
  agregarFila(campos, "", cont, () => {}, false);
  casilla.onchange = () => { if (campo.value) aplicar_(campo.value, casilla.checked); };
}

function selectorLista(valor, opciones, conVarias = false) {
  const s = document.createElement("select");
  if (conVarias) {
    const o = document.createElement("option"); o.value = ""; o.textContent = "(varias)";
    s.appendChild(o);
  }
  for (const [v, t] of opciones) {
    const o = document.createElement("option"); o.value = v; o.textContent = Tr(t);
    s.appendChild(o);
  }
  s.value = valor;
  return s;
}

/* --- Propiedades junto al ratón  ·  0.20.0 ------------------------------
 *
 * Mike (9-sep-2026): «cuando haga clic derecho sobre una entidad, desplegar
 * un menú de propiedades editable ahí mismo. Hasta que no haga clic fuera de
 * ese menú, no se cierra, para poder editar con calma. Reflejar en tiempo
 * real los cambios mientras se editan».
 *
 * Es el mismo armado de campos del panel de la derecha, en un cuadro flotante
 * y con los cambios **al teclear** (`enVivo`). Lo abre el clic derecho corto
 * sobre una entidad (ver ui/radial.js); si la entidad estaba dentro de una
 * selección, se edita toda la selección. */
const PropsFlotante = (() => {
  let caja = null;
  async function abrir(id, x, y) {
    cerrar();
    let ids = [id];
    if (estado.sel.has(id) && estado.sel.size > 1) ids = [...estado.sel];
    else { estado.sel.clear(); estado.sel.add(id); Seleccion.refrescar(); }
    let ents;
    try { ents = (await post("/api/entidades/varias", { ids: ids.slice(0, 300) })).entidades; }
    catch (_) { return false; }
    if (!ents.length) return false;
    caja = document.createElement("div");
    caja.className = "props-flot";
    const cab = document.createElement("div");
    cab.className = "cab";
    const b = document.createElement("b");
    b.textContent = ids.length === 1 ? nombreTipo(ents[0].tipo) : `${ids.length} ${Tr("entidades")}`;
    const cerrarB = document.createElement("button");
    cerrarB.className = "cerrar"; cerrarB.textContent = "×"; cerrarB.title = Tr("Cerrar (Esc)");
    cerrarB.onclick = () => cerrar();
    cab.append(b, cerrarB);
    caja.appendChild(cab);
    const campos = document.createElement("div");
    caja.appendChild(campos);
    armarCamposObjeto(campos, ids, ents, { enVivo: true });
    const pie = document.createElement("div");
    pie.className = "pie";
    pie.textContent = Tr("Los cambios se ven al momento · clic fuera o Esc cierra");
    caja.appendChild(pie);
    caja.style.visibility = "hidden";
    document.body.appendChild(caja);
    const r = caja.getBoundingClientRect();
    caja.style.left = Math.max(8, Math.min(x + 10, window.innerWidth - r.width - 8)) + "px";
    caja.style.top = Math.max(8, Math.min(y + 10, window.innerHeight - r.height - 8)) + "px";
    caja.style.visibility = "";
    setTimeout(() => {
      document.addEventListener("mousedown", fuera, true);
      document.addEventListener("keydown", tecla, true);
    }, 0);
    return true;
  }
  function fuera(e) { if (caja && !caja.contains(e.target)) cerrar(); }
  function tecla(e) {
    if (!caja) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cerrar(); return; }
    // Enter en un campo aplica y **no** cierra: el cuadro se queda hasta el
    // clic fuera (Mike). Y el resto del teclado es del cuadro, no de la línea
    // de comandos.
    if (caja.contains(e.target) && e.key === "Enter") {
      e.preventDefault();
      if (e.target.tagName === "INPUT") { e.target.blur(); e.target.focus(); }
    }
  }
  function cerrar() {
    if (!caja) return;
    caja.remove();
    caja = null;
    document.removeEventListener("mousedown", fuera, true);
    document.removeEventListener("keydown", tecla, true);
  }
  return { abrir, cerrar, get abierto() { return !!caja; } };
})();
window.PropsFlotante = PropsFlotante;

function nombreTipo(t) {
  return ({ linea: "Línea", polilinea: "Polilínea", circulo: "Círculo", arco: "Arco",
            elipse: "Elipse", spline: "Spline", punto: "Punto", solido: "Sólido",
            texto: "Texto", textom: "Texto de párrafo", insercion: "Bloque insertado",
            rayado: "Rayado", cota: "Cota", cruda: "Entidad del archivo" })[t] || t;
}

function campoTexto(valor) {
  const i = document.createElement("input");
  i.type = "text"; i.value = valor;
  return i;
}

function selectorCapa(valor) {
  const s = document.createElement("select");
  for (const c of estado.resumen.capas) {
    const o = document.createElement("option");
    o.value = c.nombre; o.textContent = c.nombre;
    s.appendChild(o);
  }
  if (valor === null) {
    const o = document.createElement("option");
    o.value = ""; o.textContent = "(varias)"; o.selected = true;
    s.insertBefore(o, s.firstChild);
  } else s.value = valor;
  return s;
}

function selectorColor(valor) {
  const s = document.createElement("select");
  const opciones = [["", "Por capa"], ...estado.resumen.capas.map((c) => [c.color, c.color])];
  const vistos = new Set();
  for (const [v, t] of opciones) {
    if (vistos.has(v)) continue;
    vistos.add(v);
    const o = document.createElement("option");
    o.value = v; o.textContent = t;
    s.appendChild(o);
  }
  s.value = valor || "";
  return s;
}

function selectorTipoLinea(valor) {
  const s = document.createElement("select");
  const o0 = document.createElement("option");
  o0.value = ""; o0.textContent = "Por capa";
  s.appendChild(o0);
  const tipos = { ...(estado.resumen.tipos_linea || {}) };
  if (valor && !(valor in tipos)) tipos[valor] = valor + " (del archivo)";
  for (const [k, desc] of Object.entries(tipos)) {
    const o = document.createElement("option");
    o.value = k; o.textContent = k.toLowerCase() + (desc && desc !== k ? " · " + desc : "");
    s.appendChild(o);
  }
  s.value = valor || "";
  return s;
}

function selectorGrosor(valor) {
  const s = document.createElement("select");
  const o0 = document.createElement("option");
  o0.value = ""; o0.textContent = "Por capa";
  s.appendChild(o0);
  for (const v of estado.resumen.grosores) {
    const o = document.createElement("option");
    o.value = v; o.textContent = (v / 100).toFixed(2) + " mm";
    s.appendChild(o);
  }
  s.value = valor === null || valor === undefined ? "" : String(valor);
  return s;
}

function agregarFila(donde, etiqueta, control, alCambiar, enVivo = false) {
  const fila = document.createElement("div");
  fila.className = "fila";
  const lab = document.createElement("label");
  lab.textContent = Tr(etiqueta);
  let ultimo = control.value;
  const mandar = (v) => { if (v === ultimo) return; ultimo = v; alCambiar(v); };
  control.onchange = (e) => mandar(e.target.value);
  if (enVivo && control.tagName === "INPUT" && control.type === "text") {
    // En tiempo real: al teclear, con un respiro de 250 ms para no mandar una
    // operación por letra. Cada envío es un paso de deshacer; se aceptan.
    let t = null;
    control.oninput = (e) => { clearTimeout(t); const v = e.target.value; t = setTimeout(() => mandar(v), 250); };
  }
  fila.append(lab, control);
  donde.appendChild(fila);
}

async function cambiarObjetos(ids, cambios) {
  const mapa = {};
  for (const id of ids) mapa[id] = cambios;
  try {
    const r = await post("/api/operacion", { accion: "Propiedades", cambios: mapa });
    aplicar(r);
    if (!aplicarParche(r)) await recargarTrazos();
  } catch (e) { avisar(e.message, true); }
}
