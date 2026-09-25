"""El mandadero · recado 46: el trazo en curso, acostado en su plano.

Mike, 24-sep, con el rectángulo a medio trazar en la Perspectiva y una foto de
Rhino al lado: *«debería estarse trazando sobre el plano xy VISUALMENTE, ir
representando el dibujo real sobre el XY de la perspectiva»*.

La línea ya iba bien desde la 0.21.1. Pero el rectángulo se pintaba con
`c.rect` entre dos esquinas proyectadas, y `c.rect` sólo sabe hacer cuadros
derechos de pantalla: en la Perspectiva salía flotando en vez de acostado. El
círculo y el arco igual, con `c.arc` y un radio en píxeles: un círculo sobre el
suelo, visto en perspectiva, es una elipse. Y el fantasma de previa (bloques,
texto) tampoco pasaba por el plano.

Ahora cada punto del contorno pasa por el plano del trazo y se proyecta, como
ya hacía la línea: las cuatro esquinas del rectángulo, y el círculo y el arco
recorridos cada 5°.

Medido con tinta, no con estado: se leen los píxeles del lienzo de encima a la
mitad de cada lado del paralelogramo que le toca al rectángulo sobre el suelo.
Con el arreglo, tinta en los cuatro; contra main, **cero en los cuatro**. La
elipse igual: tinta en cuatro ángulos y ninguna sobre el círculo de pantalla de
antes. `t035` son 10 comprobaciones y falla 3 contra main.

Suite entera en el chat antes de mandar esto: 854 comprobaciones en 35 pruebas.
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
PARCHES = "claude/parches-0.21.2"
NUMERO = 46
ASUNTO = "el trazo en curso, acostado en su plano"

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
    una copia de main, y eso es lo que autoriza a mandarlos. Y, como desde el
    recado 45, que cada pieza del arreglo **esté**."""
    import py_compile
    import shutil as sh
    import subprocess as sp

    for arch in ("core/version.py", "verificar.py", "pruebas/t035_hule_por_el_plano.py"):
        py_compile.compile(str(shape / arch), doraise=True)
    anotar("los tres archivos de Python compilan")

    if sh.which("node"):
        h = sp.run(["node", "--check", str(shape / "ui" / "vista.js")], capture_output=True, text=True)
        if h.returncode != 0:
            raise RuntimeError(f"ui/vista.js no es JavaScript válido: {h.stderr.strip()[-300:]}")
        anotar("vista.js es JavaScript válido")

    v = json.loads((shape / "package.json").read_text(encoding="utf-8"))["version"]
    if f'VERSION = "{v}"' not in (shape / "core" / "version.py").read_text(encoding="utf-8"):
        raise RuntimeError(f"package.json dice {v} y core/version.py dice otra cosa")
    if v != "0.21.2":
        raise RuntimeError(f"la versión quedó en {v} y debía quedar en 0.21.2")
    anotar(f"la versión dice {v} en los dos sitios")

    vis = (shape / "ui" / "vista.js").read_text(encoding="utf-8")
    # 1 · el rectángulo ya no se pinta con un cuadro de pantalla
    if "c.rect(Math.min(ax, bx), Math.min(ay, by)" in vis:
        raise RuntimeError("ui/vista.js: el hule del rectángulo vuelve a ser un cuadro de pantalla")
    if "const esquinas = [[h.a[0], h.a[1]], [h.b[0], h.a[1]], [h.b[0], h.b[1]], [h.a[0], h.b[1]]];" not in vis:
        raise RuntimeError("ui/vista.js: faltan las cuatro esquinas del rectángulo")
    anotar("el rectángulo en curso pasa sus cuatro esquinas por el plano")
    # 2 · el círculo y el arco, punto a punto por el plano
    if "function arcoPorElPlano(" not in vis or vis.count("arcoPorElPlano(h.c,") != 2:
        raise RuntimeError("ui/vista.js: el círculo o el arco no van por el plano")
    if "Math.abs(h.r) * estado.vista.escala" in vis:
        raise RuntimeError("ui/vista.js: queda un radio de pantalla en el hule")
    anotar("el círculo y el arco en curso van punto a punto por el plano")
    # 3 · el fantasma también
    if "pintarFantasma(h.fantasma, c, h.plano);" not in vis or "function pintarFantasma(trazos, c, plano)" not in vis:
        raise RuntimeError("ui/vista.js: el fantasma no recibe el plano")
    anotar("el fantasma de previa pasa por el plano del trazo")


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
            "El trazo en curso, acostado en su plano\n\n"
            "Mike, con el rectangulo a medio trazar en la Perspectiva y una foto de\n"
            "Rhino al lado: deberia estarse trazando sobre el plano xy visualmente, ir\n"
            "representando el dibujo real sobre el XY de la perspectiva.\n\n"
            "La linea ya iba bien desde la 0.21.1. Pero el rectangulo se pintaba con\n"
            "c.rect entre dos esquinas proyectadas, y c.rect solo sabe hacer cuadros\n"
            "derechos de pantalla: en la Perspectiva salia flotando. El circulo y el\n"
            "arco igual, con c.arc y un radio en pixeles: un circulo sobre el suelo,\n"
            "visto en perspectiva, es una elipse. El fantasma de previa tampoco pasaba\n"
            "por el plano.\n\n"
            "Ahora cada punto del contorno pasa por el plano del trazo y se proyecta:\n"
            "las cuatro esquinas del rectangulo, y el circulo y el arco cada 5 grados.\n\n"
            "Medido con tinta: a la mitad de cada lado del paralelogramo que le toca al\n"
            "rectangulo sobre el suelo hay tinta en los cuatro; contra main, cero en\n"
            "los cuatro. t035, 10 comprobaciones, falla 3 contra main.\n\n"
            "Suite completa en el chat: 854 comprobaciones en 35 pruebas.\n\n"
            "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n"
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
