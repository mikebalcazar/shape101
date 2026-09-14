/* Lo que comparten todos los módulos de la interfaz: estado, atajos de DOM y
 * las llamadas a la API. Se carga primero.
 *
 * A partir de F1 la interfaz está partida en archivos por asunto —base, vista,
 * osnap, entrada, comandos, app— y se cargan en ese orden con etiquetas
 * <script> normales. Sin empaquetador: la app se sirve desde su propio backend
 * en 127.0.0.1 y no hay nada que empaquetar.
 */

const $ = (s) => document.querySelector(s);

/* --- El indicador de «trabajando» ---------------------------------------
 *
 * Mike: *«agrega algún indicador de que el programa está trabajando cuando
 * alguna operación tarda más de medio segundo. Para saber que no se trabó»*.
 *
 * Toda llamada al motor pasa por `api()`, así que aquí se cuenta cuántas hay
 * en vuelo. Si alguna lleva más de medio segundo, sale la barra; mientras
 * está fuera, se le pregunta al motor **qué** está haciendo (`/api/progreso`)
 * y se escribe ahí: «Convirtiendo el DWG (21 MB)…», «Importando el modelo…».
 * Con eso, un minuto de conversión se ve como un minuto de trabajo y no como
 * un programa colgado. Se quita en cuanto no queda nada en vuelo.
 */
const Ocupado = (() => {
  const UMBRAL_MS = 500;
  let enVuelo = 0, temporizador = null, sondeo = null, visible = false;

  const nombreDe = (ruta) => {
    if (ruta.startsWith("/api/abrir")) return "Abriendo el plano…";
    if (ruta.startsWith("/api/guardar")) return "Guardando…";
    if (ruta.startsWith("/api/imprimir") || ruta.startsWith("/api/imagen")) return "Imprimiendo…";
    if (ruta.startsWith("/api/exportar")) return "Exportando…";
    if (ruta.startsWith("/api/trazos") || ruta.startsWith("/api/espacio")) return "Trayendo el dibujo…";
    if (ruta.startsWith("/api/papel")) return "Armando la hoja…";
    return "Trabajando…";
  };

  function mostrar(texto) {
    const caja = document.getElementById("ocupado");
    if (!caja) return;
    caja.querySelector(".que").textContent = texto;
    caja.classList.add("si");
    visible = true;
    // Preguntar al motor qué hace, y actualizar la barra con eso.
    if (!sondeo) {
      sondeo = setInterval(async () => {
        try {
          const r = await fetch("/api/progreso");
          const d = await r.json();
          if (d && d.mensaje) {
            caja.querySelector(".que").textContent =
              d.mensaje + (d.segundos >= 2 ? `  ·  ${Math.round(d.segundos)} s` : "");
          }
        } catch (_) { /* si no contesta, se deja el texto que había */ }
      }, 500);
    }
  }

  function ocultar() {
    const caja = document.getElementById("ocupado");
    if (caja) caja.classList.remove("si");
    visible = false;
    if (sondeo) { clearInterval(sondeo); sondeo = null; }
  }

  function empieza(ruta) {
    enVuelo++;
    if (!temporizador && !visible) {
      temporizador = setTimeout(() => { temporizador = null; if (enVuelo) mostrar(nombreDe(ruta)); }, UMBRAL_MS);
    }
  }

  function termina() {
    enVuelo = Math.max(0, enVuelo - 1);
    if (enVuelo) return;
    if (temporizador) { clearTimeout(temporizador); temporizador = null; }
    if (visible) ocultar();
  }

  /** Para trabajo largo del propio navegador, no del motor. */
  async function mientras(texto, fn) {
    enVuelo++;
    const t = setTimeout(() => { if (enVuelo) mostrar(texto); }, UMBRAL_MS);
    try { return await fn(); }
    finally { clearTimeout(t); termina(); }
  }

  return { empieza, termina, mientras, get activo() { return visible; } };
})();

