"""El mandadero · recado 36: la 0.15.0, el historial de la pieza a la vista.

Mike (19-sep): *«la parametrización del modelo me interesa muchísimo. El
mantener algo de historial de cómo se generó un barreno… después se quiere
agrandar o achicar: sólo se podría incrementar o disminuir el diámetro del
cilindro original sin necesidad de trazarlo todo de nuevo»*.

El motor ya lo hacía: una pieza **es** su lista de operaciones y regenerar es
volver a correrlas. Lo que faltaba era enseñarlo y dejarlo tocar.

**Los parches no viven dentro de este archivo.** Viven en
`claude/parches-0.15.0/`, cada uno en su propio `.txt`, y aquí sólo se leen y
se ponen. El recado 35 metió texto dentro de cadenas de Python y sus `\\n` se
escaparon dos veces: salieron barras literales en el cuaderno y en el mensaje
del commit. Un archivo de texto no tiene nada que escapar, y además se puede
mirar en GitHub antes de que esto corra.

Cada parche se probó contra la copia de `main` bajada de GitHub y el resultado
salió **idéntico**, byte por byte, a los archivos con los que corrieron las 573
comprobaciones. Por eso ninguna ancla puede fallar.

Este recado **no crea la rama de publicación**: primero se lee el cuaderno, y
sólo entonces se dispara el armado de 45 minutos.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
VERSION = "0.15.0"
PARCHES = "claude/parches-0.15.0"

lineas: list[str] = []


def anotar(t: str) -> None:
    print(t, flush=True)
    lineas.append(t)


def _sin_secretos(t: str) -> str:
    v = os.environ.get("TOKEN_SHAPE101")
    return t.replace(v, "***") if v else t


def correr(orden, cwd=None) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if h.returncode != 0:
        raise RuntimeError(_sin_secretos(f"falló {orden[0]}: {h.stderr.strip()[-800:]}"))
    return h.stdout


def aplicar(raiz: pathlib.Path) -> None:
    """Pone cada parche donde dice el índice.

    Dos reglas, y las dos importan: el ancla tiene que aparecer **una sola
    vez** —si aparece cero o dos, se para, que es mucho mejor que dejar un
    archivo a medias— y si el parche ya está puesto no se pone dos veces, así
    repetir el recado es inofensivo.
    """
    d = raiz / PARCHES
    for p in json.loads((d / "indice.json").read_text(encoding="utf-8")):
        arch, modo, ancla = p["archivo"], p["modo"], p["ancla"]
        texto = (d / p["texto"]).read_text(encoding="utf-8")
        f = raiz / arch
        t = f.read_text(encoding="utf-8")
        if modo == "final":
            if t.endswith(texto):
                anotar(f"  {arch}: ya estaba"); continue
            t = t + texto
        elif modo == "antes":
            if texto in t:
                anotar(f"  {arch}: ya estaba"); continue
            if t.count(ancla) != 1:
                raise RuntimeError(f"{arch}: «{ancla[:50]}» aparece {t.count(ancla)} veces")
            t = t.replace(ancla, texto + ancla)
        elif modo == "cambiar":
            if texto in t:
                anotar(f"  {arch}: ya estaba"); continue
            if t.count(ancla) != 1:
                raise RuntimeError(f"{arch}: «{ancla[:50]}» aparece {t.count(ancla)} veces")
            t = t.replace(ancla, texto)
        elif modo == "todos":
            if ancla not in t:
                anotar(f"  {arch}: ya estaba"); continue
            t = t.replace(ancla, texto)
        else:
            raise RuntimeError(f"modo desconocido: {modo}")
        f.write_text(t, encoding="utf-8")
        anotar(f"  {arch}: {modo} · {p['texto']}")


def revisar(shape: pathlib.Path) -> None:
    """Todo lo comprobable sin Windows, antes de gastar 45 minutos."""
    import py_compile
    for f in ("core/solido/cuerpo.py", "core/solido/rutas.py", "core/version.py",
              "pruebas/t026_historial_pieza.py"):
        py_compile.compile(str(shape / f), doraise=True)
    anotar("el Python tocado compila")

    for f in ("ui/historial.js", "ui/cuerpos.js", "ui/app.js"):
        correr(["node", "--check", str(shape / f)])
    anotar("el JavaScript tocado pasa node --check")

    paquete = json.loads((shape / "package.json").read_text(encoding="utf-8"))
    ver = (shape / "core" / "version.py").read_text(encoding="utf-8")
    if paquete["version"] != VERSION or f'VERSION = "{VERSION}"' not in ver:
        raise RuntimeError(f"la versión no dice {VERSION} en los dos sitios")
    if f'"version": "{VERSION}"' not in ver:
        raise RuntimeError("falta la entrada de la bitácora")
    if paquete["build"]["artifactName"] != f"shape101-{VERSION}-setup.${{ext}}":
        raise RuntimeError("artifactName no trae la versión nueva")
    anotar(f"la versión dice {VERSION} en los tres sitios y la bitácora la trae")

    html = (shape / "ui" / "index.html").read_text(encoding="utf-8")
    if 'src="historial.js"' not in html or 'id="hist-pasos"' not in html:
        raise RuntimeError("el panel del historial no quedó enganchado en index.html")
    anotar("el panel está enganchado: script y hueco en su sitio")


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado36")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    # El panel y su prueba llegaron a main por el conector, comparados byte por
    # byte contra lo que se probó. Sin ellos, los parches no significan nada.
    for arch in ("ui/historial.js", "pruebas/t026_historial_pieza.py"):
        if not (shape / arch).is_file():
            raise RuntimeError(f"falta {arch}: primero van los archivos, luego el recado")
    anotar("el panel y su prueba ya están en main")

    aplicar(shape)
    revisar(shape)

    # Los parches ya están puestos en el código: dejarlos ahí sería una copia
    # de lo mismo esperando a desincronizarse.
    shutil.rmtree(shape / PARCHES)
    anotar("parches aplicados y retirados del repositorio")

    if not correr(["git", "status", "--porcelain"], cwd=shape).strip():
        anotar("no había nada que cambiar: main ya trae la 0.15.0")
        return 0

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: 36 · la 0.15.0, el historial de la pieza a la vista\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "0.15.0: el historial de la pieza, a la vista y editable\n\n"
            "Mike: «la parametrización del modelo me interesa muchísimo. El mantener algo\n"
            "de historial de cómo se generó un barreno… después se quiere agrandar o\n"
            "achicar: sólo se podría incrementar o disminuir el diámetro del cilindro\n"
            "original sin necesidad de trazarlo todo de nuevo».\n\n"
            "El motor ya lo hacía —una pieza es su lista de operaciones y regenerar es\n"
            "volver a correrlas—; lo que faltaba era enseñarlo. Al señalar una cara, el\n"
            "panel de la derecha dice con qué se hizo la pieza y deja tocar sus números.\n"
            "Cada cambio la rehace entera desde el contorno, así que un redondeo hecho\n"
            "encima de un barreno sigue puesto cuando el barreno cambia de diámetro, y\n"
            "sigue puesto si el barreno se borra del historial.\n\n"
            "Si un cambio deja la pieza imposible, el historial vuelve como estaba: el\n"
            "peor caso de tocar un número es que no pase nada, y por eso se puede tocar\n"
            "sin miedo.\n\n"
            "Van también BARRENO y REDONDEAR, que el motor ya sabía hacer y nadie podía\n"
            "llamar, y t026 con 42 comprobaciones, la pantalla incluida.\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    anotar("main actualizado · la rama de publicación se crea aparte, tras leer esto")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado36/shape101")
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
