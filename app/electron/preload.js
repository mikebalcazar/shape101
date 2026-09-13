// Lo único que la página puede pedirle al cascarón: diálogos de archivo.
const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("escritorio", {
  abrir: (ext) => ipcRenderer.invoke("dialogo:abrir", ext),
  guardar: (nombre, ext) => ipcRenderer.invoke("dialogo:guardar", nombre, ext),
});
