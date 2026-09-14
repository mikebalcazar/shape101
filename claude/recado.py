"""El mandadero · lo que el chat de shape101 no alcanza a hacer con sus manos.

Este archivo lo corre `.github/workflows/recado.yml` cada vez que aparece una
rama `claude/recado-*`. Existe porque el conector de GitHub del chat no puede
escribir en `.github/workflows/` (403, medido) ni mover cientos de archivos de
un repositorio a otro sin pasarlos uno por uno por la ventana del chat.

**Recado de hoy: el trasplante.** shape101 vuelve a nacer desde la fuente de
draw101 0.20.4 (decisión de Mike, 13-sep-2026). De aquí en adelante son dos
programas distintos con un antepasado común: no se fusionan, no comparten
código, y lo que draw101 arregle no llega solo.

Lo que hace, en orden:

1. Clona draw101 (sólo lectura, `TOKEN_DRAW101`) y shape101 (`TOKEN_SHAPE101`).
2. En shape101 borra `app/` —la app desechada, que sigue en el historial— y
   **no toca `poc/`**, donde están las mediciones del kernel y de los nombres
   de caras, que valen igual para el camino nuevo.
3. Copia el código de draw101 y le cambia la identidad: nombre, `APP_ID`,
   extensión **`.101s`** y carpeta de usuario propia. `APP_NOMBRES_VIEJOS`
   queda **vacío** a propósito: si shape101 heredara la carpeta de draw101,
   un día un programa le pisaría el trabajo al otro y nadie entendería por qué.
4. Deja el resultado en la rama `claude/trasplante-draw101` y escribe lo que
   hizo en `claude/ultimo-recado.md`, **dentro de la misma rama**: es el canal
   de vuelta. El chat no alcanza el log de Actions, pero sí lee el repositorio.

No publica nada y no toca `main`. Eso lo decide el chat después de leer el
recado y revisar la rama.
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
RAMA = "claude/trasplante-draw101"
VERSION_NUEVA = "0.3.0"

# Lo que NO se copia de draw101: su historia de git, sus flujos, su contrato de
# trabajo (shape101 tiene el suyo) y lo que se rehace al armar.
NO_COPIAR = {".git", ".github", "claude", "OPERAR.md", "CLAUDE.md", "node_modules",
             "runtime", "dist", "__pycache__", ".venv", "venv", "salida"}

lineas: list[str] = []


def anotar(texto: str) -> None:
    print(texto, flush=True)
    lineas.append(texto)


def _sin_secretos(texto: str) -> str:
    """Un token nunca sale de aquí, ni en un error. Actions también los tapa,
    pero esto se escribe además en el repositorio: se tapa dos veces."""
    for nombre in ("TOKEN_DRAW101", "TOKEN_SHAPE101"):
        valor = os.environ.get(nombre)
        if valor:
            texto = texto.replace(valor, "***")
    return texto


def correr(orden: list[str], cwd=None) -> str:
    hecho = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if hecho.returncode != 0:
        # Nunca se imprime la orden completa: lleva el token adentro.
        raise RuntimeError(_sin_secretos(f"falló {orden[0]} {orden[1] if len(orden) > 1 else ''}: "
                                         f"{hecho.stderr.strip()[-800:]}"))
    return hecho.stdout


# --------------------------------------------------------------- renombrar
def renombrar(texto: str) -> tuple[str, int]:
    """draw101 → shape101, conservando cómo está escrito.

    No se tocan `t101draw` ni `DIBUJADOR`: son los nombres viejos de draw101 y
    aparecen en comentarios que cuentan su historia. Borrarlos no haría más
    cierto el texto, lo haría más confuso.
    """
    n = 0
    for viejo, nuevo in (("draw101", "shape101"), ("DRAW101", "SHAPE101"), ("Draw101", "Shape101")):
        n += texto.count(viejo)
        texto = texto.replace(viejo, nuevo)
    return texto, n


BINARIOS = {".png", ".jpg", ".jpeg", ".ico", ".gif", ".woff", ".woff2", ".ttf",
            ".otf", ".pdf", ".zip", ".exe", ".dll", ".so", ".t101d", ".101s"}


def es_texto(ruta: pathlib.Path) -> bool:
    if ruta.suffix.lower() in BINARIOS:
        return False
    try:
        ruta.read_text(encoding="utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


# --------------------------------------------------------------- identidad
CAMBIOS_CONFIG = [
    ('APP_NOMBRE = "shape101"',                      # ya renombrado por renombrar()
     'APP_NOMBRE = "shape101"'),
    ('APP_NOMBRES_VIEJOS = ("t101draw", "DIBUJADOR")',
     'APP_NOMBRES_VIEJOS = ()          # shape101 no hereda la carpeta de nadie: es otro programa'),
    ('APP_NOMBRE_VIEJO = APP_NOMBRES_VIEJOS[-1]',
     'APP_NOMBRE_VIEJO = ""'),
    ('APP_ID = "mx.taller101.dibujador"',
     'APP_ID = "mx.taller101.shape101"'),
    ('EXT_PROYECTO = ".t101d"',
     'EXT_PROYECTO = ".101s"'),
]


def arreglar_config(texto: str) -> str:
    for viejo, nuevo in CAMBIOS_CONFIG:
        if viejo == nuevo:
            if viejo not in texto:
                raise RuntimeError(f"config.py: no encontré «{viejo}»")
            continue
        if texto.count(viejo) != 1:
            raise RuntimeError(f"config.py: «{viejo}» aparece {texto.count(viejo)} veces, esperaba 1")
        texto = texto.replace(viejo, nuevo)
    return texto


BITACORA_NUEVA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "shape101 vuelve a nacer, ahora desde la fuente de draw101 0.20.4. Trae todo lo "
            "que draw101 sabe hacer en 2D; el modelado 3D empieza en la siguiente entrega.",
            "Sus archivos son .101s y sus preferencias, bloques y autoguardado viven en su "
            "propia carpeta: draw101 y shape101 son dos programas distintos que comparten un "
            "abuelo. Ninguno le pisa el trabajo al otro.",
            "La numeración arranca en %s porque las versiones 0.1.0 y 0.2.0 de shape101 ya se "
            "publicaron con otro contenido, y un número repetido con contenido distinto es "
            "justo lo que no se debe hacer.",
        ],
    },
]
'''


def arreglar_version(texto: str) -> str:
    hoy = dt.date.today().isoformat()
    texto, n = re.subn(r'VERSION = "[^"]+"', f'VERSION = "{VERSION_NUEVA}"', texto, count=1)
    if n != 1:
        raise RuntimeError("version.py: no encontré VERSION")
    texto, n = re.subn(r'FECHA = "[^"]+"', f'FECHA = "{hoy}"', texto, count=1)
    if n != 1:
        raise RuntimeError("version.py: no encontré FECHA")
    nueva = BITACORA_NUEVA % (VERSION_NUEVA, hoy, VERSION_NUEVA)
    texto, n = re.subn(r"BITACORA: list\[dict\] = \[.*?\n\]\n", nueva, texto, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError("version.py: no encontré la BITACORA completa")
    return texto


# ------------------------------------------------------------------ recado
def main() -> int:
    t_draw = os.environ.get("TOKEN_DRAW101")
    t_shape = os.environ.get("TOKEN_SHAPE101")
    faltan = [n for n, v in (("TOKEN_DRAW101", t_draw), ("TOKEN_SHAPE101", t_shape)) if not v]
    if faltan:
        print("faltan los secretos: " + ", ".join(faltan))
        return 1

    tmp = pathlib.Path("/tmp/recado")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    draw, shape = tmp / "draw101", tmp / "shape101"

    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_draw}@github.com/{DUENO}/draw101", str(draw)])
    correr(["git", "clone",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    sha_draw = correr(["git", "rev-parse", "HEAD"], cwd=draw).strip()
    anotar(f"draw101 clonado en {sha_draw}")
    version_draw = re.search(r'VERSION = "([^"]+)"', (draw / "core" / "version.py").read_text(encoding="utf-8")).group(1)
    anotar(f"draw101 dice versión {version_draw}")

    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    # 1 · fuera la app desechada; poc/ no se toca
    if (shape / "app").is_dir():
        shutil.rmtree(shape / "app")
        anotar("borrado app/ (la app desechada; sigue en el historial de git)")
    anotar("poc/ intacto" if (shape / "poc").is_dir() else "AVISO: no hay poc/")

    # 2 · copiar el código de draw101
    copiados = 0
    for origen in sorted(draw.iterdir()):
        if origen.name in NO_COPIAR:
            continue
        destino = shape / origen.name
        if destino.exists():
            shutil.rmtree(destino) if destino.is_dir() else destino.unlink()
        if origen.is_dir():
            shutil.copytree(origen, destino, ignore=shutil.ignore_patterns(*NO_COPIAR))
            copiados += sum(1 for _ in destino.rglob("*") if _.is_file())
        else:
            shutil.copy2(origen, destino)
            copiados += 1
        anotar(f"copiado {origen.name}")
    anotar(f"{copiados} archivos copiados de draw101")

    # 3 · renombrar en todo lo que sea texto, menos poc/ y claude/
    tocados, menciones = 0, 0
    for ruta in sorted(shape.rglob("*")):
        if not ruta.is_file():
            continue
        partes = ruta.relative_to(shape).parts
        if partes[0] in (".git", "poc", "claude", ".github"):
            continue
        if not es_texto(ruta):
            continue
        texto = ruta.read_text(encoding="utf-8")
        nuevo, n = renombrar(texto)
        if n:
            ruta.write_text(nuevo, encoding="utf-8")
            tocados += 1
            menciones += n
    anotar(f"«draw101» → «shape101» en {tocados} archivos ({menciones} menciones)")

    # 4 · identidad y versión
    cfg = shape / "core" / "config.py"
    cfg.write_text(arreglar_config(cfg.read_text(encoding="utf-8")), encoding="utf-8")
    anotar("core/config.py: APP_NOMBRE, APP_NOMBRES_VIEJOS vacío, APP_ID y EXT_PROYECTO = .101s")
    ver = shape / "core" / "version.py"
    ver.write_text(arreglar_version(ver.read_text(encoding="utf-8")), encoding="utf-8")
    anotar(f"core/version.py: versión {VERSION_NUEVA}, bitácora arrancada de cero")

    # 5 · lo que quedó diciendo draw101, para que el chat lo revise a mano
    quedan = []
    for ruta in sorted(shape.rglob("*")):
        if not ruta.is_file():
            continue
        partes = ruta.relative_to(shape).parts
        if partes[0] in (".git", "poc", "claude", ".github"):
            continue
        if es_texto(ruta) and "draw101" in ruta.read_text(encoding="utf-8").lower():
            quedan.append(str(ruta.relative_to(shape)))
    anotar(f"archivos que todavía dicen draw101 (para revisar a mano): {len(quedan)}")
    for q in quedan:
        anotar(f"  · {q}")

    # 6 · comprobaciones antes de empujar
    for ruta, debe in ((cfg, '.101s'), (ver, f'"{VERSION_NUEVA}"')):
        if debe not in ruta.read_text(encoding="utf-8"):
            raise RuntimeError(f"{ruta.name} no quedó con {debe}")
    sueltas = [str(r.relative_to(shape)) for r in shape.rglob("*")
               if r.is_file() and r.suffix == ".py" and es_texto(r)
               and ".s101" in r.read_text(encoding="utf-8")
               and r.relative_to(shape).parts[0] not in ("poc", "claude", ".git")]
    anotar(f"archivos que dicen «.s101» al revés (deberían ser .101s): {len(sueltas)} {sueltas}")

    # 7 · el recado de vuelta, dentro de la misma rama
    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions. Es el canal de\n"
        "vuelta: el chat no alcanza el log, pero sí lee el repositorio.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- draw101: {sha_draw} (versión {version_draw})\n\n```\n" + "\n".join(lineas) + "\n```\n",
        encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "shape101 vuelve a nacer desde draw101 " + version_draw + "\n\n"
            "Mike desechó la app aparte con motor propio: shape101 arranca ahora de la fuente\n"
            "de draw101 y de aquí en adelante son dos programas distintos con un antepasado\n"
            "común —no se fusionan ni comparten código—. Cambia la identidad (nombre, APP_ID,\n"
            "extensión .101s, y carpeta de usuario propia sin heredar la de draw101) y la\n"
            "versión arranca en " + VERSION_NUEVA + ", porque 0.1.0 y 0.2.0 ya se publicaron con otro\n"
            "contenido. Se borra app/ y se conserva poc/, donde están las mediciones del\n"
            "kernel y de los nombres de caras.\n\n"
            "Lo hizo claude/recado.py en Actions, porque el conector del chat no puede mover\n"
            "cientos de archivos entre repositorios. Lo medido queda en claude/ultimo-recado.md."],
           cwd=shape)
    correr(["git", "push", "-f", "origin", RAMA], cwd=shape)
    anotar(f"empujada la rama {RAMA}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"el recado falló: {type(e).__name__}: {e}")
        sys.exit(1)
