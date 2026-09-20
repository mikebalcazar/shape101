"""El mandadero · recado 40: fuera poc/, y la receta de publicar al día.

Mike, el 19-sep, preguntando qué eran esos archivos: `poc/` era la prueba de
concepto del 12 y 13 de septiembre —la medición que decidió si shape101 iba o
no—. **No era la app: era el estudio previo.**

Hace tiempo que no corre: importa de `app/motor/`, una carpeta que dejó de
existir cuando el motor se mudó a `core/solido/`. Los cinco pasos mueren con
`ModuleNotFoundError: No module named 'app'`. Nada fuera de `poc/` la toca, no
entra al instalador y no la ve ninguna prueba.

**Lo que valía eran los números, y ya están guardados** en Drive
(`suite101/shape101-prueba-de-concepto-2026-09-12-13 (archivo)`): el plan, la
tabla de resultados y los seis veredictos. Ahí sigue estando lo que sostiene el
motor de hoy —que los nombres derivados aguantan un cambio de cota y la huella
geométrica no, 0 de 2 caras— y el aviso del `~2` que la 0.18.0 acabó
arreglando.

Así que aquí se borra el código, que es deuda: 22 archivos, 196 KB y once que
todavía nombran draw101.

Y de paso, `claude/COMO-PUBLICAR.md` se pone al día: decía «45 minutos» cuando
el armado tarda unos 20, hablaba de 24 pruebas cuando son 28, y explicaba el
Python empotrado con la `INSTALADOR_ANTERIOR` que la 0.18.0 quitó. Una receta
equivocada es peor que no tenerla.

**Este recado no cambia la versión ni dispara un armado**: no toca nada que se
instale.
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
PARCHES = "claude/parches-limpieza"

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
    """Lo comprobable antes de empujar."""
    if (shape / "poc").exists():
        raise RuntimeError("poc/ sigue ahí")
    anotar("poc/ ya no está")

    # Que no quede nadie apuntando a lo borrado. Se busca en el código, no en
    # las palabras: un comentario que cuente la historia puede seguir diciendo
    # «poc» sin que eso rompa nada.
    sueltos = correr(["bash", "-lc",
                      "grep -rIl --include='*.py' --include='*.yml' --include='*.json' "
                      "-e 'from poc' -e 'import poc' -e 'poc/' . | grep -v node_modules || true"],
                     cwd=shape).strip()
    if sueltos:
        raise RuntimeError("todavía hay quien apunta a poc/: " + sueltos.replace("\n", ", "))
    anotar("y nadie apuntaba a ella")

    import py_compile
    py_compile.compile(str(shape / "verificar.py"), doraise=True)
    anotar("verificar.py sigue compilando")

    quedan = correr(["bash", "-lc",
                     "grep -rIl 'draw101' --include='*.yml' --include='*.py' --include='*.js' "
                     ". | grep -v node_modules || true"], cwd=shape).strip()
    anotar("archivos que todavía nombran draw101: "
           + (quedan.replace("\n", ", ") if quedan else "ninguno"))

    receta = (shape / "claude" / "COMO-PUBLICAR.md").read_text(encoding="utf-8")
    if "INSTALADOR_ANTERIOR" in receta or "45 minutos" in receta:
        raise RuntimeError("la receta de publicar sigue desactualizada")
    if "MANIFIESTO" not in receta:
        raise RuntimeError("la receta no explica de dónde sale el instalador anterior")
    anotar("la receta de publicar está al día")


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado40")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    if (shape / "poc").is_dir():
        cuantos = len(list((shape / "poc").rglob("*")))
        correr(["git", "rm", "-r", "-q", "poc"], cwd=shape)
        anotar(f"borrada poc/ ({cuantos} entradas)")
    else:
        anotar("poc/ ya no estaba")

    aplicar(shape)
    revisar(shape)

    # Los parches ya están puestos en el código: dejarlos ahí sería una copia
    # de lo mismo esperando a desincronizarse.
    shutil.rmtree(shape / PARCHES)
    anotar("parches aplicados y retirados del repositorio")

    if not correr(["git", "status", "--porcelain"], cwd=shape).strip():
        anotar("no había nada que cambiar: main ya estaba limpio")
        return 0

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: 40 · fuera poc/, y la receta de publicar al día\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "Fuera poc/, y la receta de publicar al día\n\n"
            "poc/ era la prueba de concepto del 12 y 13 de septiembre: la medición que\n"
            "decidió si shape101 iba o no. No era la app, era el estudio previo, y hace\n"
            "tiempo que no corre: importa de app/motor/, una carpeta que dejó de existir\n"
            "cuando el motor se mudó a core/solido/. Nada fuera de ella la tocaba.\n\n"
            "Lo que valía eran los números y ya están guardados en Drive: el plan, la tabla\n"
            "de resultados y los seis veredictos. Ahí sigue lo que sostiene el motor de hoy\n"
            "—que los nombres derivados aguantan un cambio de cota y la huella geométrica\n"
            "no, 0 de 2 caras— y el aviso del ~2 que la 0.18.0 acabó arreglando.\n\n"
            "Se van 22 archivos y 196 KB, y con ellos los once que todavía nombraban\n"
            "draw101.\n\n"
            "Y COMO-PUBLICAR.md se pone al día: decía 45 minutos cuando el armado tarda\n"
            "unos 20, hablaba de 24 pruebas cuando son 28, y explicaba el Python empotrado\n"
            "con la INSTALADOR_ANTERIOR que la 0.18.0 quitó. Una receta equivocada es peor\n"
            "que no tenerla.\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    anotar("main actualizado")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado40/shape101")
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