/* Llamadas lentas al motor, anotadas solas (13-sep-2026, objetivo 1,
 * fluidez, camino C). Medido en el plano de prueba de 21 700 entidades: pintar
 * un cuadro cuesta 40–60 ms, pero pedir `/api/trazos` entero cuesta 1–2 s y
 * una operación que no manda parche obliga a pedirlo. Cuando Mike dice «se
 * puso lentísimo», la pregunta es qué llamada fue: esto la deja anotada con
 * su ruta, cuánto tardó, cuánto pesó y si hubo recarga completa. PERF lo
 * imprime junto a los cuadros lentos. */
const DiagApi = { llamadas: [], umbral: 150 };
function _anotarLlamada(ruta, ms, bytes, recarga) {
  DiagApi.llamadas.push({ t: Date.now(), ruta: ruta.split("?")[0], ms, kb: Math.round(bytes / 1024), recarga });
  if (DiagApi.llamadas.length > 40) DiagApi.llamadas.shift();
}

const api = async (ruta, opciones) => {
  Ocupado.empieza(ruta);
  const tInicio = performance.now();
  try {
    const r = await fetch(ruta, opciones);
    let cuerpo = null, fallo = null;
    let bytes = 0;
    try {
      const texto = await r.text();
      bytes = texto.length;
      cuerpo = JSON.parse(texto);
    } catch (e) { fallo = e; cuerpo = {}; }
    const ms = performance.now() - tInicio;
    const recarga = ruta.startsWith("/api/trazos") || (cuerpo && "parche" in cuerpo && cuerpo.parche === null);
    if (ms >= DiagApi.umbral || recarga) _anotarLlamada(ruta, ms, bytes, recarga);
    if (!r.ok) throw new Error(cuerpo.detail || `Error ${r.status}`);
    // Una respuesta buena que no se pudo leer (demasiado grande para el
    // navegador, o rota) es un error, no un objeto vacío: con `{}` el
    // programa seguía con `estado.trazos` indefinido y fallaba más adelante
    // con «estado.trazos is not iterable», sin decir por qué.
    if (fallo) throw new Error(`No se pudo leer la respuesta de ${ruta.split("?")[0]}: ${fallo.message}`);
    return cuerpo;
  } finally {
    Ocupado.termina();
  }
};
const post = (ruta, datos) => api(ruta, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: datos === undefined ? undefined : JSON.stringify(datos),
});
const patch = (ruta, datos) => api(ruta, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(datos),
});

/* Un Set que sabe cuántas veces ha cambiado. La capa de selección se guarda
 * como imagen (ver Seleccion.pintarSeleccion) y necesita saber, sin recorrer
 * nada, si la selección es la misma de hace un cuadro. */
class SelSet extends Set {
  // La versión es única entre todos los SelSet que se creen: dos selecciones
  // distintas del mismo tamaño nunca comparten llave.
  constructor(it) { super(it); this.v = ++SelSet.contador; }
  add(x) { if (!this.has(x)) { this.v = ++SelSet.contador; } return super.add(x); }
  delete(x) { const r = super.delete(x); if (r) this.v = ++SelSet.contador; return r; }
  clear() { if (this.size) this.v = ++SelSet.contador; return super.clear(); }
}
SelSet.contador = 0;
window.SelSet = SelSet;

const estado = {
  resumen: null,
  cursorIcono: null,       // "tijera" | "extender" | null: icono junto al cursor (vista.js)
  trazos: [],
  geometria: [],           // primitivas exactas para el osnap
  geometriaVentana: [],    // el modelo visto por las ventanas de la hoja
  prefs: null,
  modosOsnap: {},
  seleccion: null,         // capa seleccionada en el panel
  sel: new SelSet(),       // entidades seleccionadas (ids); ver SelSet
  vista: { x: 0, y: 0, escala: 1 },
  cursor: { px: 0, py: 0, x: 0, y: 0 },   // píxeles y milímetros
  ref: null,               // referencia a objeto encontrada bajo el cursor
  resaltado: null,         // entidad encendida por el menú de «cuál de éstos»
  captura: null,           // toma de punto en curso (ver entrada.js)
  shift: false,            // Shift apretado = ortho al revés, mientras dure

  hule: null,              // lo que se pinta mientras se toma un punto
  modo: "modelo",          // "modelo" | "papel"   ·  F6
  papel: null,             // la hoja cargada cuando el modo es "papel"
  layouts: [],
  layoutActivo: 0,
};

