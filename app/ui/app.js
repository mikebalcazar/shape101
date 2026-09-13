// La pantalla de shape101  ·  versión inicial (0.1.0).
//
// Todo el estado vive en el motor (el mismo patrón que draw101): esta página
// manda operaciones por la API local y pinta lo que el motor devuelve. Una
// geometría por cara en Three.js, para poder elegir una cara con un raycast y
// saber su nombre (que es el nombre estable del historial).
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const $ = (id) => document.getElementById(id);
const estado = $("estado");
const escritorio = window.escritorio || null;   // lo pone el cascarón de Electron (diálogos de archivo)

// ------------------------------------------------------------------ la API
async function api(ruta, cuerpo) {
  const r = await fetch(ruta, cuerpo === undefined ? undefined
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
  const j = await r.json();
  if (!r.ok || j.error) throw new Error(j.error || `${r.status} en ${ruta}`);
  return j;
}
function decir(texto, error = false) { estado.textContent = texto; estado.className = error ? "error" : ""; }
async function intentar(f) {
  try { await f(); } catch (e) { decir("No se pudo: " + e.message, true); console.error(e); }
}

// ------------------------------------------------------------------ el 3D
const lienzo = $("lienzo");
const renderer = new THREE.WebGLRenderer({ canvas: lienzo, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
const escena = new THREE.Scene();
escena.background = new THREE.Color(0x1d1f22);
const camara = new THREE.PerspectiveCamera(45, 1, 1, 100000);
const controles = new OrbitControls(camara, lienzo);
// Se pinta sólo cuando algo cambia (orbitar, un modelo nuevo, la ventana). Un
// bucle de animación sin fin con el renderizador por software de un corredor
// de dos núcleos dejó al motor sin procesador: un redondeo de 200 ms tardó
// 118 s. Medido el 13-sep en windows-latest.
const pintar3d = () => renderer.render(escena, camara);
controles.addEventListener("change", pintar3d);
escena.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2));
const luz = new THREE.DirectionalLight(0xffffff, 1.4); luz.position.set(1, 2, 3); escena.add(luz);
const grupo = new THREE.Group(); escena.add(grupo);
const matNormal = new THREE.MeshStandardMaterial({ color: 0xc8a165, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1 });
const matElegida = new THREE.MeshStandardMaterial({ color: 0xffd35a, emissive: 0x553300, side: THREE.DoubleSide });
const matLinea = new THREE.LineBasicMaterial({ color: 0x111111 });
let mallas = [], elegida = null, encuadrado = false;

function ajustar() {
  const w = lienzo.clientWidth || 800, h = lienzo.clientHeight || 600;
  renderer.setSize(w, h, false); camara.aspect = w / h; camara.updateProjectionMatrix();
  pintar3d();
}
window.addEventListener("resize", ajustar); ajustar();

function pintar(modelo) {
  const nombreElegida = elegida && elegida.name;
  grupo.clear(); mallas = []; elegida = null;
  for (const c of modelo.caras) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(c.v, 3));
    g.setIndex(c.i); g.computeVertexNormals();
    const m = new THREE.Mesh(g, matNormal); m.name = c.nombre; grupo.add(m); mallas.push(m);
    if (c.nombre === nombreElegida) { elegida = m; m.material = matElegida; }
  }
  for (const a of modelo.aristas) {
    grupo.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(a.map((p) => new THREE.Vector3(...p))), matLinea));
  }
  if (!encuadrado && mallas.length) { encuadrar(); encuadrado = true; }
  pintar3d();
  $("e-cara").value = elegida ? elegida.name : "";
  const [x, y, z] = modelo.caja || [0, 0, 0];
  $("medidas").textContent = modelo.n_caras
    ? `caja ${x} × ${y} × ${z} mm\nvolumen ${(modelo.volumen_mm3 / 1000).toFixed(1)} cm³\n${modelo.n_caras} caras · ${modelo.n_triangulos} triángulos\nregenerar ${modelo.ms_regenerar} ms · teselar ${modelo.ms_teselar} ms`
    : "—";
}
function encuadrar() {
  const caja = new THREE.Box3().setFromObject(grupo);
  if (caja.isEmpty()) return;
  const c = new THREE.Vector3(); caja.getCenter(c);
  const r = caja.getSize(new THREE.Vector3()).length() / 2 || 100;
  camara.position.set(c.x + r * 1.2, c.y - r * 1.6, c.z + r * 1.2); camara.up.set(0, 0, 1);
  controles.target.copy(c); controles.update(); pintar3d();
}
const ray = new THREE.Raycaster();
function elegir(px, py) {
  const w = lienzo.clientWidth, h = lienzo.clientHeight;
  ray.setFromCamera(new THREE.Vector2((px / w) * 2 - 1, -(py / h) * 2 + 1), camara);
  const hit = ray.intersectObjects(mallas, false)[0];
  if (elegida) elegida.material = matNormal;
  elegida = hit ? hit.object : null;
  if (elegida) elegida.material = matElegida;
  pintar3d();
  $("e-cara").value = elegida ? elegida.name : "";
  return hit ? { nombre: hit.object.name, punto: hit.point.toArray(), normal: hit.face.normal.toArray() } : null;
}
// Clic elige; clic + arrastre en la dirección de la normal empuja.
let arrastre = null;
lienzo.addEventListener("pointerdown", (e) => {
  const r = lienzo.getBoundingClientRect();
  const hit = elegir(e.clientX - r.left, e.clientY - r.top);
  if (!hit) return;
  const n = new THREE.Vector3(...hit.normal).project(camara), o = new THREE.Vector3(...hit.punto).project(camara);
  arrastre = { nombre: hit.nombre, x: e.clientX, y: e.clientY, dir: new THREE.Vector2(n.x - o.x, -(n.y - o.y)).normalize() };
  controles.enabled = false;
});
window.addEventListener("pointerup", (e) => {
  controles.enabled = true;
  if (!arrastre) return;
  const d = new THREE.Vector2(e.clientX - arrastre.x, e.clientY - arrastre.y).dot(arrastre.dir);
  const mm = Math.round(d * 100) / 100; const nombre = arrastre.nombre; arrastre = null;
  if (Math.abs(mm) >= 1) intentar(() => operacion({ op: "empujar_cara", cara: nombre, mm }));
});

