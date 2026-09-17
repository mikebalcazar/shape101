"""El mandadero · recado 17 (relanzado): 0.6.1 — lo que Mike vio en la 0.6.0.

Los dos disparos anteriores se quedaron mudos porque GitHub exigía 2FA en la
cuenta y, mientras no estuviera puesto, detenía los trabajos en silencio. Mike
lo activó el 16-sep. Este es el mismo recado, sin cambios.

1. **Nadie repintaba.** La cámara, los cuerpos y el gesto pedían repintar por
   `Vista.pintar`, que **no existe**. Ahora `pintar` e `invalidarPlano` están
   expuestos y se usan.
2. **La llave del plano no sabía de la cámara.** Ahora incluye los ángulos.
3. **Las líneas se pintaban en planta siempre.** Con la cámara girada pasan
   por `aPX`; en planta sigue el camino rápido, intacto. Sin recorte por
   ventana girada y sin rejilla girada.
4. **El ciclo de pintado nunca muere.** Si un cuadro truena, se anota en
   consola, se pinta lo que se pudo y el programa sigue vivo.
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
RAMA = "claude/repintar-y-girar-las-lineas"
VERSION = "0.6.1"
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
        viejo, nuevo = c[0], c[1]
        veces = c[2] if len(c) > 2 else 1
        t = cambiar(t, viejo, nuevo, donde, veces)
    ruta.write_text(t, encoding="utf-8", newline="")
    anotar(f"{donde}: parchado")


BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "La pieza ya nace pegada al dibujo. En 0.6.0 las líneas del plano se seguían "
            "pintando desde arriba aunque la cámara girara, así que la pieza giraba sola y "
            "se veía despegada.",
            "Orbitar se ve en tiempo real y ya no brinca: la cámara pedía repintar por un "
            "nombre que no existía, y el cuadro llegaba tarde.",
            "Un error al pintar ya no deja el programa muerto: se anota, se pinta lo que se "
            "pudo y sigue vivo. Es lo que pasó en 0.6.0 al hacer zoom con la vista girada.",
            "Con la vista girada no se pinta la rejilla, que ahí no significa nada.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado17")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    vista = shape / "ui" / "vista.js"
    parchar(vista, [
        ("window.aPX = aPX;\nwindow.aMM = aMM;",
         "window.aPX = aPX;\nwindow.aMM = aMM;\n"
         "// Y el repintado, para la cámara, los cuerpos y el gesto del 3D. En 0.6.0\n"
         "// pedían repintar por un nombre que no existía y el cuadro llegaba tarde.\n"
         "window.pintar = pintar;\nwindow.invalidarPlano = invalidarPlano;"),
    ], "window.pintar = pintar;", "ui/vista.js (repintado expuesto)")
    parchar(vista, [
        ("  return `${v.x}|${v.y}|${v.escala}|${lienzo.width}|${lienzo.height}|`",
         "  return `${v.x}|${v.y}|${v.escala}|${v.rx || 0}|${v.rz || 0}|${lienzo.width}|${lienzo.height}|`"),
    ], "${v.rx || 0}|${v.rz || 0}", "ui/vista.js (la llave del plano)")
    parchar(vista, [
        ("""  const margen = 20 / esc;
  const mx0 = vx - margen, mx1 = vx + anchoPX / esc + margen;""",
         """  // Con la cámara girada la ventana en milímetros no dice la verdad: lo que en
  // planta queda fuera puede estar en pantalla. Se pinta todo, y las líneas
  // pasan por aPX en vez del camino rápido, que sólo sabe de planta.
  const girada = !!(estado.vista.rx || estado.vista.rz);
  const margen = girada ? 1e12 : 20 / esc;
  const mx0 = vx - margen, mx1 = vx + anchoPX / esc + margen;"""),
        ("    if ((bb[2] - bb[0]) * esc < MINIMO_PX && (bb[3] - bb[1]) * esc < MINIMO_PX) {",
         "    if (!girada && (bb[2] - bb[0]) * esc < MINIMO_PX && (bb[3] - bb[1]) * esc < MINIMO_PX) {"),
        ("""        const px = (pol[i][0] - vx) * esc, py = (vy - pol[i][1]) * esc;
        i === 0 ? c.moveTo(px, py) : c.lineTo(px, py);""",
         """        let px, py;
        if (girada) { const q = aPX(pol[i][0], pol[i][1], 0); px = q[0]; py = q[1]; }
        else { px = (pol[i][0] - vx) * esc; py = (vy - pol[i][1]) * esc; }
        i === 0 ? c.moveTo(px, py) : c.lineTo(px, py);"""),
        ("    pintarRejilla(c);",
         "    if (!(estado.vista.rx || estado.vista.rz)) pintarRejilla(c);   // girada no significa nada"),
    ], "const girada = !!(estado.vista.rx || estado.vista.rz);", "ui/vista.js (las líneas por la cámara)")
    parchar(vista, [
        ("function pintarYa() {",
         "function pintarYa() {\n"
         "  // Si un cuadro truena, se anota y el programa sigue vivo. En 0.6.0 un\n"
         "  // error de dibujo se repetía en cada cuadro y dejó a Mike sin programa.\n"
         "  try { _pintarYaCrudo(); }\n"
         "  catch (e) { console.error(\"[vista] el cuadro tronó, el programa sigue:\", e); }\n"
         "}\n"
         "function _pintarYaCrudo() {"),
    ], "_pintarYaCrudo", "ui/vista.js (el ciclo de pintado nunca muere)")

    for nombre in ("camara.js", "cuerpos.js", "tresd.js"):
        parchar(shape / "ui" / nombre, [
            ('if (typeof Vista !== "undefined" && Vista.pintar) Vista.pintar();',
             'if (window.pintar) window.pintar();', 0),
        ], "if (window.pintar) window.pintar();", f"ui/{nombre} (repintar de verdad)")

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

    for js in ("vista.js", "camara.js", "cuerpos.js", "tresd.js"):
        correr(["node", "--check", str(shape / "ui" / js)])
    anotar("los cuatro archivos tocados pasan node --check")
    if "Vista.pintar" in (shape / "ui" / "camara.js").read_text(encoding="utf-8"):
        raise RuntimeError("camara.js sigue pidiendo repintar por un nombre que no existe")
    anotar("ya nadie pide repintar por Vista.pintar")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, repintar, girar las líneas y no morir al pintar\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: la pieza nace pegada, la órbita se ve en tiempo real y un cuadro roto no mata el programa\n\n"
            "Mike vio en la 0.6.0 que la pieza no nacía pegada, que orbitar brincaba y que\n"
            "el programa se le murió al hacer zoom con la vista girada. Los dos primeros\n"
            "tenían causa común: se pedía repintar por Vista.pintar, que no existe, y el\n"
            "pintado por lotes multiplicaba por la escala sin pasar por la cámara.\n\n"
            "El tercero tiene la pinta de un error de dibujo repitiéndose en cada cuadro.\n"
            "Ahora el ciclo de pintado nunca muere: si un cuadro truena, se anota, se pinta\n"
            "lo que se pudo y el programa sigue vivo."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado17/shape101")
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
