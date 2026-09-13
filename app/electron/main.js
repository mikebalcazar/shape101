// El cascarón de shape101: el mismo patrón que draw101. Electron elige un
// puerto libre, arranca el motor (Python empotrado en resources/python, o el
// .venv del repositorio en desarrollo), espera /api/salud y carga la pantalla
// desde el propio motor. Los diálogos de archivo se los presta a la página por
// preload.js, porque un navegador no sabe rutas.
const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const net = require("net");
const path = require("path");
const fs = require("fs");

let python = null, puerto = 0, ventana = null;

function rutaMotor() {
  // empaquetado: resources/python/python.exe y resources/app101/app/...
  const rec = process.resourcesPath || "";
  const empotrado = process.platform === "win32" ? path.join(rec, "python", "python.exe") : path.join(rec, "python", "bin", "python3");
  if (fs.existsSync(empotrado)) return { exe: empotrado, cwd: path.join(rec, "app101") };
  // desarrollo: el .venv del repositorio (o SHAPE101_PYTHON)
  const raiz = path.resolve(__dirname, "..", "..");
  const venv = process.platform === "win32" ? path.join(raiz, ".venv", "Scripts", "python.exe") : path.join(raiz, ".venv", "bin", "python");
  return { exe: process.env.SHAPE101_PYTHON || (fs.existsSync(venv) ? venv : (process.platform === "win32" ? "python" : "python3")), cwd: raiz };
}
const puertoLibre = () => new Promise((res) => { const s = net.createServer(); s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => res(p)); }); });
function esperarSalud(p, intentos = 200) {
  return new Promise((res, rej) => {
    const uno = (n) => http.get({ host: "127.0.0.1", port: p, path: "/api/salud", timeout: 800 }, (r) => (r.statusCode === 200 ? res() : reintento(n)))
      .on("error", () => reintento(n)).on("timeout", function () { this.destroy(); reintento(n); });
    const reintento = (n) => (n <= 0 ? rej(new Error("el motor no contestó")) : setTimeout(() => uno(n - 1), 250));
    uno(intentos);
  });
}
async function arrancarMotor() {
  puerto = await puertoLibre();
  const { exe, cwd } = rutaMotor();
  python = spawn(exe, ["-m", "app.motor.servidor", String(puerto)], { cwd, env: { ...process.env, PYTHONUTF8: "1" } });
  python.stdout.on("data", (d) => process.stdout.write(`[motor] ${d}`));
  python.stderr.on("data", (d) => process.stderr.write(`[motor] ${d}`));
  python.on("exit", (c) => { if (ventana && !ventana.isDestroyed()) dialog.showErrorBox("shape101", `El motor se cerró (código ${c}).`); });
  await esperarSalud(puerto);
}
function abrirVentana() {
  ventana = new BrowserWindow({ width: 1280, height: 820, title: "shape101", backgroundColor: "#1d1f22",
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false } });
  ventana.setMenuBarVisibility(false);
  ventana.loadURL(`http://127.0.0.1:${puerto}/`);
}
ipcMain.handle("dialogo:abrir", async (_e, ext) => {
  const r = await dialog.showOpenDialog(ventana, { properties: ["openFile"], filters: [{ name: `Archivos .${ext}`, extensions: [ext] }] });
  return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle("dialogo:guardar", async (_e, nombre, ext) => {
  const r = await dialog.showSaveDialog(ventana, { defaultPath: nombre, filters: [{ name: `Archivos .${ext}`, extensions: [ext] }] });
  return r.canceled ? null : r.filePath;
});
app.whenReady().then(async () => {
  try { await arrancarMotor(); abrirVentana(); }
  catch (e) { dialog.showErrorBox("shape101", `No arrancó el motor: ${e.message}`); app.quit(); }
});
app.on("window-all-closed", () => { if (python) python.kill(); app.quit(); });
app.on("before-quit", () => { if (python) python.kill(); });
