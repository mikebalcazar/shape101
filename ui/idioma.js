/* Idioma de la interfaz  ·  0.19.0
 *
 * Mike, 6-sep-2026: *«quiero que el idioma por default sea inglés, y si alguien
 * lo quiere en español, que pueda cambiarlo en configuración del software»*.
 *
 * Cómo está hecho, y por qué así:
 *
 *   · El código sigue **en español**: es como se escribió, como lo lee Mike y
 *     como están las 33 suites de pruebas. No se reescribieron 600 cadenas.
 *   · Hay un diccionario español → inglés (ui/idioma-en.js). `T(texto)` busca
 *     la traducción; si no la hay, devuelve el texto tal cual (nunca rompe).
 *   · Las cadenas con números dentro («Rectángulo de 800 × 720 mm.») van en
 *     el diccionario como plantillas con {0}, {1}… y se casan con una
 *     expresión regular.
 *   · **La interfaz es el DOM.** En vez de tocar cada sitio que escribe un
 *     texto, un MutationObserver traduce lo que aparece: los botones del
 *     HTML, los cuadros que arma Dialogo, las líneas de la consola, los
 *     tooltips. Sólo se traduce lo que está en el diccionario, así que el
 *     contenido del usuario (capas, textos, nombres de archivo) no se toca.
 *   · Los comandos se aceptan en los dos idiomas siempre (LINE y LINEA), como
 *     hace AutoCAD con el guion bajo. En inglés la ayuda enseña los nombres
 *     en inglés.
 *
 * El idioma vive en las preferencias (`idioma`); para no parpadear en
 * español mientras llegan, se guarda también en localStorage.
 */

