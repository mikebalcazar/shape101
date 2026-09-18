"""El mandadero · recado 22: 0.8.2 — las unidades, en serio.

La captura de Mike (18-sep): «Rectangle of 222 × 230 cm … pieza de 222 × 230 ×
50 mm · 2553 cm³». El dibujo estaba en centímetros —la unidad con que arranca
draw101, heredada en el trasplante— y el kernel trabaja en milímetros y toma
los números tal cual. Una pieza de 2.22 m queda como una de 222 mm. En pantalla
no se nota, porque dibujo y pieza usan los mismos números; se nota en el
volumen (mil veces menos) y en el STEP, que abre en otro CAD diez veces más
chico. Ese error se ve ya cortado.

1. shape101 arranca en **milímetros con centésimas**: lo decidió Mike el primer
   día. El programa mostraba cm por herencia.
2. Si un dibujo está en cm o m, el motor lo sabe: el volumen se corrige y el
   STEP y el STL salen a tamaño real. En pantalla no cambia nada: la pieza se
   sigue pintando con los números del dibujo, encima de su contorno.
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
RAMA = "claude/unidades-en-serio"
VERSION = "0.8.2"
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


FACTOR = '''def _factor_mm() -> float:
    """Milímetros por unidad del dibujo. El kernel trabaja en mm y toma los
    números tal cual; si el dibujo está en cm, todo lo que salga del kernel
    hacia fuera —volumen, STEP, STL— se corrige con esto. Lo que se pinta no:
    la pantalla usa los números del dibujo y la pieza va encima de su contorno."""
    from core.unidades import MM_POR_NOMBRE
    return float(MM_POR_NOMBRE.get(getattr(_doc(), "unidades", "mm"), 1.0))


def _malla(cuerpo):
    from core.solido import cuerpo as mod
    try:
        m = mod.malla(cuerpo)
    except Exception as e:
        # El kernel habla en inglés y con nombres de clase. Aquí se contesta en
        # el idioma del taller, y el cuerpo se queda como estaba.
        raise HTTPException(400, f"no se pudo construir la pieza: {e}") from e
    f = _factor_mm()
    if f != 1.0 and "volumen_mm3" in m:
        m["volumen_mm3"] = round(m["volumen_mm3"] * f ** 3, 1)
    m["unidades"] = getattr(_doc(), "unidades", "mm")
    return m'''

MALLA_VIEJA = '''def _malla(cuerpo):
    from core.solido import cuerpo as mod
    try:
        return mod.malla(cuerpo)
    except Exception as e:
        # El kernel habla en inglés y con nombres de clase. Aquí se contesta en
        # el idioma del taller, y el cuerpo se queda como estaba.
        raise HTTPException(400, f"no se pudo construir la pieza: {e}") from e'''

EXPORT_VIEJO = '''    formato = entrada.formato.lower()
    if formato == "step":
        export_step(reg.solido, str(destino))
    elif formato == "stl":
        export_stl(reg.solido, str(destino))'''

EXPORT_NUEVO = '''    formato = entrada.formato.lower()
    # A tamaño real: si el dibujo está en cm, la pieza sale diez veces más
    # grande que los números del kernel, que es lo que mide de verdad.
    f = _factor_mm()
    solido = reg.solido.scale(f) if f != 1.0 else reg.solido
    if formato == "step":
        export_step(solido, str(destino))
    elif formato == "stl":
        export_stl(solido, str(destino))'''

BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "Los dibujos nuevos arrancan en milímetros con centésimas, como se decidió el "
            "primer día. Hasta ahora arrancaban en centímetros, heredados de draw101.",
            "Si un dibujo está en centímetros o metros, el motor lo sabe: el volumen sale "
            "bien y el STEP y el STL a tamaño real. Antes una pieza dibujada en cm se "
            "exportaba diez veces más chica, y ese error se ve ya cortado.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado22")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    parchar(shape / "core" / "config.py", [('UNIDADES_OMISION = "cm"', 'UNIDADES_OMISION = "mm"')],
            'UNIDADES_OMISION = "mm"', "core/config.py (arranca en milímetros)")
    parchar(shape / "core" / "unidades.py", [
        ('DECIMALES_POR_NOMBRE = {"mm": 0, "cm": 1, "m": 3}', 'DECIMALES_POR_NOMBRE = {"mm": 2, "cm": 1, "m": 3}'),
    ], '{"mm": 2, "cm": 1, "m": 3}', "core/unidades.py (mm con centésimas)")
    parchar(shape / "core" / "solido" / "rutas.py", [
        (MALLA_VIEJA, FACTOR),
        (EXPORT_VIEJO, EXPORT_NUEVO),
    ], "_factor_mm", "core/solido/rutas.py (volumen y STEP a tamaño real)")
    parchar(shape / "ui" / "tresd.js", [
        ('mensaje: "Espesor en mm"', 'mensaje: "Espesor (en las unidades del dibujo)"'),
    ], "unidades del dibujo", "ui/tresd.js (el espesor va en la unidad del dibujo)")

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

    correr(["node", "--check", str(shape / "ui" / "tresd.js")])
    correr([sys.executable, "-c",
            "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('core/config.py', 'core/unidades.py', 'core/solido/rutas.py')]"],
           cwd=shape)
    anotar("los tres archivos de Python siguen válidos; tresd.js pasa node --check")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, las unidades en serio\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: las unidades en serio\n\n"
            "La captura de Mike lo enseñó: el dibujo en centímetros, la pieza en milímetros\n"
            "con los mismos números. En pantalla no se nota; en el volumen y en el STEP sí,\n"
            "y ese error se ve ya cortado.\n\n"
            "Los dibujos nuevos arrancan en mm con centésimas, como se decidió el primer día.\n"
            "Si un dibujo está en cm o m, el volumen se corrige y el STEP y el STL salen a\n"
            "tamaño real; lo que se pinta no cambia."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado22/shape101")
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