/* --- Avisos ------------------------------------------------------------ */
let avisoTimer = null;
function avisar(texto, malo = false, ms = 5000) {
  const a = $("#aviso");
  a.textContent = texto;
  a.classList.toggle("malo", malo);
  a.classList.add("si");
  clearTimeout(avisoTimer);
  if (ms) avisoTimer = setTimeout(() => a.classList.remove("si"), ms);
}

/* --- Números ----------------------------------------------------------- */
// En el taller se trabaja en milímetros enteros; los decimales sólo estorban
// cuando no aportan.
/* La unidad de trabajo del dibujo (mm, cm o m; ver core/unidades.py). Los
 * números se enseñan con la precisión de una décima de milímetro: 2
 * decimales en mm, 3 en cm, 4 en m. Mike, 7-sep-2026. */
const U = () => (estado.resumen && estado.resumen.unidades) || "mm";
const mmPorUnidad = () => (estado.resumen && estado.resumen.mm_por_unidad) || 1;
const mm = (v) => {
  const k = mmPorUnidad();
  const dec = k >= 1000 ? 4 : k >= 10 ? 3 : 2;
  const f = Math.pow(10, dec);
  const r = Math.round(v * f) / f;
  return Number.isInteger(r) ? String(r) : r.toFixed(dec).replace(/0+$/, "");
};
const grados = (v) => (Math.round(((v % 360) + 360) % 360 * 10) / 10).toFixed(1);

/* --- Ortho ------------------------------------------------------------- */
/* **Shift invierte el ortho mientras se tiene apretado**, en los dos sentidos:
 * con ortho apagado, Shift lo enciende para esa raya; con ortho encendido,
 * Shift lo apaga para salirse un momento. Es como se dibuja en AutoCAD, y es lo
 * que evita ir al interruptor del pie dos veces por cada línea torcida.
 *
 * Vive aquí y no en `entrada.js` porque lo consultan tres sitios —la toma de
 * puntos, el arrastre de un grip y la vista previa—, y si cada uno mirara
 * `prefs.ortho` por su cuenta, Shift funcionaría en unos y en otros no. Ya pasó
 * con la selección: ver `seleccion.js`. */
const orthoActivo = () => !!((estado.prefs || {}).ortho) !== !!estado.shift;

/* Apretar o soltar Shift cambia el punto que corresponde al cursor sin que el
 * ratón se mueva: hay que repintar el hule y el interruptor del pie ahí mismo,
 * o la raya se ve torcida hasta que uno menea el ratón y ya no se sabe qué va
 * a salir. */
function fijarShift(apretado) {
  if (estado.shift === !!apretado) return;
  estado.shift = !!apretado;
  const b = document.getElementById("sw-ortho");
  if (b) {
    b.classList.toggle("on", orthoActivo());
    b.classList.toggle("temporal", !!apretado);
  }
  if (typeof Entrada !== "undefined") Entrada.alMoverse();
}

window.addEventListener("keydown", (e) => { if (e.key === "Shift") fijarShift(true); });
window.addEventListener("keyup", (e) => { if (e.key === "Shift") fijarShift(false); });
window.addEventListener("blur", () => fijarShift(false));

/* --- Preferencias ------------------------------------------------------ */
async function cargarPrefs() {
  const d = await api("/api/preferencias");
  estado.prefs = d.preferencias;
  estado.modosOsnap = d.modos_osnap;
  return estado.prefs;
}

async function guardarPrefs(cambios) {
  Object.assign(estado.prefs, cambios);     // que la interfaz reaccione ya
  const d = await post("/api/preferencias", { cambios });
  estado.prefs = d.preferencias;
  if (typeof pintarInterruptores === "function") pintarInterruptores();
  // La barra de herramientas vive en las preferencias: si cambian, se mueve.
  // Sin esto, guardar `barra` dejaba la preferencia escrita y la barra donde
  // estaba hasta el siguiente arranque — la clase de desajuste que hace dudar
  // de si el programa guardó algo.
  if (cambios && cambios.barra && typeof Barra !== "undefined") {
    Barra.desdePrefs(estado.prefs);
  }
  if (typeof pintar === "function") pintar();
  return estado.prefs;
}
