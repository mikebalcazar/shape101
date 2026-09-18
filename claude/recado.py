"""El mandadero · recado 25: 0.9.0, segundo intento — encuadrar en la ventana.

El armado de 0.9.0 se detuvo en tres pruebas que dibujan con el ratón: «una
línea trazada con dos clics llega al motor: se obtuvo 0». Las otras 456
pasaron. La causa se ve leyendo `vista.js`:

1. **`encuadrar` usaba el lienzo entero** para centrar el dibujo, y la ventana
   activa ahora es un cuarto. El dibujo quedaba a caballo entre las cuatro y los
   clics caían en la ventana equivocada. A cualquiera le habría pasado con Z E.
2. **Cuatro sitios reemplazaban el objeto de la cámara** por una copia
   (`estado.vista = {…}`): encuadrar sin dibujo, vista previa, un comando y el
   marco. Con una vista daba igual; con cuatro, cada uno desconecta la ventana
   activa de su cámara. Ahora se copia **dentro** del objeto, no encima.
3. Y Z E en una ventana girada la encuadra desde su ángulo, no desde arriba.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA = "claude/encuadrar-en-la-ventana"
VERSION = "0.9.0"
DESTINO = f"claude/publicar-{VERSION}"

lineas: list[str] = []


def anotar(t: str) -> None:
    print(t, flush=True)
    lineas.append(t)


def _sin_secretos(t: str) -> str:
    for n in ("TOKEN_DRAW101", "TOKEN_SHAPE101"):
        v = os.environ.get(n)
        if v:
            t = t.replace(v, "***")
    return t


def correr(orden, cwd=None) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if h.returncode != 0:
        raise RuntimeError(_sin_secretos(f"falló {orden[0]}: {h.stderr.strip()[-800:]}"))
    return h.stdout


def fin_de(t: str) -> str:
    return "\r\n" if "\r\n" in t else "\n"


def cambiar(texto: str, viejo: str, nuevo: str, donde: str, veces: int = 1) -> str:
    fin = fin_de(texto)
    viejo, nuevo = viejo.replace("\n", fin), nuevo.replace("\n", fin)
    n = texto.count(viejo)
    if veces and n != veces:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba {veces}")
    return texto.replace(viejo, nuevo)


def parchar(ruta: pathlib.Path, cambios, ya: str, donde: str) -> None:
    t = ruta.read_text(encoding="utf-8")
    if ya in t:
        anotar(f"{donde}: ya estaba, no se toca")
        return
    for c in cambios:
        veces = c[2] if len(c) > 2 else 1
        t = cambiar(t, c[0], c[1], donde, veces)
    ruta.write_text(t, encoding="utf-8", newline="")
    anotar(f"{donde}: parchado")


ENCUADRAR_VIEJO = """function encuadrar(recordar = true) {
  const caja = estado.resumen && estado.resumen.extension;
  const ancho = lienzo.clientWidth || 800;
  const alto = lienzo.clientHeight || 600;
  if (recordar) recordarVista();
  if (!caja) {
    estado.vista = { x: -ancho / 4, y: alto / 4, escala: 1 };
    return pintar();
  }
  const [x0, y0, x1, y1] = caja;
  const escala = Math.min(
    (ancho * 0.92) / Math.max(x1 - x0, 1e-6),
    (alto * 0.92) / Math.max(y1 - y0, 1e-6)
  );
  estado.vista.escala = Math.min(escala, 200);
  estado.vista.x = (x0 + x1) / 2 - ancho / 2 / estado.vista.escala;
  estado.vista.y = (y0 + y1) / 2 + alto / 2 / estado.vista.escala;
  pintar();
}"""

ENCUADRAR_NUEVO = """/** El tamaño útil de la ventana activa: su ancho y su alto sin la franja del
 *  título. Con una sola vista es el lienzo entero. */
function tamanoActivo() {
  const v = estado.vista;
  const titulo = v.w && typeof Ventanas !== "undefined" ? Ventanas.TITULO : 0;
  return { ancho: v.w || lienzo.clientWidth || 800, alto: (v.h || lienzo.clientHeight || 600) - titulo, titulo };
}

/** Cambiar la cámara **dentro** del objeto, nunca encima: la ventana activa ES
 *  ese objeto, y reemplazarlo la desconecta de su cámara. */
function ponerVista(v) {
  Object.assign(estado.vista, { x: v.x, y: v.y, escala: v.escala, rx: v.rx || 0, rz: v.rz || 0 });
}

