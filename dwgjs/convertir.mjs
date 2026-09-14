/* DWG ↔ DXF sin instalar nada  ·  DIBUJADOR
 *
 * Dos motores, y se usan los dos porque ninguno solo alcanza:
 *
 *   · **LibreDWG** (GNU, compilado a WebAssembly). Es el lector de DWG con más
 *     kilómetros encima. Lee R13 hasta R2018 — menos **R2007**, que es el
 *     formato más retorcido de todos y donde LibreDWG tropieza.
 *   · **acad-ts** (puerto de ACadSharp, MIT, JavaScript puro). Sí lee R2007, y
 *     además **escribe** DWG, que LibreDWG en esta compilación no hace.
 *
 * Se intenta LibreDWG primero y acad-ts después. Un DWG que se abre no depende
 * de que el taller instale nada: es la diferencia entre "el programa lee DWG" y
 * "el programa lee DWG si antes te bajas otro programa".
 *
 * Se corre con Node ≥20. En la app instalada eso es el propio Electron con
 * ELECTRON_RUN_AS_NODE=1; en desarrollo, el `node` que haya.
 *
 *   node convertir.mjs dwg2dxf entrada.dwg salida.dxf
 *   node convertir.mjs dxf2dwg entrada.dxf salida.dwg [R2013]
 *
 * Contesta siempre una línea de JSON, con `ok` true o false. Nunca truena sin
 * decir por qué: del otro lado hay Python esperando una respuesta.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));

/* LibreDWG cuenta sus problemas con console.log. La salida estándar es del
   JSON y de nadie más: del otro lado hay un json.loads() esperando. */
console.log = (...a) => process.stderr.write(a.join(" ") + "\n");

/** Los .mjs se resuelven contra esta carpeta, no contra la de trabajo. */
async function traer(paquete) {
  const url = new URL(`./node_modules/${paquete}`, `file://${AQUI}/`);
  return import(url.href);
}

function buffer(ruta) {
  const b = fs.readFileSync(ruta);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

// --- DWG → DXF -------------------------------------------------------------

async function conLibreDwg(entrada, salida) {
  const { LibreDwg } = await traer("@mlightcad/libredwg-web/dist/libredwg-web.js");
  const lib = await LibreDwg.create();
  const dxf = lib.dwg_write_dxf(buffer(entrada));
  if (!dxf || dxf.length === 0) throw new Error("LibreDWG no produjo DXF");
  fs.writeFileSync(salida, dxf);
  return dxf.length;
}

async function conAcadTs(entrada, salida) {
  const { DwgReader, DxfWriter } = await traer("@node-projects/acad-ts/dist/index.js");
  const doc = DwgReader.readFromStream(buffer(entrada));
  const trozos = [];
  DxfWriter.writeToStream({ write: (s) => trozos.push(s) }, doc, false);
  const texto = trozos.join("");
  if (!texto) throw new Error("acad-ts no produjo DXF");
  fs.writeFileSync(salida, texto, "utf8");
  return Buffer.byteLength(texto);
}

/* Qué capas están de verdad apagadas, según acad-ts.
 *
 * Hace falta porque **LibreDWG escribe el color de capa en negativo** en su
 * DXF, y en DXF un color negativo quiere decir «capa apagada». Resultado: un
 * plano ajeno abre con las 31 capas apagadas, o sea en blanco. Lo descubrió el
 * primer DWG de verdad que entró (I5103 de Taller 101, 31 de 31 apagadas);
 * acad-ts lee el mismo archivo y dice que las 31 están encendidas, con los
 * mismos números de color pero en positivo.
 *
 * Así que la geometría la pone LibreDWG, que es mejor leyéndola, y el
 * encendido/apagado lo pone acad-ts, que es el que lo tiene bien. Si acad-ts
 * no puede con el archivo se devuelve null, y del lado de Python eso significa
 * «no sé, déjalas todas encendidas»: una capa encendida de más se apaga con dos
 * clics; una apagada de más parece que perdimos el plano.
 */
async function capasApagadas(entrada) {
  try {
    const { DwgReader } = await traer("@node-projects/acad-ts/dist/index.js");
    const doc = DwgReader.readFromStream(buffer(entrada));
    const apagadas = [];
    for (const c of doc.layers) if (c.isOn === false) apagadas.push(c.name);
    return apagadas;
  } catch (e) {
    process.stderr.write(`capasApagadas: ${e.message}\n`);
    return null;
  }
}

async function dwg2dxf(entrada, salida) {
  const fallos = [];
  for (const [motor, fn] of [["libredwg", conLibreDwg], ["acad-ts", conAcadTs]]) {
    try {
      const bytes = await fn(entrada, salida);
      const r = { ok: true, motor, bytes, fallos };
      // acad-ts ya leyó el archivo cuando es él quien convierte: su DXF lleva
      // el apagado bien y no hay que preguntar dos veces.
      r.apagadas = motor === "libredwg" ? await capasApagadas(entrada) : undefined;
      return r;
    } catch (e) {
      fallos.push(`${motor}: ${e.message}`);
    }
  }
  return { ok: false, error: "ningún motor pudo leer el DWG", fallos };
}

// --- DXF → DWG -------------------------------------------------------------

const VERSIONES = {
  R2000: 23, R2004: 25, R2007: 27, R2010: 29, R2013: 31, R2018: 33,
};

async function dxf2dwg(entrada, salida, version = "R2013") {
  const v = VERSIONES[String(version).toUpperCase()];
  if (!v) return { ok: false, error: `versión desconocida: ${version}` };
  try {
    const { DxfReader, DwgWriter } = await traer("@node-projects/acad-ts/dist/index.js");
    const doc = DxfReader.readFromStream(buffer(entrada));
    doc.header.version = v;
    const bytes = DwgWriter.writeToBuffer(doc);
    if (!bytes || bytes.length === 0) throw new Error("no se produjo ningún byte");
    fs.writeFileSync(salida, bytes);
    return { ok: true, motor: "acad-ts", bytes: bytes.length, version };
  } catch (e) {
    return { ok: false, error: e.message, motor: "acad-ts" };
  }
}

// --- ---------------------------------------------------------------------

const [, , orden, entrada, salida, extra] = process.argv;
let r;
try {
  if (orden === "dwg2dxf") r = await dwg2dxf(entrada, salida);
  else if (orden === "dxf2dwg") r = await dxf2dwg(entrada, salida, extra);
  else if (orden === "probar") r = { ok: true, node: process.version };
  else r = { ok: false, error: `orden desconocida: ${orden}` };
} catch (e) {
  r = { ok: false, error: e.message };
}
process.stdout.write(JSON.stringify(r) + "\n");
process.exit(r.ok ? 0 : 1);
