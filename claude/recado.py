"""El mandadero · recado 7: enganchar el 3D a la pantalla y subir a 0.4.0.

Tres cosas chicas en archivos que no caben por el conector:

1. `ui/index.html` carga `tresd.js`. Va **después de `app.js`** a propósito:
   el 3D se registra como comando y usa lo que el resto ya montó.
2. `core/version.py` y `package.json` suben a **0.4.0**, con la bitácora en el
   idioma del taller. Si los dos no dicen lo mismo, el flujo de armado se niega
   a publicar —a propósito—, así que se cambian juntos.
3. Se comprueba, antes de empujar, que `ui/index.html` no haya quedado con el
   script repetido si el recado se corre dos veces.

Ojo con los finales de línea: los archivos de `ui/` vienen de draw101 con CRLF.
Si se les mete una línea con LF suelto, git marca el archivo entero como
cambiado y la siguiente comparación con draw101 se vuelve ilegible. Por eso
aquí se detecta el final de línea del archivo y se respeta.
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
RAMA = "claude/el-3d-en-la-pantalla"
VERSION = "0.4.0"

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
        raise RuntimeError(f"{donde}: «{viejo[:50]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo, 1)


BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "Empieza el 3D. Dibuja un contorno cerrado como siempre, selecciónalo y teclea "
            "EXTRUIR: se levanta y se vuelve una pieza sólida de verdad, con su espesor.",
            "La vista pasa a 3D sola. Arrastrando en el vacío se gira la pieza y la rueda "
            "acerca. Un clic señala una cara —se pone amarilla— y arrastrarla la jala: la "
            "pieza se rehace, no se estira. La medida se toma sobre la dirección a la que la "
            "cara apunta, así que jalar se siente igual mires desde donde mires.",
            "Los vértices del contorno salen como puntos azules. Al mover uno, la pieza "
            "entera se reconstruye y conserva lo que hayas hecho después: un barreno sigue "
            "siendo redondo y una cara jalada sigue jalada.",
            "La pieza se guarda dentro del .101s como cómo se hizo, no como una malla, y sale "
            "en STEP para abrirla en otro CAD o en STL para imprimirla.",
            "Escape vuelve al dibujo; el comando 3D regresa. Esta es la primera versión del "
            "gesto: todavía no hay ejes de arrastre, ni ajuste a rejilla, ni deshacer dentro "
            "del 3D.",
            "El instalador pesa bastante más: el motor de sólidos (OpenCascade) son unos "
            "200 MB. Es el precio de que las piezas sean exactas y se puedan exportar.",
        ],
    },
'''


def arreglar_version(texto: str) -> str:
    hoy = dt.date.today().isoformat()
    texto = cambiar(texto, 'VERSION = "0.3.0"', f'VERSION = "{VERSION}"', "version.py")
    texto, n = re.subn(r'FECHA = "[^"]+"', f'FECHA = "{hoy}"', texto, count=1)
    if n != 1:
        raise RuntimeError("version.py: no encontré FECHA")
    return cambiar(texto, "BITACORA: list[dict] = [\n", BITACORA % (VERSION, hoy), "version.py (bitácora)")


def arreglar_paquete(texto: str) -> str:
    d = "package.json"
    texto = cambiar(texto, '"version": "0.3.0"', f'"version": "{VERSION}"', d)
    texto = cambiar(texto, '"_versionApp": "0.3.0 —', f'"_versionApp": "{VERSION} —', d)
    return cambiar(texto, '"artifactName": "shape101-0.3.0-setup.${ext}"',
                   f'"artifactName": "shape101-{VERSION}-setup.${{ext}}"', d)


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado7")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    # 1 · la pantalla carga el 3D
    idx = shape / "ui" / "index.html"
    texto = idx.read_text(encoding="utf-8")
    if "tresd.js" in texto:
        anotar("ui/index.html ya cargaba tresd.js: no se toca")
    else:
        fin = "\r\n" if "\r\n" in texto else "\n"
        ancla = '<script src="app.js"></script>'
        texto = cambiar(texto, ancla, ancla + fin + '<script src="tresd.js"></script>', "index.html")
        idx.write_text(texto, encoding="utf-8", newline="")
        anotar(f"ui/index.html: carga tresd.js después de app.js (finales de línea {'CRLF' if fin == chr(13) + chr(10) else 'LF'})")

    # 2 · la versión, en los dos sitios a la vez
    ver = shape / "core" / "version.py"
    ver.write_text(arreglar_version(ver.read_text(encoding="utf-8")), encoding="utf-8")
    paq = shape / "package.json"
    paq.write_text(arreglar_paquete(paq.read_text(encoding="utf-8")), encoding="utf-8")
    anotar(f"core/version.py y package.json dicen los dos {VERSION}")

    # 3 · comprobar antes de empujar
    texto = idx.read_text(encoding="utf-8")
    if texto.count("tresd.js") != 1:
        raise RuntimeError(f"index.html quedó con tresd.js {texto.count('tresd.js')} veces")
    for archivo, debe in ((ver, f'"{VERSION}"'), (paq, f'"version": "{VERSION}"')):
        if debe not in archivo.read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo.name} no quedó en {VERSION}")
    salida = correr([sys.executable, "-c",
                     "import os, sys, tempfile; os.environ['HOME']=tempfile.mkdtemp();"
                     "sys.path.insert(0, '.');"
                     "from core.version import VERSION, BITACORA;"
                     "print('el programa dice versión', VERSION, 'con', len(BITACORA), 'entradas de bitácora')"],
                    cwd=shape)
    for l in salida.strip().splitlines():
        anotar(l)

    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: enganchar el 3D a la pantalla y subir a {VERSION}\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"El 3D en la pantalla y la versión {VERSION}\n\n"
            "index.html carga tresd.js después de app.js, y version.py y package.json suben\n"
            "juntos: si no coinciden, el flujo de armado se niega a publicar, que es lo que\n"
            "queremos.\n\n"
            "Se respeta el final de línea del archivo. Los de ui/ vienen de draw101 con CRLF,\n"
            "y meterles una línea con LF suelto marca el archivo entero como cambiado y deja\n"
            "ilegible cualquier comparación futura con draw101."],
           cwd=shape)
    correr(["git", "push", "-f", "origin", RAMA], cwd=shape)
    correr(["git", "push", "origin", f"{RAMA}:main"], cwd=shape)
    anotar(f"empujada {RAMA} y llevada a main")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado7/shape101")
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
