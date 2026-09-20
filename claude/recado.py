"""El mandadero · recado 38: la 0.17.0, el nombrado de las caras partidas.

El rumbo llama al nombrado topológico *«el riesgo que gobierna todo»*. Se
midió sobre un tablero con una muesca y salieron dos defectos silenciosos: el
nombre base saltaba de un trozo al otro al cambiar una cota, y jalar un trozo
dejaba al otro sin nombre.

**Los parches no viven dentro de este archivo.** Viven en
`claude/parches-0.17.0/`, cada uno en dos `.txt` —el ancla y el texto nuevo—, y
aquí sólo se leen y se ponen. El recado 35 metió texto dentro de cadenas de
Python y sus `\\n` se escaparon dos veces: salieron barras literales en el
cuaderno y en el mensaje del commit. Desde el 37 **ni el ancla va en el JSON**:
un archivo de texto no tiene nada que escapar, y además se puede mirar en
GitHub antes de que esto corra.

Cada parche se ensayó contra la copia de `main` bajada de GitHub y el resultado
salió **idéntico**, byte por byte, a los archivos con los que corrieron las 662
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
VERSION = "0.17.0"
PARCHES = "claude/parches-0.17.0"

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
        arch, modo = p["archivo"], p["modo"]
        ancla = ((d / p["ancla_txt"]).read_text(encoding="utf-8")
                 if p.get("ancla_txt") else p.get("ancla", ""))
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
    for f in ("core/solido/nombres.py", "core/solido/cuerpo.py", "core/version.py",
              "pruebas/t028_nombrado_partido.py"):
        py_compile.compile(str(shape / f), doraise=True)
    anotar("el Python tocado compila")

    # Esta entrega no toca JavaScript: no hay nada que revisar ahí.

    paquete = json.loads((shape / "package.json").read_text(encoding="utf-8"))
    ver = (shape / "core" / "version.py").read_text(encoding="utf-8")
    if paquete["version"] != VERSION or f'VERSION = "{VERSION}"' not in ver:
        raise RuntimeError(f"la versión no dice {VERSION} en los dos sitios")
    if f'"version": "{VERSION}"' not in ver:
        raise RuntimeError("falta la entrada de la bitácora")
    if paquete["build"]["artifactName"] != f"shape101-{VERSION}-setup.${{ext}}":
        raise RuntimeError("artifactName no trae la versión nueva")
    anotar(f"la versión dice {VERSION} en los tres sitios y la bitácora la trae")

    nom = (shape / "core" / "solido" / "nombres.py").read_text(encoding="utf-8")
    if "_orden" not in nom or "disputados" not in nom:
        raise RuntimeError("el reparto por posición no quedó puesto en nombres.py")
    anotar("el reparto de caras partidas va por posición, no por cercanía")


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado38")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    for arch in ("pruebas/t028_nombrado_partido.py",):
        if not (shape / arch).is_file():
            raise RuntimeError(f"falta {arch}: primero van los archivos, luego el recado")
    anotar("la prueba del nombrado partido ya está en main")

    aplicar(shape)
    revisar(shape)

    # Los parches ya están puestos en el código: dejarlos ahí sería una copia
    # de lo mismo esperando a desincronizarse.
    shutil.rmtree(shape / PARCHES)
    anotar("parches aplicados y retirados del repositorio")

    if not correr(["git", "status", "--porcelain"], cwd=shape).strip():
        anotar("no había nada que cambiar: main ya trae la 0.17.0")
        return 0

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: 38 · la 0.17.0, el nombrado de las caras partidas\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "0.17.0: cuando una operación parte una cara en dos\n\n"
            "El rumbo llama al nombrado topológico «el riesgo que gobierna todo». Se midió\n"
            "sobre un tablero con una muesca y salieron dos defectos, los dos silenciosos.\n\n"
            "Uno: el nombre base saltaba de un trozo al otro al cambiar una cota. El trozo\n"
            "se elegía «el más cercano a la cara vieja», y la cara vieja era la entera,\n"
            "cuyo centro se mueve al estirar la pieza. Medido: lado[0] era el trozo\n"
            "izquierdo con 600 y 450 de ancho, y el derecho con 900 y 2000. Una cara jalada\n"
            "se iba al otro lado de la pieza sin que el programa dijera nada.\n\n"
            "Dos: jalar una cara ya partida dejaba a su hermana sin nombre, y con ella sin\n"
            "nombre sus aristas y sus vértices.\n\n"
            "Ahora los trozos se reparten por posición —el centro, eje por eje—, que no\n"
            "cambia de orden cuando la pieza se estira, y una cara desplazada por herencia\n"
            "se corre a un ~k en vez de perderse.\n\n"
            "t028 trae 36 comprobaciones. Contra el código de la 0.16.0 falla con 8\n"
            "errores: prueba el arreglo, no se prueba a sí misma.\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    anotar("main actualizado · la rama de publicación se crea aparte, tras leer esto")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado38/shape101")
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
