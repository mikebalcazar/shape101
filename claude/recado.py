"""El mandadero · recado 42: la rejilla, y el cero al centro de las cuatro.

Mike, 20-sep: *«cuando recién abres shape101, la ventana superior y la de
perspectiva tienen todo descentrado el grid, y la frontal y lateral no tienen
grid… el grid debería ser infinito, es una referencia»*. Y media hora después,
sobre CRECER: *«NO SIRVIÓ»*.

Eran el mismo defecto visto por dos lados. Las tres ventanas que no son la
Superior nacían con el origen del mundo **en su esquina de arriba a la
izquierda**, así que una pieza levantada después caía fuera de la Perspectiva:
no había cara que picar, y CRECER contestaba, con razón, «primero señala una
cara». Medido antes de tocar nada, con una pieza de 400 × 300 × 100: la
Perspectiva la proyectaba entre −225 y 0 píxeles, y su ventana empieza en 0.

Lo que va aquí:

  · La rejilla es infinita. Se averigua al revés —de las cuatro esquinas de la
    ventana al plano— y salen exactamente las líneas que se ven. Antes era un
    cuadro fijo de mil milímetros alrededor del cero, con su orilla pintada.
  · Cada ventana pinta **su** plano: XY la Superior, XZ la Frontal, YZ la
    Lateral. El suelo visto desde la Frontal es una raya, y por eso esas dos
    salían vacías.
  · Se prende y se apaga por ventana —el cuadrito del título— y en la
    Perspectiva por plano. El botón REJILLA manda sobre todas sin borrar lo que
    cada una tenía elegido.
  · Y el botón REJILLA apaga de verdad: la rejilla se pinta dentro de algo que
    va en caché, y la llave de esa caché no la miraba.
  · Las cuatro ventanas miran al cero al abrir, y Extents encuadra las cuatro
    contando también las piezas, no sólo los trazos.

Probado aquí antes de mandarlo: la suite entera, 808 comprobaciones en 32
pruebas. `t032` es la nueva y falla contra el código de la 0.19.0.

Los parches viajan como texto pelón en `claude/parches-0.20.0/`: ni el ancla ni
el texto viven dentro de una cadena de Python, que es como se han colado los
errores de comillas y de sangría en los recados anteriores.
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
PARCHES = "claude/parches-0.20.0"
NUMERO = 42
ASUNTO = "la rejilla infinita y el cero al centro de las cuatro ventanas"

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

    `entero` es de este recado: el archivo se reemplaza completo. Se usa cuando
    lo que cambió está tan repartido que describirlo por anclas sería más
    frágil que mandar el archivo, que es el caso de `visor.js` y `ventanas.js`.
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
    """Lo comprobable sin el motor de sólidos, que aquí no está instalado.

    No se corre la suite: son 350 MB de OpenCascade y catorce minutos. La suite
    ya corrió entera en el chat, con estos mismos parches puestos sobre una
    copia de main, y eso es lo que autoriza a mandarlos. Aquí se comprueba lo
    que sí se puede comprobar en treinta segundos y que es justo lo que se
    rompe al transportar texto: que todo compile y que las piezas se encuentren
    unas a otras.
    """
    import py_compile

    for arch in ("core/preferencias.py", "core/version.py", "verificar.py",
                 "pruebas/t032_rejilla_y_encuadre.py"):
        py_compile.compile(str(shape / arch), doraise=True)
    anotar("los cuatro archivos de Python compilan")

    # La versión vive en dos sitios y tienen que decir lo mismo: un instalador
    # que se llama de una manera y se presenta de otra ya pasó ocho veces.
    v = json.loads((shape / "package.json").read_text(encoding="utf-8"))["version"]
    if f'VERSION = "{v}"' not in (shape / "core" / "version.py").read_text(encoding="utf-8"):
        raise RuntimeError(f"package.json dice {v} y core/version.py dice otra cosa")
    if v != "0.20.0":
        raise RuntimeError(f"la versión quedó en {v} y debía quedar en 0.20.0")
    anotar(f"la versión dice {v} en los dos sitios")

    # Las preferencias nuevas: sin ellas los interruptores del título no tienen
    # dónde guardarse y se olvidan al cerrar.
    prefs = (shape / "core" / "preferencias.py").read_text(encoding="utf-8")
    for clave in ("rejilla_ventanas", "rejilla_planos"):
        if clave not in prefs:
            raise RuntimeError(f"falta la preferencia {clave}")
    anotar("las preferencias por ventana y por plano están puestas")

    # Las piezas se buscan por nombre entre archivos: si una se queda con el
    # nombre viejo, el programa arranca y la rejilla no aparece nunca.
    ventanas = (shape / "ui" / "ventanas.js").read_text(encoding="utf-8")
    for f in ("planosRejilla", "botonEn", "alternarRejilla", "centrarEnOrigen"):
        if f"function {f}" not in ventanas or f not in ventanas.split("return {")[-1]:
            raise RuntimeError(f"ventanas.js no ofrece {f}")
    anotar("ventanas.js ofrece las cuatro funciones nuevas")

    visor = (shape / "ui" / "visor.js").read_text(encoding="utf-8")
    if "dibujarSuelo" in visor:
        raise RuntimeError("visor.js todavía pinta el suelo con orilla")
    for clave in ("BASES", "XZ: [[1, 0, 0]", "YZ: [[0, 1, 0]", "MIN_PX"):
        if clave not in visor:
            raise RuntimeError(f"visor.js no trae {clave}")
    anotar("visor.js pinta los tres planos y ya no pinta la orilla")

    vista = (shape / "ui" / "vista.js").read_text(encoding="utf-8")
    for clave in ("Ventanas.planosRejilla(v)", "Ventanas.botonEn", "Cuerpos.esquinas"):
        if clave not in vista:
            raise RuntimeError(f"vista.js no llama a {clave}")
    # La llave de la caché del plano: sin la rejilla dentro, el botón REJILLA
    # cambia la preferencia y la pantalla se queda igual. Fue el defecto.
    llave = vista.split("function llavePlano()")[1].split("\n}")[0]
    if "rejilla" not in llave:
        raise RuntimeError("la llave del plano no mira la rejilla: el botón no la borraría")
    anotar("vista.js engancha las cuatro ventanas y la llave mira la rejilla")

    if "esquinas" not in (shape / "ui" / "cuerpos.js").read_text(encoding="utf-8").split("return {")[-1]:
        raise RuntimeError("cuerpos.js no ofrece esquinas(): Extents dejaría piezas fuera")
    anotar("cuerpos.js ofrece la caja de las piezas para encuadrar")


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
            "La rejilla infinita, por ventana y por plano; y el cero al centro\n\n"
            "Mike reporto dos cosas con media hora de diferencia: que al abrir el grid\n"
            "sale descentrado y que la Frontal y la Lateral no tienen, y que CRECER no\n"
            "sirvio. Eran el mismo defecto visto por dos lados.\n\n"
            "Las tres ventanas que no son la Superior nacian con el origen del mundo en\n"
            "su esquina de arriba a la izquierda. Medido con una pieza de 400x300x100: la\n"
            "Perspectiva la proyectaba entre -225 y 0 pixeles, y su ventana empieza en 0.\n"
            "La pieza caia fuera, no habia cara que picar, y CRECER contestaba con razon\n"
            "que primero habia que senalar una.\n\n"
            "La rejilla: ahora se averigua al reves -de las cuatro esquinas de la ventana\n"
            "al plano- y salen exactamente las lineas que se ven, a cualquier zoom. Cada\n"
            "ventana pinta su plano (XY, XZ, YZ); el suelo visto desde la Frontal es una\n"
            "raya, y por eso esas dos salian vacias. En la Perspectiva se desvanece hacia\n"
            "el horizonte en vez de apelmazarse.\n\n"
            "Se prende y se apaga por ventana, con el cuadrito del titulo, y en la\n"
            "Perspectiva por plano. El boton REJILLA manda sobre todas sin borrar lo que\n"
            "cada una tenia elegido, y ahora apaga de verdad: la rejilla se pinta dentro\n"
            "de algo que va en cache y la llave de esa cache no la miraba.\n\n"
            "Extents encuadra las cuatro y cuenta tambien las piezas, no solo los trazos.\n\n"
            "t032, 36 comprobaciones, mirando el lienzo pixel por pixel en las orillas de\n"
            "cada ventana a tres zooms, y picando una cara con el raton de verdad.\n\n"
            "Suite completa en el chat: 808 comprobaciones en 32 pruebas.\n\n"
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
