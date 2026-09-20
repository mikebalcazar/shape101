"""El mandadero · recado 39: el armado que no se apoya en una URL a mano, y la 0.18.0.

El armado de la 0.17.0 murió en un minuto: el flujo llevaba escrita a mano la
URL del instalador del que hereda el Python empotrado, apuntando a la 0.13.0, y
la poda automática que metimos en esa misma versión se la había llevado. Dos
cosas nuestras que funcionan bien, juntas se rompían.

El flujo vive en `.github/workflows/`, donde el conector del chat no puede
escribir: por eso esto va por recado, que es justo para lo que existe.

**Los parches no viven dentro de este archivo.** Viven en
`claude/parches-0.18.0/`, cada uno en dos `.txt` —el ancla y el texto nuevo—, y
aquí sólo se leen y se ponen. Un archivo de texto no tiene nada que escapar, y
además se puede mirar en GitHub antes de que esto corra.

Cada parche se ensayó contra la copia de `main` bajada de GitHub y el resultado
salió **idéntico**, byte por byte, a los archivos con los que corrieron las 673
comprobaciones. Por eso ninguna ancla puede fallar.

Este recado **no crea la rama de publicación**: primero se lee el cuaderno, y
sólo entonces se dispara el armado.
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
VERSION = "0.18.0"
PARCHES = "claude/parches-0.18.0"

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
    """Todo lo comprobable sin Windows, antes de gastar un armado."""
    import py_compile
    for f in ("core/solido/nombres.py", "core/version.py",
              "pruebas/t025_tiradores.py"):
        py_compile.compile(str(shape / f), doraise=True)
    anotar("el Python tocado compila")

    for f in ("ui/tiradores.js", "ui/historial.js"):
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

    # El flujo de armado: que ya no lleve una URL escrita a mano, que siga
    # siendo YAML válido, y que el manifiesto de verdad dé una URL utilizable.
    # Si esto no se comprueba aquí, se comprueba gastando un armado entero.
    flujo = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    t = flujo.read_text(encoding="utf-8")
    if "INSTALADOR_ANTERIOR" in t:
        raise RuntimeError("el flujo todavía lleva la URL escrita a mano")
    if "MANIFIESTO" not in t:
        raise RuntimeError("el flujo no sabe de dónde leer el instalador anterior")
    correr([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
    import yaml
    datos = yaml.safe_load(t)
    if not datos.get("jobs"):
        raise RuntimeError("el flujo dejó de ser YAML válido")
    anotar("el flujo ya no lleva URL a mano y sigue siendo YAML válido")

    import re
    import urllib.request
    manifiesto = urllib.request.urlopen(
        "https://raw.githubusercontent.com/mikebalcazar/descargas/main/shape101.json",
        timeout=30).read().decode("utf-8")
    url = re.findall(r'https://github\.com/[^"]*-setup\.exe', manifiesto)
    if not url:
        raise RuntimeError("el manifiesto no trae ninguna URL de instalador")
    anotar("y el manifiesto de verdad da: " + url[0])


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado39")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    # Esta entrega no trae archivos nuevos: todo son retoques.

    aplicar(shape)
    revisar(shape)

    # Los parches ya están puestos en el código: dejarlos ahí sería una copia
    # de lo mismo esperando a desincronizarse.
    shutil.rmtree(shape / PARCHES)
    anotar("parches aplicados y retirados del repositorio")

    if not correr(["git", "status", "--porcelain"], cwd=shape).strip():
        anotar("no había nada que cambiar: main ya trae la 0.18.0")
        return 0

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: 39 · el armado que no se apoya en una URL a mano, y la 0.18.0\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "El armado deja de apoyarse en una URL a mano, y la 0.18.0\n\n"
            "El armado de la 0.17.0 murió en un minuto: el flujo llevaba escrita a mano la\n"
            "URL del instalador del que hereda el Python empotrado, apuntando a la 0.13.0,\n"
            "y la poda automática que metimos en esa misma versión se la había llevado.\n"
            "Dos cosas nuestras que funcionan bien, juntas se rompían.\n\n"
            "Cambiarle el número a la URL habría durado tres versiones. Ahora el flujo lee\n"
            "cuál es el instalador publicado de descargas/shape101.json, que ya es la única\n"
            "señal que cuenta para dar una versión por publicada: la poda y el armado dejan\n"
            "de poder contradecirse.\n\n"
            "La 0.17.0 no llegó a publicarse, así que su contenido sale en la 0.18.0, que\n"
            "añade elegir a mano las aristas que se redondean: Ctrl+clic sobre el círculo\n"
            "de en medio de una arista la elige y REDONDEAR usa ésas. Sin elegir ninguna\n"
            "sigue tomando las verticales, así que nada de lo de antes cambia. Ctrl y no un\n"
            "clic pelón porque el clic pelón ya significa jalar esa arista.\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    anotar("main actualizado · la rama de publicación se crea aparte, tras leer esto")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado39/shape101")
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
