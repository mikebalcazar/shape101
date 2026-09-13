// Cascarón vacío para P1: una ventana en blanco. Sólo existe para medir cuánto
// pesa un instalador de Electron que lleva el Python con build123d empotrado.
const { app, BrowserWindow } = require("electron");
app.whenReady().then(() => {
  const w = new BrowserWindow({ width: 800, height: 600 });
  w.loadURL("data:text/html,<title>shape101</title><p>shape101 · cascarón vacío (P1)</p>");
});
app.on("window-all-closed", () => app.quit());
