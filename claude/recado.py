"""El mandadero · recado 14: 0.4.1 — EXTRUIR pregunta el espesor (segundo intento).

El recado 13 aplicó bien el parche y **se cayó en su propia comprobación**:
buscaba que no quedara ningún `window.prompt` en el archivo, y lo encontró en
el comentario nuevo que explica justamente que Electron no lo soporta. La
comprobación estaba mal escrita, no el arreglo.

Aquí se busca la **llamada** —`window.prompt(`, con paréntesis— y no la
palabra. Una comprobación que se dispara sola con su propia explicación no
comprueba nada: sólo estorba.

Lo que arregla, que es lo de fondo: en 0.4.0, EXTRUIR sin argumento se queda
muerto con «prompt() is not supported». Electron no tiene `window.prompt`. La
app ya tiene su forma de pedir una medida —`Entrada.pedirNumero`— que usa la
cajita de siempre, acepta coma o punto y recuerda el último valor.
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
RAMA = "claude/extruir-pide-espesor"
VERSION = "0.4.1"
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


def cambiar(texto: str, viejo: str, nuevo: str, donde: str) -> str:
    n = texto.count(viejo)
    if n != 1:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo, 1)


VIEJO_PROMPT = '''    if (!isFinite(mm)) {
      // `Comandos.pedir` sólo escribe el mensaje en la consola; no devuelve lo
      // tecleado. Para una medida hace falta una respuesta, así que se pregunta
      // aparte y se sugiere el espesor más común de taller.
      mm = parseFloat(window.prompt("Espesor en mm", "18") || "");
    }'''

NUEVO_PROMPT = '''    if (!isFinite(mm)) {
      // Electron no tiene la ventanita de preguntar del navegador: usarla deja
      // el comando muerto con un «prompt() is not supported». La app ya tiene
      // su forma de pedir una medida, con la cajita de siempre, que acepta coma
      // o punto y recuerda lo último que se tecleó.
      if (typeof Entrada === "undefined" || !Entrada.pedirNumero) {
        Comandos.eco("EXTRUIR necesita un espesor.", "malo");
        return;
      }
      mm = await Entrada.pedirNumero({ mensaje: "Espesor en mm", valor: 18, clave: "extruir-espesor" });
    }'''

BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "EXTRUIR ya pregunta el espesor como el resto del programa, con la cajita de "
            "siempre: acepta coma o punto y recuerda lo último que tecleaste. En 0.4.0 el "
            "comando se quedaba muerto sin preguntar nada.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado14")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    js = shape / "ui" / "tresd.js"
    texto = js.read_text(encoding="utf-8")
    if "Entrada.pedirNumero" in texto:
        anotar("ui/tresd.js ya pedía el espesor con la cajita: no se toca")
    else:
        js.write_text(cambiar(texto, VIEJO_PROMPT, NUEVO_PROMPT, "ui/tresd.js"), encoding="utf-8")
        anotar("ui/tresd.js: EXTRUIR pide el espesor con Entrada.pedirNumero")
    # La LLAMADA, no la palabra: el comentario que explica el problema nombra
    # window.prompt a propósito, y buscar la palabra suelta tumbó el intento
    # anterior con su propia explicación.
    quedan = js.read_text(encoding="utf-8").count("window.prompt(")
    if quedan:
        raise RuntimeError(f"todavía quedan {quedan} llamadas a window.prompt( en tresd.js")
    anotar("no queda ninguna llamada a window.prompt( en tresd.js")

    hoy = dt.date.today().isoformat()
    ver = shape / "core" / "version.py"
    t = ver.read_text(encoding="utf-8")
    t = cambiar(t, 'VERSION = "0.4.0"', f'VERSION = "{VERSION}"', "version.py")
    t, n = re.subn(r'FECHA = "[^"]+"', f'FECHA = "{hoy}"', t, count=1)
    if n != 1:
        raise RuntimeError("version.py: no encontré FECHA")
    ver.write_text(cambiar(t, "BITACORA: list[dict] = [\n", BITACORA % (VERSION, hoy),
                           "version.py (bitácora)"), encoding="utf-8")
    paq = shape / "package.json"
    t = paq.read_text(encoding="utf-8")
    t = cambiar(t, '"version": "0.4.0"', f'"version": "{VERSION}"', "package.json")
    t = cambiar(t, '"_versionApp": "0.4.0 —', f'"_versionApp": "{VERSION} —', "package.json")
    paq.write_text(cambiar(t, '"artifactName": "shape101-0.4.0-setup.${ext}"',
                           f'"artifactName": "shape101-{VERSION}-setup.${{ext}}"',
                           "package.json"), encoding="utf-8")
    anotar(f"core/version.py y package.json dicen los dos {VERSION}")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, EXTRUIR pide el espesor (segundo intento)\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: EXTRUIR pide el espesor con la cajita del programa\n\n"
            "Electron no tiene la ventanita de preguntar del navegador, así que en 0.4.0 el\n"
            "comando se quedaba muerto con un «prompt() is not supported». Lo encontró Mike\n"
            "al primer intento, en lo único que no se puede probar desde el chat: la\n"
            "pantalla.\n\n"
            "El intento anterior de este mismo arreglo se cayó en su propia comprobación:\n"
            "buscaba que no quedara ningún «window.prompt» y lo encontró en el comentario\n"
            "que explica por qué no se usa. Ahora se busca la llamada, con paréntesis. Una\n"
            "comprobación que se dispara con su propia explicación no comprueba nada."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado14/shape101")
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
