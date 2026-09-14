/* shape101 — envoltura Electron.
 *
 * Levanta el servidor de Python, espera a /api/salud y carga la interfaz desde
 * él. Tres cosas que aquí se hacen bien desde el principio porque en Taller 101
 * costaron una versión cada una:
 *
 *  · Al cerrar se usa `destroy()`, no `close()`. El `beforeunload` del
 *    renderer cancela el cierre **en silencio** y el programa se queda abierto
 *    hasta que lo matas desde el Administrador de tareas (era el #034).
 *  · Se leen `process.argv` y el evento `open-file`, y hay candado de una sola
 *    instancia: sin eso, doble clic en un archivo abre la app vacía.
 *  · Si no hay Python empotrado, se cae al Python del sistema en vez de no
 *    arrancar.
 */

const { app, BrowserWindow, dialog, ipcMain, Menu, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

const RAIZ = path.join(__dirname, "..");
const EXTENSIONES = [".t101d", ".dxf", ".dwg"];

let ventana = null;
let python = null;
let puerto = 0;
let archivoInicial = null;

/* --- La tarjeta de video  ·  punto 6 -------------------------------------
 *
 * Mike preguntó si se puede aprovechar la gráfica discreta. Sí, y aquí está
 * todo lo que se puede hacer desde el programa; conviene saber qué compra:
 *
 *  · El lienzo es un `<canvas>` 2D de Chromium, que **ya** va acelerado: las
 *    líneas las rasteriza la GPU, no la CPU. Lo que se pide aquí es que, en un
 *    portátil con dos tarjetas, use la **discreta** en vez de la integrada, y
 *    que no se caiga a dibujar por software si el driver le parece viejo.
 *  · Lo que **no** arregla es lo que de verdad cuesta en un plano grande, que
 *    es recorrer decenas de miles de entidades en JavaScript antes de dibujar
 *    ninguna. Ese trabajo es de CPU y ninguna tarjeta lo toca. Por eso la
 *    mejora de la 0.10.0 —repintar sólo lo que cambió— valió veinticinco veces
 *    más que esto.
 *
 * O sea: se enciende porque es gratis y quita tirones al hacer zoom, no porque
 * vaya a cambiar la sensación de los comandos.
 */
app.commandLine.appendSwitch("force_high_performance_gpu");
app.commandLine.appendSwitch("ignore-gpu-blocklist");
app.commandLine.appendSwitch("enable-zero-copy");
app.commandLine.appendSwitch("enable-features", "CanvasOopRasterization");

/* --- Qué archivo pidió Windows al abrir --------------------------------- */
function archivoDeArgv(argv) {
  for (const a of argv.slice(1)) {
    if (a.startsWith("-")) continue;
    if (EXTENSIONES.includes(path.extname(a).toLowerCase()) && fs.existsSync(a)) return a;
  }
  return null;
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", (_e, argv) => {
    const archivo = archivoDeArgv(argv);
    if (ventana) {
      if (ventana.isMinimized()) ventana.restore();
      ventana.focus();
      if (archivo) ventana.webContents.send("abrir-archivo", archivo);
    }
  });
}

app.on("open-file", (e, ruta) => {     // macOS y arrastrar-al-icono
  e.preventDefault();
  if (ventana) ventana.webContents.send("abrir-archivo", ruta);
  else archivoInicial = ruta;
});

/* --- Python -------------------------------------------------------------- */
/* El Python que va dentro del paquete. Cada sistema lo guarda a su manera:
 *
 *   Windows   resources/python/python.exe
 *   macOS     Contents/Resources/python/bin/python3
 *
 * Se prueban las dos rutas en los dos sistemas en vez de ramificar por
 * `process.platform`: cuesta lo mismo, y así un paquete armado de otra forma
 * —o el árbol de desarrollo— sigue arrancando en vez de fallar por una
 * suposición sobre dónde debería estar el archivo.
 *
 * El último recurso es el Python del sistema. En macOS eso es un `python3` que
 * puede no traer nuestras librerías; arranca igual y el error, si lo hay, sale
 * en el motor y se lee, en vez de una ventana en blanco. */
const RELATIVAS_PYTHON = [
  ["python", "python.exe"],          // Windows, empotrado
  ["python", "bin", "python3"],      // macOS y Linux, empotrado
];