function encuadrar(recordar = true) {
  const caja = estado.resumen && estado.resumen.extension;
  const { ancho, alto, titulo } = tamanoActivo();
  if (recordar) recordarVista();
  // Girada, se encuadra desde su ángulo: la caja en planta no dice dónde caen
  // las cosas vistas de frente.
  if ((estado.vista.rx || estado.vista.rz) && typeof Ventanas !== "undefined" && estado.vista.w) {
    Ventanas.encuadrarUna(estado.vista.i, puntosDelDibujo());
    return pintar();
  }
  if (!caja) {
    ponerVista({ x: -ancho / 4, y: alto / 4 + titulo, escala: 1 });
    return pintar();
  }
  const [x0, y0, x1, y1] = caja;
  const escala = Math.min(
    (ancho * 0.92) / Math.max(x1 - x0, 1e-6),
    (alto * 0.92) / Math.max(y1 - y0, 1e-6)
  );
  estado.vista.escala = Math.min(escala, 200);
  estado.vista.x = (x0 + x1) / 2 - ancho / 2 / estado.vista.escala;
  estado.vista.y = (y0 + y1) / 2 + (alto / 2 + titulo) / estado.vista.escala;
  pintar();
}"""

CAJA_VIEJA = """  recordarVista();
  const ancho = lienzo.clientWidth, alto = lienzo.clientHeight;
  estado.vista.escala = Math.min(500, Math.min(
    ancho / Math.abs(x1 - x0), alto / Math.abs(y1 - y0)));
  estado.vista.x = (x0 + x1) / 2 - ancho / 2 / estado.vista.escala;
  estado.vista.y = (y0 + y1) / 2 + alto / 2 / estado.vista.escala;"""

CAJA_NUEVA = """  recordarVista();
  const { ancho, alto, titulo } = tamanoActivo();
  estado.vista.escala = Math.min(500, Math.min(
    ancho / Math.abs(x1 - x0), alto / Math.abs(y1 - y0)));
  estado.vista.x = (x0 + x1) / 2 - ancho / 2 / estado.vista.escala;
  estado.vista.y = (y0 + y1) / 2 + (alto / 2 + titulo) / estado.vista.escala;"""


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado25")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    parchar(shape / "ui" / "vista.js", [
        (ENCUADRAR_VIEJO, ENCUADRAR_NUEVO),
        (CAJA_VIEJA, CAJA_NUEVA),
        ("  if (!v) return avisar(\"No hay vista anterior.\", false, 2000);\n  estado.vista = v;",
         "  if (!v) return avisar(\"No hay vista anterior.\", false, 2000);\n  ponerVista(v);"),
    ], "function tamanoActivo()", "ui/vista.js (encuadrar en la ventana activa)")
    parchar(shape / "ui" / "comandos.js", [
        ("      estado.vista = v0;", "      Object.assign(estado.vista, { x: v0.x, y: v0.y, escala: v0.escala });"),
    ], "Object.assign(estado.vista, { x: v0.x", "ui/comandos.js (no reemplazar la cámara)")
    parchar(shape / "ui" / "marco.js", [
        ("    if (v) { estado.vista = v; pintar(); } else encuadrar(false);",
         "    if (v) { Object.assign(estado.vista, { x: v.x, y: v.y, escala: v.escala }); pintar(); } else encuadrar(false);"),
    ], "Object.assign(estado.vista, { x: v.x", "ui/marco.js (no reemplazar la cámara)")
    parchar(shape / "ui" / "ventanas.js", [
        ("  function encuadrarTodas(puntos, proyectarCon = proyectar) {\n    for (const v of ventanas) {\n      if (v.w <= 0 || v.h <= 0 || !puntos.length) continue;",
         "  function encuadrarTodas(puntos, proyectarCon = proyectar, solo = null) {\n    for (const v of ventanas) {\n      if (solo !== null && v.i !== solo) continue;\n      if (v.w <= 0 || v.h <= 0 || !puntos.length) continue;"),
        ("           adoptar, encuadrarTodas, pintarTodas, proyectar, TITULO,",
         "           adoptar, encuadrarTodas, pintarTodas, proyectar, TITULO,\n           encuadrarUna: (i, puntos) => encuadrarTodas(puntos, proyectar, i),"),
    ], "encuadrarUna", "ui/ventanas.js (encuadrar una sola)")

    for js in ("vista.js", "comandos.js", "marco.js", "ventanas.js"):
        correr(["node", "--check", str(shape / "ui" / js)])
    anotar("los cuatro archivos pasan node --check")
    if "estado.vista = {" in (shape / "ui" / "vista.js").read_text(encoding="utf-8"):
        raise RuntimeError("vista.js sigue reemplazando el objeto de la cámara")
    anotar("ya nadie en vista.js reemplaza el objeto de la cámara")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, segundo intento: encuadrar en la ventana\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "Encuadrar en la ventana activa, y nunca reemplazar el objeto de la cámara\n\n"
            "El armado de 0.9.0 se detuvo en tres pruebas que dibujan con el ratón: encuadrar\n"
            "usaba el lienzo entero y la ventana activa es un cuarto, así que el dibujo\n"
            "quedaba a caballo entre las cuatro y los clics caían en la equivocada.\n\n"
            "Además, cuatro sitios reemplazaban el objeto de la cámara por una copia. Con\n"
            "una vista daba igual; con cuatro, cada uno desconecta la ventana activa de su\n"
            "cámara. Ahora se copia dentro del objeto, no encima. Y Z E en una ventana\n"
            "girada la encuadra desde su ángulo."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} movida: el armado de {VERSION} arranca de nuevo")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado25/shape101")
    if not (shape / ".git").is_dir():
        return
    try:
        correr(["git", "checkout", "--", "."], cwd=shape)
        correr(["git", "clean", "-fd"], cwd=shape)
        correr(["git", "checkout", "-B", "claude/recado-fallo"], cwd=shape)
        (shape / "claude").mkdir(exist_ok=True)
        (shape / "claude" / "ultimo-recado.md").write_text(
            "# Último recado · FALLÓ\n\n"
            f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n\n"
            "```\n" + "\n".join(lineas) + "\n\nERROR: " + error + "\n```\n", encoding="utf-8")
        correr(["git", "add", "claude/ultimo-recado.md"], cwd=shape)
        correr(["git", "commit", "-m", "recado fallido: dónde se rompió"], cwd=shape)
        correr(["git", "push", "-f", "origin", "claude/recado-fallo"], cwd=shape)
    except Exception as e2:
        print(f"ni el aviso del fracaso se pudo escribir: {e2}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        d = _sin_secretos(f"{type(e).__name__}: {e}")
        print(f"el recado falló: {d}")
        avisar_del_fracaso(d)
        sys.exit(1)
