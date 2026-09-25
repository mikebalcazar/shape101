"""El mandadero · recado 44: traer un dibujo 2D de draw101.

Mike, 24-sep: *«necesito poder importar dibujo 2D desde draw. El formato 101d»*.

Lo primero que se midió, antes de escribir una línea: **el documento de los dos
programas es idéntico campo por campo**. Se escribió un dibujo con el propio
draw101 0.21.0 y el motor de aquí lo abrió entero — 3 entidades, 2 capas. Así
que un dibujo de draw101 nunca necesitó traducción; necesitaba que alguien lo
dejara entrar. `/api/abrir` repartía por extensión, `.t101d` no estaba en la
lista, y el archivo acababa en el lector de DXF contestando «is not a DXF file».

Lo que va aquí:

  · `IMPORTAR` (y el botón «Importar…») mete el dibujo **adentro** de la pieza
    abierta, sin borrar lo que haya. Lo que entra es geometría de verdad: se
    selecciona y se levanta con EXTRUIR. Ni Abrir —que reemplaza— ni REFEXT
    —que entra bloqueado, para calcar— servían para eso.
  · Cae siempre en el suelo (XY). Lo eligió Mike.
  · Las capas que trae y aquí no están se crean; las que ya existen no se tocan.
  · Abrir acepta `.101d` y `.t101d`, y abrir uno **no** lo vuelve el archivo de
    guardado: el 2D sigue siendo de draw101.

Y dos defectos que aparecieron al medir, los dos ya publicados:

  · La interfaz decía `.t101d` mientras el motor guardaba `.101s`. Las piezas
    que Mike guardaba **no aparecían en su propio diálogo de Abrir**, Guardar le
    volvía a pedir la ruta cada vez, y el doble clic de Windows no abría una
    pieza propia.
  · El peligroso: traer otro dibujo encima de una pieza levantada **la borraba
    sin avisar**. `nuevo_id()` cuenta desde un contador global que se resiembra
    al leer cualquier archivo; los ids de draw101 no son `e1, e2, …`, así que el
    contador volvía a cero y `Documento.agregar`, que guarda por llave, pisaba
    lo que ya estaba. Medido: la polilínea y el sólido desaparecían. Tocaba
    también a la referencia externa, y ahí queda arreglado igual.

Probado aquí antes de mandarlo: la suite entera, 834 comprobaciones en 33
pruebas. `t033` es la nueva y falla contra el código publicado — su primer
fallo es justamente el de las extensiones.
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
PARCHES = "claude/parches-0.21.0"
NUMERO = 44
ASUNTO = "traer un dibujo 2D de draw101"

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
    una copia de main, y eso es lo que autoriza a mandarlos."""
    import py_compile

    for arch in ("core/config.py", "core/version.py", "server.py", "verificar.py",
                 "pruebas/t033_importar_de_draw.py"):
        py_compile.compile(str(shape / arch), doraise=True)
    anotar("los cinco archivos de Python compilan")

    v = json.loads((shape / "package.json").read_text(encoding="utf-8"))["version"]
    if f'VERSION = "{v}"' not in (shape / "core" / "version.py").read_text(encoding="utf-8"):
        raise RuntimeError(f"package.json dice {v} y core/version.py dice otra cosa")
    if v != "0.21.0":
        raise RuntimeError(f"la versión quedó en {v} y debía quedar en 0.21.0")
    anotar(f"la versión dice {v} en los dos sitios")

    # El defecto que Mike vivía: el motor guardaba .101s y la interfaz decía
    # .t101d. Se comprueba aquí y además en t033, porque es la clase de cosa
    # que se vuelve a desincronizar sola.
    cfg = (shape / "core" / "config.py").read_text(encoding="utf-8")
    app = (shape / "ui" / "app.js").read_text(encoding="utf-8")
    if 'EXT_PROYECTO = ".101s"' not in cfg:
        raise RuntimeError("core/config.py ya no guarda en .101s")
    if 'const EXT_PROPIA = "101s"' not in app:
        raise RuntimeError("ui/app.js y core/config.py no dicen la misma extensión")
    for clave in ("EXT_DRAW101", "def es_propio", "def es_de_draw"):
        if clave not in cfg:
            raise RuntimeError(f"core/config.py no trae {clave}")
    anotar("el motor y la interfaz guardan con la misma extensión, y reconocen draw101")

    srv = (shape / "server.py").read_text(encoding="utf-8")
    if 'ruta.suffix.lower() == config.EXT_PROYECTO' in srv:
        raise RuntimeError("queda una puerta repartiendo por una sola extensión")
    for clave in ('@app.post("/api/importar")', "def _id_libre", "config.es_de_draw(ruta)"):
        if clave not in srv:
            raise RuntimeError(f"server.py no trae {clave}")
    # El que borraba piezas: si alguien vuelve a pedir un id sin mirar lo que
    # hay abierto, importar vuelve a pisar lo que ya estaba.
    if "copia.id = ent_mod.nuevo_id()" in srv:
        raise RuntimeError("alguna puerta vuelve a pedir ids sin mirar el documento abierto")
    anotar("la puerta de importar está puesta y los ids ya no pisan lo que hay")

    for arch, clave in (("ui/suite.js", 'nombre: "IMPORTAR"'),
                        ("ui/index.html", 'id="b-importar"'),
                        ("electron/main.js", '".101s"')):
        if clave not in (shape / arch).read_text(encoding="utf-8"):
            raise RuntimeError(f"{arch} no trae {clave}")
    anotar("el comando, el botón y el doble clic de Windows están enganchados")


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
            "Traer un dibujo 2D de draw101, y dos defectos que salieron al medir\n\n"
            "Mike: necesito poder importar dibujo 2D desde draw, el formato 101d.\n\n"
            "Lo primero que se midio: el documento de los dos programas es identico\n"
            "campo por campo. Se escribio un dibujo con draw101 0.21.0 de verdad y el\n"
            "motor de aqui lo abrio entero. Nunca necesito traduccion; necesitaba que\n"
            "alguien lo dejara entrar. /api/abrir repartia por extension, .t101d no\n"
            "estaba en la lista, y acababa en el lector de DXF diciendo is not a DXF.\n\n"
            "IMPORTAR mete el dibujo adentro de la pieza abierta sin borrar lo que haya,\n"
            "como geometria de verdad que se selecciona y se levanta con EXTRUIR. Ni\n"
            "Abrir -que reemplaza- ni REFEXT -que entra bloqueado para calcar- servian.\n"
            "Cae siempre en el suelo (XY), que lo eligio Mike. Las capas que trae y aqui\n"
            "no estan se crean; las que ya existen no se tocan.\n\n"
            "Dos defectos ya publicados que aparecieron al medir:\n\n"
            "1. La interfaz decia .t101d y el motor guardaba .101s. Las piezas guardadas\n"
            "   no aparecian en el propio dialogo de Abrir, Guardar volvia a pedir ruta\n"
            "   cada vez, y el doble clic de Windows no abria una pieza propia.\n\n"
            "2. El peligroso: importar encima de una pieza levantada la borraba sin\n"
            "   avisar. nuevo_id() cuenta desde un contador global que se resiembra al\n"
            "   leer cualquier archivo; los ids de draw101 no son e1, e2, asi que el\n"
            "   contador volvia a cero y Documento.agregar, que guarda por llave, pisaba\n"
            "   lo que ya estaba. Tocaba tambien a la referencia externa.\n\n"
            "t033, 24 comprobaciones, con draw101 de verdad como referencia. Su primera\n"
            "comprobacion no prueba una funcion: prueba que el motor y la interfaz digan\n"
            "la misma extension, que es el defecto 1 y la clase de cosa que se vuelve a\n"
            "desincronizar sola.\n\n"
            "Suite completa en el chat: 834 comprobaciones en 33 pruebas.\n\n"
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