// ------------------------------------------------------------------ el documento
let doc = null, rutaActual = null;
function espesor() { return Number($("p-espesor").value); }
function etiqueta(op, i) {
  switch (op.op) {
    case "boceto": { const e = op.entidades[0]; return e.tipo === "polilinea" ? `boceto rectángulo` : e.tipo === "circulo" ? `boceto círculo ⌀${2 * e.radio}` : `boceto`; }
    case "extruir": return `extruir ${op.mm} mm`;
    case "restar": { const e = op.entidades[0]; return e.tipo === "circulo" ? `barreno ⌀${2 * e.radio} en (${e.centro[0]}, ${e.centro[1]})` : `corte rectangular`; }
    case "redondear": return `redondear ${op.aristas.length} aristas r=${op.r}`;
    case "empujar_cara": return `empujar «${op.cara}» ${op.mm} mm`;
    default: return op.op;
  }
}
let opElegida = null;
function pintarHistorial() {
  const ol = $("historial"); ol.innerHTML = "";
  (doc ? doc.operaciones : []).forEach((op, i) => {
    const li = document.createElement("li"); li.textContent = etiqueta(op, i); li.dataset.i = i;
    if (i === opElegida) li.className = "elegida";
    li.onclick = () => { opElegida = i; $("ed-json").value = JSON.stringify(op, null, 1); $("editor").hidden = false; pintarHistorial(); };
    ol.appendChild(li);
  });
  $("p-nombre").value = doc ? doc.pieza.nombre : ""; $("p-material").value = doc ? doc.pieza.material : "";
  if (doc) $("p-espesor").value = doc.pieza.espesor_mm;
}
async function refrescar(modelo) {
  doc = await api("/api/documento");
  pintar(modelo || await api("/api/modelo"));
  pintarHistorial();
  document.title = `shape101 · ${doc.pieza.nombre}${rutaActual ? " · " + rutaActual : ""}`;
}
async function operacion(op) {
  const modelo = await api("/api/operacion", { op });
  await refrescar(modelo);
  decir(`${etiqueta(op)} · listo`);
}
async function nuevaPieza() {
  await api("/api/documento/nuevo", { nombre: $("p-nombre").value || "Pieza", material: $("p-material").value, espesor_mm: espesor() });
  rutaActual = null; encuadrado = false; opElegida = null; $("editor").hidden = true;
  doc = await api("/api/documento"); grupo.clear(); mallas = []; elegida = null; pintar({ caras: [], aristas: [] }); pintarHistorial();
  decir("pieza nueva: ponle un tablero");
}
function rect(x, y, w, h) {
  return [{ tipo: "polilinea", cerrada: true, puntos: [[x, y, 0], [x + w, y, 0], [x + w, y + h, 0], [x, y + h, 0]] }];
}
const PASANTE_EXTRA = 200;   // el corte pasa de sobra aunque la cara de arriba se haya empujado

// ------------------------------------------------------------------ botones
$("b-nuevo").onclick = () => intentar(nuevaPieza);
$("b-tablero").onclick = () => intentar(async () => {
  if (!doc) await nuevaPieza();
  await api("/api/operacion", { op: { op: "boceto", plano: "XY", entidades: rect(0, 0, Number($("t-ancho").value), Number($("t-fondo").value)) } });
  await operacion({ op: "extruir", mm: espesor() });
});
$("b-barreno").onclick = () => intentar(() => operacion({ op: "restar", mm: espesor() + PASANTE_EXTRA,
  entidades: [{ tipo: "circulo", centro: [Number($("h-x").value), Number($("h-y").value)], radio: Number($("h-d").value) / 2 }] }));
