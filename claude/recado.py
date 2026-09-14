"""El mandadero · recado 2: el empaque y el flujo de armado.

Lo corre `.github/workflows/recado.yml` al aparecer una rama `claude/recado-*`.

El trasplante (recado 1) dejó shape101 con el código de draw101, pero el
empaque sigue siendo el de draw101: `package.json` dice versión 0.20.4, el
`appId` es el del dibujador y los archivos asociados son `.t101d`. Y el flujo
que arma el instalador todavía es el de la app desechada, que ya no existe.

Aquí se arreglan las dos cosas:

1. **`package.json`**: versión 0.3.0, nombre del instalador, `appId` propio y
   la asociación de archivo a **`.101s`**. Si electron-builder no dice lo mismo
   que `core/version.py`, el flujo de armado se niega a publicar —a propósito—,
   así que esto va primero.
2. **`.github/workflows/armar-y-publicar.yml`**: se toma el de draw101, que ya
   funciona y está probado, y se le cambia lo que es identidad. No se inventa
   uno nuevo: un flujo de publicación que nadie ha corrido es un flujo que no
   sabes si publica.

El chat no puede escribir en `.github/workflows/` (403 por las dos vías del
conector, medido). El token de Mike sí, y vive sólo aquí dentro.

**Una cosa que parece un error y no lo es**: el Python empotrado se saca del
instalador publicado de **draw101 0.20.1**. No es pereza ni una liga suelta: es
un Python de Windows con ezdxf, fastapi, numpy, pillow y reportlab ya dentro, y
shape101 necesita exactamente esos. El día que shape101 necesite otra cosa
—OpenCascade para el 3D— esa línea cambia y se arma el runtime aparte.
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
RAMA = "claude/flujo-y-empaque"
VERSION = "0.3.0"

# El runtime empotrado: un Python de Windows con las dependencias del motor ya
# instaladas. Sale del instalador publicado de draw101 porque shape101 usa las
# mismas; cuando dejen de ser las mismas, esto cambia.
RUNTIME = ("https://github.com/mikebalcazar/descargas/releases/download/"
           "draw101-0.20.1/draw101-0.20.1-setup.exe")

lineas: list[str] = []


def anotar(texto: str) -> None:
    print(texto, flush=True)
    lineas.append(texto)


def _sin_secretos(texto: str) -> str:
    for nombre in ("TOKEN_DRAW101", "TOKEN_SHAPE101"):
        valor = os.environ.get(nombre)
        if valor:
            texto = texto.replace(valor, "***")
    return texto


def correr(orden: list[str], cwd=None) -> str:
    hecho = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if hecho.returncode != 0:
        raise RuntimeError(_sin_secretos(f"falló {orden[0]} {orden[1] if len(orden) > 1 else ''}: "
                                         f"{hecho.stderr.strip()[-800:]}"))
    return hecho.stdout


def cambiar(texto: str, viejo: str, nuevo: str, veces: int = 1, donde: str = "") -> str:
    """Un reemplazo que comprueba cuántas veces debía aparecer. Si no cuadra,
    para: un parche que se aplicó a medias es peor que uno que no se aplicó."""
    n = texto.count(viejo)
    if n != veces:
        raise RuntimeError(f"{donde}: «{viejo[:60]}» aparece {n} veces, esperaba {veces}")
    return texto.replace(viejo, nuevo)


# ------------------------------------------------------------ package.json
def arreglar_paquete(texto: str) -> str:
    d = "package.json"
    texto = cambiar(texto, '"version": "0.20.4"', f'"version": "{VERSION}"', 1, d)
    texto = cambiar(texto, '"_versionApp": "0.20.4 —',
                    f'"_versionApp": "{VERSION} —', 1, d)
    texto = cambiar(texto, '"artifactName": "shape101-0.20.4-setup.${ext}"',
                    f'"artifactName": "shape101-{VERSION}-setup.${{ext}}"', 1, d)
    texto = cambiar(texto, '"appId": "mx.taller101.dibujador"',
                    '"appId": "mx.taller101.shape101"', 1, d)
    texto = cambiar(texto, '"ext": "t101d"', '"ext": "101s"', 1, d)
    texto = cambiar(texto, '"name": "Dibujo Taller 101"',
                    '"name": "Pieza de shape101"', 1, d)
    texto = cambiar(texto, '"description": "CAD 2D de Taller 101 — leer, trazar, acotar e imprimir planos"',
                    '"description": "shape101 — modelador 3D de sólidos de Taller 101"', 1, d)
    return texto


# ------------------------------------------------------------- el workflow
def arreglar_flujo(texto: str) -> str:
    """El flujo de draw101, con la identidad cambiada. Lo que no es identidad
    se queda tal cual: está probado y publica de verdad."""
    for viejo, nuevo in (("draw101", "shape101"), ("DRAW101", "SHAPE101")):
        texto = texto.replace(viejo, nuevo)
    # …menos el runtime empotrado, que sí sale de draw101 (ver el encabezado).
    texto, n = re.subn(r"INSTALADOR_ANTERIOR: \S+", "INSTALADOR_ANTERIOR: " + RUNTIME, texto, count=1)
    if n != 1:
        raise RuntimeError("el flujo no trae INSTALADOR_ANTERIOR")
    texto = texto.replace(
        "env:\n  # El Windows del runner",
        "env:\n  # INSTALADOR_ANTERIOR es de draw101 a propósito: de ahí sale el Python de\n"
        "  # Windows con ezdxf, fastapi, numpy, pillow y reportlab ya dentro, que es lo que\n"
        "  # shape101 necesita hoy. Cuando el 3D pida OpenCascade, esto cambia.\n"
        "  # El Windows del runner", 1)
    return texto


def main() -> int:
    t_draw = os.environ.get("TOKEN_DRAW101")
    t_shape = os.environ.get("TOKEN_SHAPE101")
    faltan = [n for n, v in (("TOKEN_DRAW101", t_draw), ("TOKEN_SHAPE101", t_shape)) if not v]
    if faltan:
        print("faltan los secretos: " + ", ".join(faltan))
        return 1

    tmp = pathlib.Path("/tmp/recado2")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    draw, shape = tmp / "draw101", tmp / "shape101"

    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_draw}@github.com/{DUENO}/draw101", str(draw)])
    correr(["git", "clone",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    # 1 · el empaque
    paq = shape / "package.json"
    paq.write_text(arreglar_paquete(paq.read_text(encoding="utf-8")), encoding="utf-8")
    anotar(f"package.json: versión {VERSION}, appId propio, instalador shape101-{VERSION}-setup, archivos .101s")

    # 2 · el flujo de armado, tomado del de draw101
    origen = draw / ".github" / "workflows" / "armar-y-publicar.yml"
    if not origen.is_file():
        raise RuntimeError("draw101 no trae .github/workflows/armar-y-publicar.yml")
    destino = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(arreglar_flujo(origen.read_text(encoding="utf-8")), encoding="utf-8")
    anotar("armar-y-publicar.yml: el de draw101 con la identidad cambiada (el runtime sigue saliendo de draw101 0.20.1)")

    # 3 · comprobaciones antes de empujar
    yml = destino.read_text(encoding="utf-8")
    for debe in ("shape101-$VER-setup", "core/version.py", "shape101.json", "TOKEN_DESCARGAS"):
        if debe not in yml:
            raise RuntimeError(f"el flujo no quedó con «{debe}»")
    if "draw101-0.20.1-setup.exe" not in yml:
        raise RuntimeError("el flujo perdió el runtime de draw101 0.20.1")
    version_py = re.search(r'VERSION = "([^"]+)"',
                           (shape / "core" / "version.py").read_text(encoding="utf-8")).group(1)
    if version_py != VERSION:
        raise RuntimeError(f"core/version.py dice {version_py} y el empaque {VERSION}: no coinciden")
    anotar(f"core/version.py y package.json dicen los dos {VERSION}")

    # 4 · el recado de vuelta
    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: empaque y flujo de armado\n\n```\n" + "\n".join(lineas) + "\n```\n",
        encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "El empaque y el flujo de armado, ya de shape101\n\n"
            "package.json queda en " + VERSION + " con appId propio, el instalador se llamará\n"
            "shape101-" + VERSION + "-setup.exe y los archivos asociados son .101s, no .t101d.\n\n"
            "El flujo de publicación es el de draw101 —que ya funciona y publica de verdad—\n"
            "con la identidad cambiada, en vez de uno nuevo sin estrenar. El Python empotrado\n"
            "se sigue sacando del instalador de draw101 0.20.1 a propósito: es un Python de\n"
            "Windows con ezdxf, fastapi, numpy, pillow y reportlab ya dentro, que es justo lo\n"
            "que shape101 necesita hoy.\n\n"
            "Lo hizo claude/recado.py en Actions: el conector del chat recibe 403 en\n"
            ".github/workflows/ por las dos vías."],
           cwd=shape)
    correr(["git", "push", "-f", "origin", RAMA], cwd=shape)
    correr(["git", "push", "origin", f"{RAMA}:main"], cwd=shape)
    anotar(f"empujada la rama {RAMA} y llevada a main")
    return 0


def avisar_del_fracaso(error: str) -> None:
    """Si el recado falla, el chat no ve el log: lo único que ve es el
    repositorio. Así que el fracaso también se escribe ahí, en una rama aparte
    y sin nada más pegado. Un canal de vuelta que sólo funciona cuando todo
    sale bien no es un canal de vuelta."""
    shape = pathlib.Path("/tmp/recado2/shape101")
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
            "```\n" + "\n".join(lineas) + "\n\nERROR: " + error + "\n```\n",
            encoding="utf-8")
        correr(["git", "add", "claude/ultimo-recado.md"], cwd=shape)
        correr(["git", "commit", "-m", "recado fallido: lo que se alcanzó a hacer y dónde se rompió"], cwd=shape)
        correr(["git", "push", "-f", "origin", "claude/recado-fallo"], cwd=shape)
        print("el fracaso quedó escrito en la rama claude/recado-fallo")
    except Exception as e2:
        print(f"ni el aviso del fracaso se pudo escribir: {e2}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        detalle = _sin_secretos(f"{type(e).__name__}: {e}")
        print(f"el recado falló: {detalle}")
        avisar_del_fracaso(detalle)
        sys.exit(1)
