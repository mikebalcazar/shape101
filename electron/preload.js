/* Puente entre la interfaz y Electron. Lo mínimo, y nada de Node en la página. */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("t101", {
  abrir: (filtros) => ipcRenderer.invoke("dialogo-abrir", filtros),
  guardar: (filtros, sugerido) => ipcRenderer.invoke("dialogo-guardar", filtros, sugerido),
  archivoInicial: () => ipcRenderer.invoke("archivo-inicial"),
  abrirArchivo: (ruta) => ipcRenderer.invoke("abrir-con-sistema", ruta),
  imprimirPDF: (ruta, opciones) => ipcRenderer.invoke("imprimir-pdf", ruta, opciones),
  imprimirHTML: (html, opciones) => ipcRenderer.invoke("imprimir-html", html, opciones),
  impresoras: () => ipcRenderer.invoke("listar-impresoras"),

  // El proceso principal pregunta; la página contesta con si hay cambios.
  alPreguntarCierre: (fn) => ipcRenderer.on("preguntar-cierre", fn),
  alAbrirArchivo: (fn) => ipcRenderer.on("abrir-archivo", (_e, ruta) => fn(ruta)),
  alGuardarYSalir: (fn) => ipcRenderer.on("guardar-y-salir", fn),
  cerrar: (sucio) => ipcRenderer.send("cerrar", sucio),
  idioma: (cual) => ipcRenderer.send("idioma", cual),
});
