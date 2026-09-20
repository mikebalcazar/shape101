"""El mandadero · recado 41: el grupo model, alcanzable desde el dibujo.

El motor ya sabía revolver, barrer, loftear y crecer desde una cara —t030 lo
fija—, pero desde el programa no había manera de llegar a ninguna. Un comando
al que no se puede llamar no existe.

Este recado abre las puertas:

  · `planos.del_dibujo` dice el plano de cada ventana **como plano**, para que
    cada boceto se coloque desde el principio en vez de armar la pieza en el
    suelo y rotarla al salir. Sin eso no se puede decir un barrido con el
    perfil en la Frontal y el camino en la Superior: esos dos no se rotan
    juntos.
  · `cuerpo.ops_de_revolver/_barrer/_loft` arman el historial, y `repartir`
    separa la selección en cerrado (el contorno) y abierto (el eje o el
    camino), que es lo que hace que el comando sea «señala y dale».
  · tres rutas nuevas más `crecer-cara`, que niegan en español lo que no se
    puede hacer.
  · `ui/model.js` con los cuatro comandos, su sitio en la barra y su gajo en
    la rueda del 3D, sin moverle el ángulo a Extruir.
  · y la 0.19.0, con su bitácora.

Probado aquí antes de mandarlo: la suite entera, 772 comprobaciones en 31
pruebas, con los parches ya aplicados sobre una copia de main.

Los parches viajan como texto pelón en `claude/parches-0.19.0/`: ni el ancla
ni el texto viven dentro de una cadena de Python, que es como se han colado
los errores de comillas y de sangría en los recados anteriores.
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
PARCHES = "claude/parches-0.19.0"
NUMERO = 41
ASUNTO = "el grupo model, alcanzable desde el dibujo"

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

    `nuevo` es de este recado: un archivo que no existía. Se escribe entero y
    se crea su carpeta si hace falta.
    """
    d = raiz / PARCHES
    for p in json.loads((d / "indice.json").read_text(encoding="utf-8")):
        arch, modo = p["archivo"], p["modo"]
        ancla = ((d / p["ancla_txt"]).read_text(encoding="utf-8")
                 if p.get("ancla_txt") else p.get("ancla", ""))
        texto = (d / p["texto"]).read_text(encoding="utf-8")
        f = raiz / arch
        if modo == "nuevo":
            if f.exists() and f.read_text(encoding="utf-8") == texto:
                anotar(f"  {arch}: ya estaba"); continue
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(texto, encoding="utf-8")
            anotar(f"  {arch}: nuevo · {len(texto):,} caracteres")
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
    rompe al transportar texto: que todo compile y que el número cuadre.
    """
    import py_compile

    for arch in ("core/solido/planos.py", "core/solido/cuerpo.py", "core/solido/rutas.py",
                 "core/version.py", "pruebas/t031_model_desde_el_dibujo.py", "verificar.py"):
        py_compile.compile(str(shape / arch), doraise=True)
    anotar("los seis archivos de Python compilan")

    # La versión vive en dos sitios y tienen que decir lo mismo: un instalador
    # que se llama de una manera y se presenta de otra ya pasó ocho veces.
    v = json.loads((shape / "package.json").read_text(encoding="utf-8"))["version"]
    texto = (shape / "core" / "version.py").read_text(encoding="utf-8")
    if f'VERSION = "{v}"' not in texto:
        raise RuntimeError(f"package.json dice {v} y core/version.py dice otra cosa")
    if v != "0.19.0":
        raise RuntimeError(f"la versión quedó en {v} y debía quedar en 0.19.0")
    anotar(f"la versión dice {v} en los dos sitios")

    # Un comando que no se carga es un comando que no existe.
    html = (shape / "ui" / "index.html").read_text(encoding="utf-8")
    if 'src="model.js"' not in html:
        raise RuntimeError("ui/model.js no se carga desde index.html")
    faltan = [c for c in ("REVOLVER", "BARRER", "LOFT", "CRECER")
              if f'data-cmd="{c}"' not in html]
    if faltan:
        raise RuntimeError("sin botón en la barra: " + ", ".join(faltan))
    anotar("los cuatro comandos se cargan y tienen botón")

    js = (shape / "ui" / "model.js").read_text(encoding="utf-8")
    faltan = [c for c in ("REVOLVER", "BARRER", "LOFT", "CRECER")
              if f'nombre: "{c}"' not in js]
    if faltan:
        raise RuntimeError("sin registrar en model.js: " + ", ".join(faltan))
    rueda = (shape / "ui" / "radial.js").read_text(encoding="utf-8")
    if 'cmd: "REVOLVER"' not in rueda or rueda.index('cmd: "EXTRUIR"') > rueda.index('cmd: "REVOLVER"'):
        raise RuntimeError("la rueda del 3D no ofrece model, o le movió el sitio a Extruir")
    anotar("y están en la rueda, detrás de Extruir")

    rutas = (shape / "core" / "solido" / "rutas.py").read_text(encoding="utf-8")
    # `crecer-cara` cuelga de `/{id_}/`, así que se busca el final y no la ruta
    # entera: la primera versión de esta comprobación buscó "/crecer-cara" y se
    # cayó sola en el ensayo. Que se cayera es la prueba de que sirve.
    faltan = [r for r in ("/revolver", "/barrer", "/loft", "/crecer-cara")
              if f'{r}"' not in rutas]
    if faltan:
        raise RuntimeError("faltan rutas: " + ", ".join(faltan))
    anotar("las cuatro rutas están puestas")


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
            "El grupo model, alcanzable: REVOLVER, BARRER, LOFT y CRECER\n\n"
            "El motor ya sabia las cuatro (t030), pero no habia manera de llegar a ellas\n"
            "desde el dibujo. Aqui se abren las puertas.\n\n"
            "planos.del_dibujo dice el plano de cada ventana como plano, para que cada\n"
            "boceto se coloque desde el principio en vez de armar la pieza en el suelo y\n"
            "rotarla al salir. Sin eso no se puede decir un barrido con el perfil en la\n"
            "Frontal y el camino en la Superior: esos dos no se rotan juntos.\n\n"
            "cuerpo.ops_de_revolver/_barrer/_loft arman el historial y repartir separa la\n"
            "seleccion en cerrado (el contorno) y abierto (el eje o el camino), que es lo\n"
            "que hace que el comando sea senala y dale. Tres rutas nuevas mas crecer-cara,\n"
            "que niegan en espanol lo que no se puede hacer, incluido el caso callado: dos\n"
            "secciones en la misma ventana sin separacion, donde el kernel solo dice\n"
            "BRep_API: command not done.\n\n"
            "ui/model.js con los cuatro comandos, su sitio en la barra y su gajo en la\n"
            "rueda del 3D sin moverle el angulo a Extruir.\n\n"
            "t031, 37 comprobaciones, con el navegador de verdad. Dentro va la que evita\n"
            "que esto se pudra: planos.del_dibujo y rutas._a_mundo son dos maneras de decir\n"
            "el mismo hecho en archivos distintos, y la prueba las compara punto por punto.\n\n"
            "Suite completa en el chat: 772 comprobaciones en 31 pruebas.\n\n"
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