const Idioma = (() => {
  let actual = "en";
  // Se pregunta al motor **antes de pintar nada**, en una llamada síncrona:
  // es local y tarda un milisegundo, y así la ventana nace ya en su idioma en
  // vez de arrancar en inglés y recargarse en español. Si el motor no
  // contesta (pruebas sin motor, arranque a medias), vale lo último guardado.
  try {
    const x = new XMLHttpRequest();
    x.open("GET", "/api/preferencias", false);
    x.send(null);
    if (x.status === 200) {
      const p = JSON.parse(x.responseText).preferencias || {};
      actual = p.idioma === "es" ? "es" : "en";
      try { localStorage.setItem("idioma", actual); } catch (e) { /* nada */ }
    } else throw new Error("sin motor");
  } catch (e) {
    try { actual = localStorage.getItem("idioma") || "en"; } catch (e2) { /* sin storage */ }
  }
  if (actual !== "es") actual = "en";

  const dic = (typeof IDIOMA_EN !== "undefined") ? IDIOMA_EN : {};
  const plantillas = [];
  const cache = new Map();
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  for (const [es, en] of Object.entries(dic)) {
    if (!/\{\d+\}/.test(es)) continue;
    const orden = [...es.matchAll(/\{(\d+)\}/g)].map((m) => +m[1]);
    const partes = es.split(/\{\d+\}/);
    plantillas.push({ re: new RegExp("^" + partes.map(esc).join("([\\s\\S]*?)") + "$"), en, orden });
  }

  function buscar(nucleo) {
    let r = dic[nucleo];
    if (r !== undefined) return r;
    if (cache.has(nucleo)) return cache.get(nucleo);
    r = null;
    for (const p of plantillas) {
      const m = p.re.exec(nucleo);
      if (!m) continue;
      r = p.en.replace(/\{(\d+)\}/g, (_, i) => {
        const k = p.orden.indexOf(+i);
        return k >= 0 ? T(m[k + 1]) : "";
      });
      break;
    }
    if (cache.size > 2000) cache.clear();
    cache.set(nucleo, r);
    return r;
  }

  function T(texto) {
    if (actual === "es" || texto == null) return texto;
    const s = String(texto);
    if (!s.trim()) return texto;
    const ini = s.match(/^\s*/)[0], fin = s.match(/\s*$/)[0];
    let nucleo = s.trim();
    let r = buscar(nucleo);
    if (r != null) return ini + r + fin;
    // «› LINEA», «Al punto:», «   · algo»: se separa lo que envuelve al texto
    // (viñetas, dos puntos) y se traduce el centro.
    let pre = "", post = "";
    const mp = nucleo.match(/^([›·•\-–—\s]+)/);
    if (mp) { pre = mp[1]; nucleo = nucleo.slice(pre.length); }
    const ms = nucleo.match(/([:：]\s*)$/);
    if (ms) { post = ms[1]; nucleo = nucleo.slice(0, -post.length); }
    if (!pre && !post) return texto;
    r = buscar(nucleo);
    return r == null ? texto : ini + pre + r + post + fin;
  }

  /* --- El DOM ------------------------------------------------------------ */
  const ATRIBUTOS = ["title", "placeholder", "alt", "aria-label", "data-pista"];
  const SALTAR = new Set(["SCRIPT", "STYLE", "TEXTAREA", "CODE", "PRE"]);

  function traducirTexto(nodo) {
    const v = nodo.nodeValue;
    if (!v || !v.trim()) return;
    const padre = nodo.parentNode;
    if (padre && SALTAR.has(padre.nodeName)) return;
    const t = T(v);
    if (t !== v) nodo.nodeValue = t;
  }

  function traducirElemento(el) {
    for (const a of ATRIBUTOS) {
      if (!el.hasAttribute(a)) continue;
      const v = el.getAttribute(a), t = T(v);
      if (t !== v) el.setAttribute(a, t);
    }
  }

  function traducirArbol(raiz) {
    if (actual === "es" || !raiz) return;
    if (raiz.nodeType === 3) { traducirTexto(raiz); return; }
    if (raiz.nodeType !== 1 && raiz.nodeType !== 11) return;
    if (raiz.nodeType === 1) {
      if (SALTAR.has(raiz.nodeName)) return;
      traducirElemento(raiz);
    }
    const it = document.createNodeIterator(raiz, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let n;
    while ((n = it.nextNode())) {
      if (n === raiz) continue;
      if (n.nodeType === 3) traducirTexto(n);
      else { if (SALTAR.has(n.nodeName)) continue; traducirElemento(n); }
    }
  }

  let observador = null;
  function vigilar() {
    if (actual === "es" || observador) return;
    observador = new MutationObserver((cambios) => {
      for (const c of cambios) {
        if (c.type === "childList") c.addedNodes.forEach(traducirArbol);
        else if (c.type === "characterData") traducirTexto(c.target);
        else if (c.type === "attributes" && c.target.nodeType === 1) traducirElemento(c.target);
      }
    });
    observador.observe(document.documentElement, {
      childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ATRIBUTOS,
    });
  }

  function arrancar() {
    if (actual === "es") return;
    traducirArbol(document.documentElement);
    document.title = T(document.title);
    vigilar();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", arrancar);
  else arrancar();

  /* Cambiar de idioma: se guarda y se recarga la ventana. Traducir hacia
   * atrás lo ya traducido sería llevar una segunda copia de cada texto; una
   * recarga de un segundo es más simple y no deja nada a medias. */
  async function cambiar(nuevo) {
    nuevo = nuevo === "es" ? "es" : "en";
    try { localStorage.setItem("idioma", nuevo); } catch (e) { /* nada */ }
    if (typeof guardarPrefs === "function") await guardarPrefs({ idioma: nuevo });
    if (nuevo !== actual) location.reload();
  }

  /* Al llegar las preferencias del motor, la que manda es ésa. */
  function sincronizar(prefs) {
    const p = (prefs && prefs.idioma === "es") ? "es" : "en";
    try { localStorage.setItem("idioma", p); } catch (e) { /* nada */ }
    if (p !== actual) location.reload();
  }

  /* --- Comandos en inglés ------------------------------------------------ */
  const COMANDOS = {
    LINE: "LINEA", PLINE: "POLILINEA", POLYLINE: "POLILINEA", RECTANGLE: "RECTANGULO", RECTANG: "RECTANGULO",
    CIRCLE: "CIRCULO", ARC: "ARCO", ELLIPSE: "ELIPSE", POINT: "PUNTO", HATCH: "RAYADO",
    TEXT: "TEXTO", MTEXT: "TEXTO", DIM: "COTA", DIMLINEAR: "COTA", DIMALIGNED: "COTAALINEADA",
    ADDVIEWPORT: "VENTANAHOJA", VIEWPORTSHEET: "VENTANAHOJA", EDITVIEWPORT: "EDITARVENTANA", VIEWPORTS: "EDITARVENTANA",
    NEWVIEWPORT: "VENTANANUEVA", DELETEVIEWPORT: "BORRARVENTANA",
    DIMANGULAR: "COTAANGULAR", DIMBASELINE: "COTABASE", DIMCONTINUE: "COTACONTINUA",
    DIMDIAMETER: "COTADIAMETRO", DIMRADIUS: "COTARADIO", DIMSTYLE: "ESTILOCOTA", LEADER: "DIRECTRIZ",
    MOVE: "MOVER", COPY: "COPIAR", ROTATE: "ROTAR", SCALE: "ESCALAR", MIRROR: "ESPEJO",
    TRIM: "RECORTAR", EXTEND: "EXTENDER", FILLET: "EMPALME", CHAMFER: "CHAFLAN", ARRAY: "ARREGLO",
    STRETCH: "ESTIRAR", ERASE: "BORRAR", DELETE: "BORRAR", MATCHPROP: "IGUALAR",
    BLOCK: "BLOQUE", INSERT: "INSERTAR", WBLOCK: "GUARDARBLOQUE", LIBRARY: "BIBLIOTECA",
    UNDO: "DESHACER", REDO: "REHACER", MEASURE: "MEDIR", DISTANCE: "MEDIR", ZOOMEXTENTS: "ENCUADRAR",
    EXTENTS: "ENCUADRAR", LAYOUT: "PLANO", SHEET: "PLANO", MODEL: "MODELO", TITLEBLOCK: "ROTULO",
    PRINT: "IMPRIMIRFISICO", PLOTTER: "IMPRIMIRFISICO", VPSCALE: "ESCALAVENTANA", VPFIT: "ENCUADRARVENTANA",
    DELETESHEET: "BORRARPLANO", EDITSHEET: "EDITARHOJA", IMAGE: "IMAGEN", IMAGEREF: "IMAGENREF",
    PDFBACKGROUND: "PDFFONDO", BACKGROUND: "PDFFONDO", GRID: "REJILLA", OSNAP: "REFERENCIAS",
    OSNAPSET: "MODOSREF", DYN: "DINAMICA", HELP: "AYUDA", COMMANDS: "AYUDA", ABOUT: "VERSION",
    THEME: "TEMA", TOOLBAR: "BARRA", SHORTCUT: "ATAJO", QUANTITIES: "CANTIDADES", COUNT: "CANTIDADES",
    COMPARE: "COMPARAR", REGENALL: "REGENERAR", PERFORMANCE: "RENDIMIENTO", DRAFT: "BORRADOR",
    SETTINGS: "CONFIGURACION", CONFIG: "CONFIGURACION", OPTIONS: "CONFIGURACION", LANGUAGE: "IDIOMA",
    UPDATE: "ACTUALIZAR", UPDATES: "ACTUALIZAR", NOTICES: "AVISOS", NEWS: "AVISOS", LICENSES: "LICENCIAS", CREDITS: "LICENCIAS",
    UNITS: "UNIDADES", CENTER: "CENTRAR", CENTERVIEWPORT: "CENTRAR", GUIDE: "GUIA", TOOLS: "GUIA",
    PREVIEW: "VISTAPREVIA", PRINTPREVIEW: "VISTAPREVIA",
  };
  const INVERSO = {};
  for (const [en, es] of Object.entries(COMANDOS)) if (!INVERSO[es]) INVERSO[es] = en;

  /** El nombre en español del comando que se tecleó (en cualquier idioma). */
  function comando(nombre) {
    const n = String(nombre || "").toUpperCase();
    return COMANDOS[n] || n;
  }
  /** Cómo se enseña un comando en el idioma actual (para AYUDA y tooltips). */
  function nombreComando(es) {
    return actual === "en" ? (INVERSO[es] || es) : es;
  }

  return { T, traducirArbol, cambiar, sincronizar, comando, nombreComando, COMANDOS,
           get actual() { return actual; }, get ingles() { return actual === "en"; } };
})();

const Tr = Idioma.T;
