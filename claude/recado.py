"""El mandadero · recado 19: 0.7.0 — el visor toma el mando girado.

Lo que Mike vio en la 0.6.1, y su causa, cada una encontrada en el código:

1. **Lento, y las líneas se quedaban en 2D.** El recado 17 giró el bucle de los
   rellenos (`t.poligonos`) y no el de las líneas (`t.puntos`), que va aparte
   con la cuenta a mano. Parché el bucle equivocado. Y aun bien parchado, el
   pintado viejo redibuja el plano entero con sus cachés peleando contra la
   cámara. Solución: **cuando la cámara está girada, pinta el visor nuevo**
   (`ui/visor.js`), sin lotes ni foto ni recorte. En planta sigue el pintado
   de siempre, intacto, con sus 470 comprobaciones.
2. **Orbitar raro al topar, y el pan se dispara solo.** La órbita escuchaba
   eventos `pointer` y el lienzo escucha `mouse`: frenar unos no frena los
   otros, así que los dos gestos corrían a la vez. Ahora la órbita escucha
   los mismos `mouse` que el lienzo y se queda con ellos.
3. **Zoom descentrado girado.** `zoomEn` convertía el cursor a coordenadas del
   plano y las mezclaba con `vista.x`, que vive en el espacio de la cámara.
   En planta son lo mismo; girado, se van por media pantalla. Ahora la cuenta
   va en el espacio de la cámara: en planta da lo mismo de siempre.
4. **Los sólidos no se redibujaban tras jalar.** La caché del plano no sabía
   que la pieza cambió. Ahora, cuando una pieza cambia, se invalida el plano.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import re
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA = "claude/el-visor-toma-el-mando"
VERSION = "0.7.0"
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
    if not veces and n == 0:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» no aparece")
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


BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "Con la vista girada pinta un visor nuevo, pensado en 3D: las líneas del dibujo y "
            "las piezas en un mismo espacio, sin los atajos de planta que hacían que las "
            "líneas se quedaran en 2D y que girar fuera lento. En planta todo sigue igual.",
            "Orbitar ya no se pelea con el pan: mientras giras, el ratón es de la cámara.",
            "El zoom con la rueda girado ya no se descentra: lo que está bajo el cursor se "
            "queda bajo el cursor, desde cualquier ángulo.",
            "Después de jalar una cara, la pieza se redibuja de inmediato.",
            "Girado se ve el plano de trabajo, apenas insinuado, para saber dónde está el "
            "suelo. Textos y cotas todavía no se pintan girados; en planta sí.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado19")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    vista = shape / "ui" / "vista.js"
    # 1 · girada, pinta el visor
    parchar(vista, [
        ('  const oscuro = estado.modo === "papel" ? false : T.oscuro;\n  const esc = estado.vista.escala;',
         '  const oscuro = estado.modo === "papel" ? false : T.oscuro;\n'
         '  // Girada, pinta el visor nuevo: un solo espacio, sin los atajos de planta.\n'
         '  // En planta sigue todo lo de abajo, intacto, con sus cachés y sus pruebas.\n'
         '  if ((estado.vista.rx || estado.vista.rz) && typeof Visor !== "undefined") {\n'
         '    return Visor.pintarPlano(c, {\n'
         '      ancho: lienzo.clientWidth, alto: lienzo.clientHeight, fondo,\n'
         '      lienzoColor: T.lienzo, oscuro, escala: estado.vista.escala, trazos: estado.trazos,\n'
         '      borrador: !!(estado.prefs && estado.prefs.borrador), aPX,\n'
         '      colorDe: (hex) => colorDeTrazo(hex, oscuro),\n'
         '    });\n'
         '  }\n'
         '  const esc = estado.vista.escala;'),
    ], "Visor.pintarPlano(c, {", "ui/vista.js (girada pinta el visor)")
    # 3 · zoom en el espacio de la cámara
    parchar(vista, [
        ("""function zoomEn(px, py, factor) {
  const [mx, my] = aMM(px, py);
  estado.vista.escala = Math.min(500, Math.max(0.002, estado.vista.escala * factor));
  estado.vista.x = mx - px / estado.vista.escala;     // el punto bajo el cursor
  estado.vista.y = my + py / estado.vista.escala;     // se queda quieto""",
         """function zoomEn(px, py, factor) {
  // En el espacio de la cámara, no en el del plano: vista.x y vista.y viven
  // ahí. En planta son lo mismo; girado, mezclar los dos descentra el zoom
  // media pantalla en cada tic de la rueda.
  const v = estado.vista;
  const ux = px / v.escala + v.x, vy = v.y - py / v.escala;
  v.escala = Math.min(500, Math.max(0.002, v.escala * factor));
  v.x = ux - px / v.escala;                            // el punto bajo el cursor
  v.y = vy + py / v.escala;                            // se queda quieto"""),
    ], "const ux = px / v.escala + v.x, vy = v.y - py / v.escala;", "ui/vista.js (zoom en el espacio de la cámara)")

    # 2 · la órbita escucha los mismos eventos que el lienzo
    parchar(shape / "ui" / "camara.js", [
        ('"pointerdown"', '"mousedown"', 0),
        ('"pointermove"', '"mousemove"', 0),
        ('"pointerup"', '"mouseup"', 0),
    ], '"mousedown"', "ui/camara.js (mismos eventos que el lienzo)")

    # 4 · cuando una pieza cambia, el plano se invalida
    parchar(shape / "ui" / "cuerpos.js", [
        ("if (window.pintar) window.pintar();",
         "if (window.invalidarPlano) window.invalidarPlano();\n    if (window.pintar) window.pintar();", 0),
    ], "window.invalidarPlano", "ui/cuerpos.js (la pieza cambió: se invalida el plano)")

    # la pantalla carga el visor
    parchar(shape / "ui" / "index.html", [
        ('<script src="camara.js"></script>', '<script src="camara.js"></script>\n<script src="visor.js"></script>'),
    ], "visor.js", "ui/index.html (carga el visor)")

    # la versión
    hoy = dt.date.today().isoformat()
    ver = shape / "core" / "version.py"
    t = ver.read_text(encoding="utf-8")
    actual = re.search(r'VERSION = "([^"]+)"', t).group(1)
    if actual != VERSION:
        t = cambiar(t, f'VERSION = "{actual}"', f'VERSION = "{VERSION}"', "version.py")
        t = re.sub(r'FECHA = "[^"]+"', f'FECHA = "{hoy}"', t, count=1)
        ver.write_text(cambiar(t, "BITACORA: list[dict] = [\n", BITACORA % (VERSION, hoy), "version.py"),
                       encoding="utf-8")
        paq = shape / "package.json"
        t = paq.read_text(encoding="utf-8")
        t = cambiar(t, f'"version": "{actual}"', f'"version": "{VERSION}"', "package.json")
        t = cambiar(t, f'"_versionApp": "{actual} —', f'"_versionApp": "{VERSION} —', "package.json")
        paq.write_text(cambiar(t, f'"artifactName": "shape101-{actual}-setup.${{ext}}"',
                               f'"artifactName": "shape101-{VERSION}-setup.${{ext}}"', "package.json"),
                       encoding="utf-8")
        anotar(f"versión {actual} → {VERSION}")

    for js in ("vista.js", "camara.js", "cuerpos.js", "visor.js"):
        correr(["node", "--check", str(shape / "ui" / js)])
    anotar("los cuatro archivos tocados pasan node --check")
    if "pointerdown" in (shape / "ui" / "camara.js").read_text(encoding="utf-8"):
        raise RuntimeError("camara.js sigue escuchando pointer")
    anotar("la órbita escucha mouse, como el lienzo")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, el visor toma el mando girado\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: el visor toma el mando cuando la cámara está girada\n\n"
            "Lo que Mike vio en 0.6.1: líneas que se quedaban en 2D (se giró el bucle de\n"
            "los rellenos y no el de las líneas), órbita que se peleaba con el pan (eventos\n"
            "pointer contra mouse), zoom descentrado girado (coordenadas del plano mezcladas\n"
            "con las de la cámara) y piezas que no se redibujaban (la caché del plano no\n"
            "sabía que cambiaron).\n\n"
            "Girada, pinta el visor nuevo: un solo espacio, sin lotes ni foto ni recorte.\n"
            "En planta sigue el pintado de siempre, intacto, con sus 470 comprobaciones."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado19/shape101")
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
