"""El mandadero · recado 37: la 0.16.0, el boceto con cotas que se teclean.

Mike, sobre la etapa B: *«hoy sólo se mueven los puntos con el ratón; que
cambiar el ancho a 900 sea teclear 900»*.

Un contorno no trae cotas escritas: trae puntos. Así que las cotas se sacan de
su caja, y teclear una estira el contorno hasta que la caja mida eso.

**Los parches no viven dentro de este archivo.** Viven en
`claude/parches-0.16.0/`, cada uno en dos `.txt` —el ancla y el texto nuevo—, y
aquí sólo se leen y se ponen. El recado 35 metió texto dentro de cadenas de
Python y sus `\\n` se escaparon dos veces: salieron barras literales en el
cuaderno y en el mensaje del commit. Desde el 37 **ni el ancla va en el JSON**:
un ancla de varias líneas obligaría a escaparla, y escapar a mano es justo lo
que rompió aquello. Un archivo de texto no tiene nada que escapar, y además se
puede mirar en GitHub antes de que esto corra.

Cada parche se ensayó contra la copia de `main` bajada de GitHub y el resultado
salió **idéntico**, byte por byte, a los archivos con los que corrieron las 626
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
VERSION = "0.16.0"
PARCHES = "claude/parches-0.16.0"

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
        # El ancla también puede venir en su propio archivo. Desde la 0.16.0 se
        # usa siempre así: un ancla de varias líneas metida en el JSON obliga a
        # escaparla, y escapar a mano es exactamente lo que rompió el recado 35.
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
    for f in ("core/solido/cuerpo.py", "core/solido/rutas.py", "core/version.py",
              "pruebas/t026_historial_pieza.py", "pruebas/t027_boceto_cotas.py"):
        py_compile.compile(str(shape / f), doraise=True)
    anotar("el Python tocado compila")

    for f in ("ui/historial.js", "ui/cotaspieza.js", "ui/vista.js"):
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
    if 'src="cotaspieza.js"' not in html or 'src="historial.js"' not in html:
        raise RuntimeError("el letrero de cotas no quedó enganchado en index.html")
    vista = (shape / "ui" / "vista.js").read_text(encoding="utf-8")
    if "CotasPieza.pintar" not in vista or "CotasPieza.abajo" not in vista:
        raise RuntimeError("el letrero de cotas no se pinta o no se pica")
    anotar("el letrero está enganchado: se carga, se pinta y se pica")


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado37")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    # Los dos archivos nuevos llegaron a main por el conector, comparados byte
    # por byte contra lo que se probó. Sin ellos, los parches no significan
    # nada.
    for arch in ("ui/cotaspieza.js", "pruebas/t027_boceto_cotas.py"):
        if not (shape / arch).is_file():
            raise RuntimeError(f"falta {arch}: primero van los archivos, luego el recado")
    anotar("el letrero de cotas y su prueba ya están en main")

    aplicar(shape)
    revisar(shape)

    # Los parches ya están puestos en el código: dejarlos ahí sería una copia
    # de lo mismo esperando a desincronizarse.
    shutil.rmtree(shape / PARCHES)
    anotar("parches aplicados y retirados del repositorio")

    if not correr(["git", "status", "--porcelain"], cwd=shape).strip():
        anotar("no había nada que cambiar: main ya trae la 0.16.0")
        return 0

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: 37 · la 0.16.0, el boceto con cotas que se teclean\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "0.16.0: el boceto con cotas, y las cotas de la pieza en pantalla\n\n"
            "Mike, sobre la etapa B: «hoy sólo se mueven los puntos con el ratón; que\n"
            "cambiar el ancho a 900 sea teclear 900».\n\n"
            "Un contorno no trae cotas escritas: trae puntos. Así que las cotas se sacan\n"
            "de su caja y teclear una estira el contorno hasta que la caja mida eso. El\n"
            "paso del historial se lee ahora «Rectángulo 600 × 400» y trae Ancho, Fondo y\n"
            "la esquina donde empieza.\n\n"
            "Estirar no se lleva lo que se hizo después, y el barreno sigue redondo: su\n"
            "centro está en milímetros de la pieza, no en fracciones de ella. En madera no\n"
            "hay barrenos ovalados.\n\n"
            "Y la pieza señalada enseña sus tres medidas encima, en píxeles para que se\n"
            "lean igual con cualquier zoom. Se pican: clic al número, tecleas la medida y\n"
            "la pieza se rehace, sin abrir el panel y sin comandos.\n\n"
            "Va también un defecto del panel del historial cazado por la prueba nueva: se\n"
            "saltaba una recarga si había otra petición en vuelo, así que señalar una\n"
            "pieza y cambiarle un número en seguida podía dejarlo enseñando los pasos de\n"
            "antes. Ahora las peticiones van en fila.\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    anotar("main actualizado · la rama de publicación se crea aparte, tras leer esto")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado37/shape101")
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