function ejecutablePython() {
  const bases = [process.resourcesPath || RAIZ, path.join(RAIZ, "runtime"), RAIZ];
  for (const base of bases) {
    for (const rel of RELATIVAS_PYTHON) {
      const cand = path.join(base, ...rel);
      if (fs.existsSync(cand)) return cand;
    }
  }
  return process.platform === "win32" ? "python" : "python3";
}

function esperarSalud(p, intentos = 120) {
  return new Promise((resolve, reject) => {
    const probar = (n) => {
      http.get({ host: "127.0.0.1", port: p, path: "/api/salud", timeout: 800 }, (res) => {
        res.resume();
        res.statusCode === 200 ? resolve() : reintentar(n);
      }).on("error", () => reintentar(n));
    };
    const reintentar = (n) => {
      if (n <= 0) return reject(new Error("El motor no respondió"));
      setTimeout(() => probar(n - 1), 250);
    };
    probar(intentos);
  });
}

async function arrancarMotor() {
  const net = require("net");
  puerto = await new Promise((res) => {
    const s = net.createServer();
    s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => res(p)); });
  });

  python = spawn(ejecutablePython(), [path.join(RAIZ, "server.py"), String(puerto)], {
    cwd: RAIZ,
    env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
  });
  python.stdout.on("data", (d) => process.stdout.write(`[motor] ${d}`));
  python.stderr.on("data", (d) => process.stderr.write(`[motor] ${d}`));

  await esperarSalud(puerto);
}

/* --- Pantalla de carga --------------------------------------------------
 *
 * Mientras arranca el motor de Python (de dos a diez segundos en una máquina
 * del taller) no había nada en pantalla, y la gente le daba doble clic otra
 * vez. Ahora sale `cargando.html`: una ventana **sin marco y transparente**,
 * así que lo que se ve es el plano flotando sobre el escritorio y la marca en
 * medio; no un recuadro. Se cierra sola cuando la ventana principal ya pintó.
 *
 * `hasShadow: false` porque la sombra la trae el propio dibujo; la de Windows
 * dibujaría el rectángulo de la ventana, que es justo lo que no se quiere.
 */
let cargando = null;
let cargandoDesde = 0;