$("b-corte").onclick = () => intentar(() => operacion({ op: "restar", mm: espesor() + PASANTE_EXTRA,
  entidades: rect(Number($("c-x").value), Number($("c-y").value), Number($("c-ancho").value), Number($("c-alto").value)) }));
$("b-redondear").onclick = () => intentar(async () => {
  const { aristas } = await api("/api/aristas");
  // las esquinas verticales del tablero: aristas entre dos lados del primer boceto
  const verticales = aristas.filter((a) => /^lado\[\d+\]\|lado\[\d+\]$/.test(a));
  if (!verticales.length) throw new Error("no hay esquinas verticales que redondear (¿ya están redondeadas?)");
  await operacion({ op: "redondear", aristas: verticales, r: Number($("r-radio").value) });
});
$("b-empujar").onclick = () => intentar(async () => {
  if (!elegida) throw new Error("primero elige una cara con clic en el 3D");
  await operacion({ op: "empujar_cara", cara: elegida.name, mm: Number($("e-mm").value) });
});
$("b-aplicar").onclick = () => intentar(async () => {
  const op = JSON.parse($("ed-json").value);
  const modelo = await api("/api/operacion/editar", { i: opElegida, op });
  await refrescar(modelo); decir("operación editada y regenerada");
});
$("b-borrar").onclick = () => intentar(async () => {
  const modelo = await api("/api/operacion/borrar", { i: opElegida });
  opElegida = null; $("editor").hidden = true; await refrescar(modelo); decir("operación borrada");
});
$("b-cancelar").onclick = () => { opElegida = null; $("editor").hidden = true; pintarHistorial(); };

async function rutaPara(guardar, nombre, ext) {
  if (escritorio) return guardar ? escritorio.guardar(nombre, ext) : escritorio.abrir(ext);
  return window.prompt(`Ruta del archivo (.${ext})`, nombre);     // en un navegador suelto, sin diálogos
}
$("b-abrir").onclick = () => intentar(async () => {
  const ruta = await rutaPara(false, "", "s101"); if (!ruta) return;
  const modelo = await api("/api/documento/abrir", { ruta }) && await api("/api/modelo");
  rutaActual = ruta; encuadrado = false; await refrescar(modelo); decir(`abierto ${ruta}`);
});
async function guardar(preguntar) {
  if (!doc) throw new Error("no hay pieza que guardar");
  let ruta = rutaActual;
  if (preguntar || !ruta) ruta = await rutaPara(true, `${doc.pieza.nombre}.s101`, "s101");
  if (!ruta) return;
  const r = await api("/api/documento/guardar", { ruta }); rutaActual = r.ruta; await refrescar(); decir(`guardado ${r.ruta}`);
}
$("b-guardar").onclick = () => intentar(() => guardar(false));
$("b-guardar-como").onclick = () => intentar(() => guardar(true));
for (const [id, formato, ext] of [["b-step", "step", "step"], ["b-stl", "stl", "stl"], ["b-gltf", "gltf", "glb"]]) {
  $(id).onclick = () => intentar(async () => {
    if (!doc) throw new Error("no hay pieza que exportar");
    const ruta = await rutaPara(true, `${doc.pieza.nombre}.${ext}`, ext); if (!ruta) return;
    const r = await api("/api/exportar", { formato, ruta }); decir(`exportado ${r.ruta} (${r.bytes} bytes)`);
  });
}

// ------------------------------------------------------------------ arranque
window.shape101 = { api, elegir, mallas: () => mallas.map((m) => m.name), elegida: () => elegida && elegida.name,
  puntoEnPantalla: (nombre) => { const m = mallas.find((x) => x.name === nombre); if (!m) return null;
    const pos = m.geometry.attributes.position, ix = m.geometry.index; const c = new THREE.Vector3();
    for (let k = 0; k < 3; k++) c.add(new THREE.Vector3().fromBufferAttribute(pos, ix.getX(k)));
    c.multiplyScalar(1 / 3).project(camara); const r = lienzo.getBoundingClientRect();
    return [(c.x + 1) / 2 * lienzo.clientWidth + r.left, (1 - c.y) / 2 * lienzo.clientHeight + r.top]; } };
intentar(async () => {
  const salud = await api("/api/salud");
  $("version").textContent = salud.version;
  try { doc = await api("/api/documento"); await refrescar(); decir("motor listo"); }
  catch { decir("motor listo · empieza con «Nueva pieza» y «Poner tablero»"); }
  window.__lista = true;
});
