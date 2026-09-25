"""El mandadero · recado 45: dibujar donde está el ratón, sobre su plano.

Mike, 24-sep, sobre la 0.21.0 recién mandada: *«sigue sin dibujarse en
perspectiva de manera real sobre el plano xy cuando estás trazando»*.

**Seguía porque el arreglo nunca llegó a main.** Estaba escrito desde el 23-sep
y vivía en un documento del proyecto (`shape101-033-dibujo-en-perspectiva.patch`)
que nadie aplicó. Medido antes de tocar nada: `grep -c planoComando ui/entrada.js`
daba 0 contra main. Mike no estaba viendo un arreglo incompleto; estaba viendo el
código de siempre. Eso es lo primero que hay que decir, porque el defecto real
fue del proceso, no del código.

Eran dos defectos que se ven como uno. Los dos medidos aquí, en main, antes de
escribir una línea:

  · **El punto se leía con la cámara de la ventana activa**, no con la de la
    ventana donde está el ratón. Apuntando al centro de la Perspectiva con la
    Superior activa, el programa tomaba un punto a **558 mm** del señalado. Eso
    es lo que Mike describió el 23-sep como *«aparece en un lugar que no tienes
    control»*. Medido después del arreglo: **1.1 mm**.

  · **El hule no se acordaba de su plano**, así que cada ventana lo pintaba con
    el suyo. El mismo punto salía en `[76.2, -62.3, 0]` en la Superior y en
    `[76.2, 0, -62.3]` en la Frontal: el trazo sobre el suelo se veía parado,
    *«como en vista frontal»*. Ahora el hule nace con el plano puesto y las
    cuatro ventanas lo pintan en el mismo punto del mundo.

Y una regla que protege la geometría: una vez tomado el primer punto, una
ventana de **otro** plano ya no se lleva el trazo. Una línea no puede tener un
extremo en el suelo y el otro en la pared, así que el hule se queda quieto.

`t034` son 10 comprobaciones y **fallaba 6 contra main**: existe para que el
arreglo no pueda volver a desaparecer en silencio. Suite entera en el chat antes
de mandar esto: 844 comprobaciones en 34 pruebas.
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
PARCHES = "claude/parches-0.21.1"
NUMERO = 45
ASUNTO = "dibujar donde está el ratón, sobre su plano"

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
    están. La suite ya corrió entera en el chat con estos mismos parches sobre
    una copia de main, y eso es lo que autoriza a mandarlos.

    Este recado revisa una cosa más que los anteriores: que el arreglo **esté**.
    El defecto que Mike reportó dos veces seguía vivo porque el código se
    escribió y nunca llegó al repositorio, así que aquí se para el recado si
    falta cualquiera de las piezas."""
    import py_compile
    import shutil as sh
    import subprocess as sp

    for arch in ("core/version.py", "verificar.py",
                 "pruebas/t034_dibujo_en_perspectiva.py"):
        py_compile.compile(str(shape / arch), doraise=True)
    anotar("los tres archivos de Python compilan")

    # Aquí se toca interfaz, no motor: si el runner trae node, se revisa que el
    # JavaScript por lo menos se lea. Un paréntesis de más no debe llegar a Mike.
    if sh.which("node"):
        for arch in ("ui/entrada.js", "ui/vista.js"):
            h = sp.run(["node", "--check", str(shape / arch)], capture_output=True, text=True)
            if h.returncode != 0:
                raise RuntimeError(f"{arch} no es JavaScript válido: {h.stderr.strip()[-300:]}")
        anotar("entrada.js y vista.js son JavaScript válido")

    v = json.loads((shape / "package.json").read_text(encoding="utf-8"))["version"]
    if f'VERSION = "{v}"' not in (shape / "core" / "version.py").read_text(encoding="utf-8"):
        raise RuntimeError(f"package.json dice {v} y core/version.py dice otra cosa")
    if v != "0.21.1":
        raise RuntimeError(f"la versión quedó en {v} y debía quedar en 0.21.1")
    anotar(f"la versión dice {v} en los dos sitios")

    ent = (shape / "ui" / "entrada.js").read_text(encoding="utf-8")
    vis = (shape / "ui" / "vista.js").read_text(encoding="utf-8")

    # 1 · el plano del comando: se guarda, se limpia y se puede preguntar.
    for clave in ("let planoComando = null", "planoComando = null;",
                  "planoComando: () => planoComando,"):
        if clave not in ent:
            raise RuntimeError(f"ui/entrada.js no trae «{clave}»")
    anotar("el plano del comando se guarda y se puede preguntar")

    # 2 · el hule nace con su plano: esto es lo que hacía que el trazo sobre el
    # suelo se viera parado en las otras ventanas.
    if "if (!h.plano) h.plano = plano;" not in ent:
        raise RuntimeError("ui/entrada.js: el hule vuelve a nacer sin plano")
    if "if (parte && !parte.plano) parte.plano = plano;" not in ent:
        raise RuntimeError("ui/entrada.js: las partes del hule vuelven a nacer sin plano")
    anotar("el hule nace con el plano en el que se está trazando")

    # 3 · manda la ventana bajo el cursor, y el plano del comando la frena.
    if "Ventanas.bajo(px, py)" not in vis:
        raise RuntimeError("ui/vista.js: el ratón ya no manda sobre la ventana activa")
    if "Entrada.planoComando()" not in vis:
        raise RuntimeError("ui/vista.js: ya nada frena el salto de plano a media línea")
    anotar("manda la ventana bajo el cursor, y a media línea el plano la frena")

    if "DESVIO_DE_ANTES_MM = 558" not in (
            shape / "pruebas" / "t034_dibujo_en_perspectiva.py").read_text(encoding="utf-8"):
        raise RuntimeError("t034 perdió la medida de antes, que es lo que hace legible el fallo")
    anotar("t034 está puesta, con los 558 mm de antes escritos")


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
    correr(["git", "commit", "-m",
            "Dibujar donde esta el raton, sobre su plano\n\n"
            "Mike, sobre la 0.21.0: sigue sin dibujarse en perspectiva de manera real\n"
            "sobre el plano xy cuando estas trazando.\n\n"
            "Seguia porque el arreglo nunca llego a main. Estaba escrito desde el 23-sep\n"
            "y vivia en un documento del proyecto que nadie aplico: grep -c planoComando\n"
            "ui/entrada.js daba 0 contra main. El defecto real fue del proceso.\n\n"
            "Eran dos defectos que se ven como uno, los dos medidos en main antes de\n"
            "escribir una linea:\n\n"
            "1. El punto se leia con la camara de la ventana activa, no con la de la\n"
            "   ventana donde esta el raton. Apuntando al centro de la Perspectiva con la\n"
            "   Superior activa, el programa tomaba un punto a 558 mm del senalado: el\n"
            "   lugar que no tienes control. Despues del arreglo, 1.1 mm.\n\n"
            "2. El hule no se acordaba de su plano, asi que cada ventana lo pintaba con\n"
            "   el suyo. El mismo punto salia en [76.2, -62.3, 0] en la Superior y en\n"
            "   [76.2, 0, -62.3] en la Frontal: el trazo sobre el suelo se veia parado,\n"
            "   como en vista frontal. Ahora nace con el plano puesto y las cuatro\n"
            "   ventanas lo pintan en el mismo punto del mundo.\n\n"
            "Y la regla que protege la geometria: con el primer punto ya tomado, una\n"
            "ventana de otro plano no se lleva el trazo. Una linea no puede tener un\n"
            "extremo en el suelo y el otro en la pared.\n\n"
            "t034, 10 comprobaciones, fallaba 6 contra main: existe para que el arreglo\n"
            "no pueda volver a desaparecer en silencio.\n\n"
            "Suite completa en el chat: 844 comprobaciones en 34 pruebas.\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
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