function abrirCargando() {
  cargando = new BrowserWindow({
    width: 760, height: 520, frame: false, transparent: true, resizable: false,
    hasShadow: false, alwaysOnTop: true, skipTaskbar: true, show: false,
    center: true, movable: true, focusable: false,
    icon: path.join(RAIZ, "build", "icon.ico"),
    title: "shape101",
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  cargando.setMenu(null);
  cargando.loadFile(path.join(__dirname, "cargando.html"));
  cargando.once("ready-to-show", () => { if (cargando) cargando.show(); });
  cargando.on("closed", () => { cargando = null; });
  cargandoDesde = Date.now();
}

function avisarCargando(texto) {
  if (!cargando || cargando.isDestroyed()) return;
  cargando.webContents.executeJavaScript(`window.estado && window.estado(${JSON.stringify(texto)})`)
    .catch(() => {});
}

function cerrarCargando() {
  if (!cargando || cargando.isDestroyed()) return;
  // Que se alcance a ver: si el motor arrancó en medio segundo, la pantalla
  // parpadearía. Un segundo y medio es lo mínimo para leer el nombre.
  const falta = Math.max(0, 1500 - (Date.now() - cargandoDesde));
  const c = cargando;
  cargando = null;
  setTimeout(() => { if (!c.isDestroyed()) c.destroy(); }, falta);
}

/* --- Ventana ------------------------------------------------------------- */
function crearVentana() {
  ventana = new BrowserWindow({
    width: 1360, height: 860, minWidth: 1024, minHeight: 640,
    backgroundColor: "#eef0f3",
    icon: path.join(RAIZ, "build", "icon.ico"),
    title: "shape101",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  ventana.loadURL(`http://127.0.0.1:${puerto}/`);
  ventana.on("closed", () => { ventana = null; });
  // La principal sale cuando ya tiene qué enseñar, y en ese momento se va la
  // de carga: nunca hay un hueco vacío entre las dos.
  ventana.once("ready-to-show", () => { ventana.show(); cerrarCargando(); });
  // Por si `ready-to-show` no llega (pasa con algunas gráficas): a los 4 s se
  // enseña de todos modos.
  setTimeout(() => { if (ventana && !ventana.isVisible()) { ventana.show(); cerrarCargando(); } }, 4000);

  // El zoom de página, clavado en 1. Ctrl+rueda o Ctrl+más agrandaban la
  // interfaz entera y el pie se salía de la ventana; el zoom que importa es el
  // del dibujo, y ése lo hace el lienzo.
  ventana.webContents.on("did-finish-load", () => {
    ventana.webContents.setZoomFactor(1);
    ventana.webContents.setVisualZoomLevelLimits(1, 1).catch(() => {});
  });
  ventana.webContents.on("zoom-changed", () => {
    ventana.webContents.setZoomFactor(1);
  });

  // El cierre se decide aquí, no en la página: `close()` vuelve a disparar el
  // beforeunload del renderer y el proceso se queda vivo sin decir nada.
  ventana.on("close", (e) => {
    e.preventDefault();
    ventana.webContents.send("preguntar-cierre");
  });

  ventana.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

/* Idioma de los cuadros nativos (abrir, guardar, salir). La página lo manda
 * al arrancar y al cambiarlo; hasta entonces, inglés, como el resto (0.19.0). */
let idioma = "en";
const TEXTOS = {
  es: {
    abrir: "Abrir dibujo", guardar: "Guardar", guardarSalir: "Guardar y salir",
    salirSin: "Salir sin guardar", cancelar: "Cancelar",
    cambiosN: (n) => `Hay cambios sin guardar en ${n} dibujos.`,
    cambios1: "Hay cambios sin guardar en el dibujo.",
    detalle: "Si sales sin guardar, los cambios se pierden: no se conserva copia de recuperación.",
    noArranco: "No arrancó el motor de dibujo.",
    dibujoT101: "Dibujo Taller 101", todos: "Todos los dibujos",
  },
  en: {
    abrir: "Open drawing", guardar: "Save", guardarSalir: "Save and exit",
    salirSin: "Exit without saving", cancelar: "Cancel",
    cambiosN: (n) => `There are unsaved changes in ${n} drawings.`,
    cambios1: "There are unsaved changes in the drawing.",
    detalle: "If you exit without saving, the changes are lost: no recovery copy is kept.",
    noArranco: "The drawing engine did not start.",
    dibujoT101: "Taller 101 drawing", todos: "All drawings",
  },
};
const tx = () => TEXTOS[idioma] || TEXTOS.en;
ipcMain.on("idioma", (_e, cual) => { idioma = cual === "es" ? "es" : "en"; });

// Los nombres de los filtros de archivo vienen de la página en español; aquí
// se traducen los que se conocen.
function filtrosTraducidos(filtros) {
  const mapa = { "Dibujo Taller 101": tx().dibujoT101, "Todos los dibujos": tx().todos,
                 "Dibujos": idioma === "es" ? "Dibujos" : "Drawings", "Todos los archivos": idioma === "es" ? "Todos los archivos" : "All files",
                 "Imágenes": idioma === "es" ? "Imágenes" : "Images" };
  return (filtros || []).map((f) => ({ ...f, name: mapa[f.name] || f.name }));
}

ipcMain.handle("dialogo-abrir", async (_e, filtros) => {
  const r = await dialog.showOpenDialog(ventana, {
    title: tx().abrir, properties: ["openFile"], filters: filtrosTraducidos(filtros),
  });
  return r.canceled ? null : r.filePaths[0];
});

ipcMain.handle("dialogo-guardar", async (_e, filtros, sugerido) => {
  const r = await dialog.showSaveDialog(ventana, {
    title: tx().guardar, defaultPath: sugerido, filters: filtrosTraducidos(filtros),
  });
  return r.canceled ? null : r.filePath;
});

// Abrir el PDF recién impreso con el visor del sistema. Es lo que espera
// cualquiera después de darle a imprimir: ver la hoja.
//
// El canal se llama distinto del «abrir-archivo» que va de aquí a la página
// (el del doble clic en un .t101d) aunque Electron los guarde en mapas
// separados: dos cosas con el mismo nombre y direcciones contrarias es una
// trampa esperando a que alguien la pise.
ipcMain.handle("abrir-con-sistema", async (_e, ruta) => {
  const error = await shell.openPath(ruta);
  return error || null;
});

/* --- Imprimir en impresora de verdad  ·  punto 12 ------------------------
 *
 * El camino es: el motor arma el PDF de la hoja —el mismo que ya se exporta,
 * con su marco y su pie de plano— y aquí se abre en una ventana escondida y se
 * manda a la impresora desde ella.
 *
 * Por qué así y no imprimiendo la página directamente: la pantalla no es la
 * hoja. Imprimir el lienzo saca lo que se ve, con su zoom y sin marco, y a una
 * escala que no es ninguna. Pasando por el PDF, lo que sale de la impresora es
 * exactamente lo que saldría del plóter, que es lo único medible con
 * escalímetro.
 *
 * `printBackground` va encendido porque los rellenos de los rayados son fondo.
 *
 * Se puede mandar a una impresora **por su nombre** (`deviceName`), que es lo
 * que usa el cuadro de shape101, o dejar salir el cuadro de Windows. Las dos
 * cosas imprimen en las impresoras instaladas en la PC; la diferencia es quién
 * elige. En un taller la impresora es siempre la misma, y tener que pasar por
 * el cuadro de Windows en cada hoja es un clic de más doscientas veces al mes.
 */

/** Las impresoras instaladas en esta máquina, tal como las ve Windows. */
ipcMain.handle("listar-impresoras", async () => {
  const w = ventana || BrowserWindow.getAllWindows()[0];
  if (!w) return [];
  try {
    const lista = await w.webContents.getPrintersAsync();
    return lista.map((p) => ({
      nombre: p.name,
      descripcion: p.displayName || p.description || "",
      omision: !!p.isDefault,
      estado: p.status,
    }));
  } catch (e) {
    return [];
  }
});

ipcMain.handle("imprimir-pdf", async (_e, ruta, opciones) => {
  if (!fs.existsSync(ruta)) return "No se encontró el PDF que se iba a imprimir";
  const o = opciones || {};
  // Hija de la ventana principal: un cuadro de impresión colgado de una
  // ventana escondida sale detrás de todo y parece que el programa se colgó.
  const oculta = new BrowserWindow({
    show: false,
    parent: ventana || undefined,
    webPreferences: { plugins: true, contextIsolation: true, nodeIntegration: false },
  });
  try {
    await oculta.loadURL("file://" + ruta.replace(/\\/g, "/"));
    // El visor de PDF de Chromium necesita un instante después de cargar: sin
    // esta espera se ha visto imprimir la primera página en blanco.
    await new Promise((r) => setTimeout(r, 700));
    const ajustes = {
      silent: !!o.deviceName,          // con impresora elegida no hace falta cuadro
      printBackground: true,
      color: o.color !== false,
      copies: Math.max(1, Math.min(parseInt(o.copias, 10) || 1, 99)),
    };
    if (o.deviceName) ajustes.deviceName = o.deviceName;
    if (o.horizontal !== undefined) ajustes.landscape = !!o.horizontal;
    const resultado = await new Promise((resolver) => {
      oculta.webContents.print(ajustes,
        (ok, motivo) => resolver(ok ? null : (motivo || "cancelado")));
    });
    return resultado === "cancelado" ? "cancelado" : resultado;
  } catch (e) {
    return e.message;
  } finally {
    if (!oculta.isDestroyed()) oculta.destroy();
  }
});

/* Imprimir una página HTML del tamaño exacto del papel, sin márgenes: así la
 * hoja queda centrada en el papel y no en el área imprimible (ver
 * `Papel.imprimirEn` en ui/papel.js). */
ipcMain.handle("imprimir-html", async (_e, html, opciones) => {
  const o = opciones || {};
  const os = require("os");
  const ruta = path.join(os.tmpdir(), `shape101-imprimir-${Date.now()}.html`);
  fs.writeFileSync(ruta, html, "utf-8");
  const oculta = new BrowserWindow({
    show: false,
    parent: ventana || undefined,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  try {
    await oculta.loadURL("file://" + ruta.replace(/\\/g, "/"));
    await new Promise((r) => setTimeout(r, 400));
    const ajustes = {
      silent: !!o.deviceName,
      printBackground: true,
      color: o.color !== false,
      copies: Math.max(1, Math.min(parseInt(o.copias, 10) || 1, 99)),
      margins: { marginType: "none" },
      scaleFactor: 100,
    };
    if (o.deviceName) ajustes.deviceName = o.deviceName;
    if (o.anchoMM && o.altoMM) {
      // El papel se pide en vertical y se gira con `landscape`: es como lo
      // entiende Chromium; un tamaño ya apaisado más landscape lo giraba dos veces.
      const corto = Math.min(o.anchoMM, o.altoMM), largo = Math.max(o.anchoMM, o.altoMM);
      ajustes.pageSize = { width: Math.round(corto * 1000), height: Math.round(largo * 1000) };
      ajustes.landscape = !!o.horizontal;
    }
    const resultado = await new Promise((resolver) => {
      oculta.webContents.print(ajustes, (ok, motivo) => resolver(ok ? null : (motivo || "cancelado")));
    });
    return resultado === "cancelado" ? "cancelado" : resultado;
  } catch (e) {
    return e.message;
  } finally {
    if (!oculta.isDestroyed()) oculta.destroy();
    try { fs.unlinkSync(ruta); } catch (_) { /* nada */ }
  }
});

ipcMain.handle("archivo-inicial", () => {
  const r = archivoInicial;
  archivoInicial = null;
  return r;
});

/* Avisarle al motor que el cierre fue **por la X**, ya contestado si se guarda
 * o no. Con eso tira los autoguardados y quita la marca de sesión: la próxima
 * vez no hay nada que recuperar. Si el programa se cae —o lo matan desde el
 * Administrador de tareas— esto no corre, la marca se queda, y al abrir se
 * ofrece recuperar. Es exactamente la regla que pidió Mike el 6-sep. */
function cerrarSesionMotor() {
  return new Promise((resolver) => {
    if (!puerto) return resolver();
    const req = http.request({ host: "127.0.0.1", port: puerto, path: "/api/sesion/cerrar",
                               method: "POST", timeout: 1500 }, (res) => { res.resume(); resolver(); });
    req.on("error", () => resolver());
    req.on("timeout", () => { req.destroy(); resolver(); });
    req.end();
  });
}

let cerrandoBien = false;

async function salirBien() {
  if (cerrandoBien) return;
  cerrandoBien = true;
  await cerrarSesionMotor();
  if (ventana && !ventana.isDestroyed()) ventana.destroy();   // destroy, no close: ver arriba
}

ipcMain.on("cerrar", (_e, sucio) => {
  // `sucio` puede ser un número (cuántos dibujos tienen cambios) o un booleano.
  const n = typeof sucio === "number" ? sucio : (sucio ? 1 : 0);
  if (n > 0) {
    const eleccion = dialog.showMessageBoxSync(ventana, {
      type: "warning",
      buttons: [tx().guardarSalir, tx().salirSin, tx().cancelar],
      defaultId: 0, cancelId: 2,
      message: n > 1 ? tx().cambiosN(n) : tx().cambios1,
      detail: tx().detalle,
    });
    if (eleccion === 2) return;
    if (eleccion === 0) { ventana.webContents.send("guardar-y-salir"); return; }
  }
  salirBien();
});

app.whenReady().then(async () => {
  archivoInicial = archivoDeArgv(process.argv);
  // Sin esto, Windows agrupa la ventana bajo «Electron» en la barra de tareas
  // y le pone el icono de Electron en vez del nuestro.
  app.setAppUserModelId("mx.taller101.dibujador");
  Menu.setApplicationMenu(null);
  abrirCargando();
  try {
    avisarCargando("Arrancando el motor de dibujo");
    await arrancarMotor();
    avisarCargando("Abriendo la interfaz");
    crearVentana();
  } catch (err) {
    if (cargando && !cargando.isDestroyed()) cargando.destroy();
    dialog.showErrorBox("shape101", tx().noArranco + "\n\n" + err.message);
    app.quit();
  }
});

app.on("window-all-closed", () => { if (python) python.kill(); app.quit(); });
app.on("before-quit", () => { if (python) python.kill(); });
