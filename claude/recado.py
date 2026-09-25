"""El mandadero  ·  desde el recado 47 es genérico.

Lo que cambia de un recado a otro —qué parches, qué revisar, qué decir en el
commit— vive en `claude/recado.json`, y este archivo ya no se toca. Hasta el
recado 46 se copiaba entero en cada envío (unos 15 KB tecleados a mano), y de
los seis errores de copia que el ensayo atrapó, tres estaban aquí. Un archivo
que no viaja no se copia mal.

Cómo corre: Actions lo lanza cuando el chat crea una rama `claude/recado-NN`.
Clona main, aplica los parches de `recado.json` («parches»), revisa lo que ese
JSON dice («revisar»), retira la carpeta de parches y empuja a main con el
mensaje del JSON. Si algo falla, deja el aviso en `claude/recado-fallo`.

El JSON:

  {
    "numero": 47,
    "asunto": "una línea",
    "parches": "claude/parches-0.21.3",
    "version": "0.21.3",                      // la que debe quedar en los dos sitios
    "compilar": ["core/version.py", ...],     // py_compile
    "js": ["ui/editar.js", ...],              // node --check, si el runner trae node
    "revisar": [                              // se para el recado si falla uno
      {"archivo": "ui/editar.js", "trae": ["texto que debe estar"],
       "no_trae": ["texto que ya no debe estar"], "dice": "qué se anota si pasa"}
    ],
    "commit": "el mensaje del commit, sin las líneas de autoría (se añaden)"
  }

La regla de siempre sigue: la suite corrió entera en el chat con estos mismos
parches sobre una copia de main, y el ensayo exige un árbol idéntico byte por
byte. Eso es lo que autoriza a mandar.
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
AQUI = pathlib.Path(__file__).resolve().parent
RECADO = json.loads((AQUI / "recado.json").read_text(encoding="utf-8"))
PARCHES = RECADO["parches"]
NUMERO = int(RECADO["numero"])
ASUNTO = RECADO["asunto"]
AUTORIA = ("\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew")

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
        if modo in ("nuevo", "entero"):
            if f.exists() and f.read_text(encoding="utf-8") == texto:
                anotar(f"  {arch}: ya estaba"); continue
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(texto, encoding="utf-8")
            anotar(f"  {arch}: {modo} · {len(texto):,} caracteres")
            continue
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
    """Lo comprobable sin navegador y sin el motor de sólidos, que aquí no
    están: que compile, que la versión sea la que debe, y que **cada pieza del
    arreglo esté** (la lista «revisar» del JSON). Lo último existe desde el
    recado 45, cuando un arreglo se escribió y nunca llegó al repositorio."""
    import py_compile
    import shutil as sh
    import subprocess as sp

    compilar = RECADO.get("compilar", [])
    for arch in compilar:
        py_compile.compile(str(shape / arch), doraise=True)
    if compilar:
        anotar(f"{len(compilar)} archivo(s) de Python compilan")

    js = RECADO.get("js", [])
    if js and sh.which("node"):
        for arch in js:
            h = sp.run(["node", "--check", str(shape / arch)], capture_output=True, text=True)
            if h.returncode != 0:
                raise RuntimeError(f"{arch} no es JavaScript válido: {h.stderr.strip()[-300:]}")
        anotar(f"{len(js)} archivo(s) de JavaScript se leen")

    v = json.loads((shape / "package.json").read_text(encoding="utf-8"))["version"]
    if f'VERSION = "{v}"' not in (shape / "core" / "version.py").read_text(encoding="utf-8"):
        raise RuntimeError(f"package.json dice {v} y core/version.py dice otra cosa")
    if v != RECADO["version"]:
        raise RuntimeError(f"la versión quedó en {v} y debía quedar en {RECADO['version']}")
    anotar(f"la versión dice {v} en los dos sitios")

    for r in RECADO.get("revisar", []):
        texto = (shape / r["archivo"]).read_text(encoding="utf-8")
        for clave in r.get("trae", []):
            if clave not in texto:
                raise RuntimeError(f"{r['archivo']} no trae «{clave[:70]}»")
        for clave in r.get("no_trae", []):
            if clave in texto:
                raise RuntimeError(f"{r['archivo']} todavía trae «{clave[:70]}»")
        anotar(r.get("dice") or f"{r['archivo']}: bien")


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path(f"/tmp/recado{NUMERO}")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    aplicar(shape)
    revisar(shape)

    # Los parches ya están puestos en el código: dejarlos ahí sería una copia
    # de lo mismo esperando a desincronizarse.
    shutil.rmtree(shape / PARCHES)
    anotar("parches aplicados y retirados del repositorio")

    if not correr(["git", "status", "--porcelain"], cwd=shape).strip():
        anotar("no había nada que cambiar")
        return 0

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {NUMERO} · {ASUNTO}\n\n```\n" + "\n".join(lineas) + "\n```\n",
        encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m", RECADO["commit"].rstrip() + AUTORIA],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    anotar("empujado a main")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path(f"/tmp/recado{NUMERO}/shape101")
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
