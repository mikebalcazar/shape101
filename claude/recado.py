"""El mandadero · recado 43: la rejilla de la Perspectiva, sin orillas.

Mike, 20-sep, sobre la 0.20.0 ya publicada: *«se dibuja mal el grid en
perspectiva. se ven como 3 planos espaciados»* —con una foto y sólo el plano XY
prendido—.

Eran los tres discos concéntricos con que la 0.20.0 desvanecía la rejilla en
perspectiva. Las líneas quedaban cortadas en el borde de cada disco, y los
extremos de todas esas líneas trazaban tres arcos. Vistos casi de canto cerca
del horizonte, esos arcos se leen como tres planos espaciados. El desvanecido
estaba bien pensado y mal hecho: a pasos, cuando tenía que ser de un golpe.

Ahora la rejilla de la Perspectiva se pinta en un lienzo aparte y se le aplica
una máscara de degradado, en coordenadas del plano y no de la pantalla. No
queda ninguna orilla porque no hay ningún corte: el tono baja hasta cero y ya.

`t032` crece con una comprobación que no habla de discos ni de máscaras sino de
lo que se ve, y por eso seguirá valiendo si mañana el desvanecido se hace de
otra manera: **acercándose, la rejilla nunca puede volverse más tenue**.
Medido: 0.013 de salto con el desvanecido nuevo, 0.142 con el de la 0.20.0.
La prueba falla contra el visor publicado.

Probado aquí antes de mandarlo: la suite entera, 810 comprobaciones en 32
pruebas.
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
PARCHES = "claude/parches-0.20.1"
NUMERO = 43
ASUNTO = "la rejilla de la Perspectiva, sin orillas"

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
    una copia de main, y eso es lo que autoriza a mandarlos. Aquí se comprueba
    lo que se rompe al transportar texto."""
    import py_compile

    for arch in ("core/version.py", "verificar.py", "pruebas/t032_rejilla_y_encuadre.py"):
        py_compile.compile(str(shape / arch), doraise=True)
    anotar("los tres archivos de Python compilan")

    v = json.loads((shape / "package.json").read_text(encoding="utf-8"))["version"]
    if f'VERSION = "{v}"' not in (shape / "core" / "version.py").read_text(encoding="utf-8"):
        raise RuntimeError(f"package.json dice {v} y core/version.py dice otra cosa")
    if v != "0.20.1":
        raise RuntimeError(f"la versión quedó en {v} y debía quedar en 0.20.1")
    anotar(f"la versión dice {v} en los dos sitios")

    visor = (shape / "ui" / "visor.js").read_text(encoding="utf-8")
    # Lo que se fue: el desvanecido a tres discos, que es el defecto. Se busca
    # el código y no la palabra: «discos» aparece en el comentario que explica
    # justamente por qué ya no se hacen así.
    for rastro in ("let discos = null", "discos || [null]", "[1, 0.72, 0.46]"):
        if rastro in visor:
            raise RuntimeError(f"visor.js todavía desvanece a discos: «{rastro}»")
    # Y lo que llegó: el lienzo aparte con su máscara de degradado.
    for clave in ("lienzoAparte", "createRadialGradient", "destination-in"):
        if clave not in visor:
            raise RuntimeError(f"visor.js no trae {clave}: el desvanecido no es de una pieza")
    # La `g` de la escalera y el contexto aparte comparten función: ya se
    # colaron una vez y el ensayo lo cazó con la ventana en blanco.
    if "const grad = g.createRadialGradient" in visor:
        raise RuntimeError("visor.js confunde el contador `g` con el contexto del lienzo aparte")
    anotar("visor.js desvanece la rejilla de una sola pieza")

    prueba = (shape / "pruebas" / "t032_rejilla_y_encuadre.py").read_text(encoding="utf-8")
    if "_sin_orillas" not in prueba or "nunca se vuelve más tenue" not in prueba:
        raise RuntimeError("t032 no fija la regla de las orillas")
    anotar("t032 fija que acercándose la rejilla nunca se vuelve más tenue")


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
            "La rejilla de la Perspectiva, sin orillas\n\n"
            "Mike, sobre la 0.20.0 ya publicada: se dibuja mal el grid en perspectiva, se\n"
            "ven como 3 planos espaciados. Con foto y solo el plano XY prendido.\n\n"
            "Eran los tres discos concentricos con que la 0.20.0 desvanecia la rejilla.\n"
            "Las lineas quedaban cortadas en el borde de cada disco, y los extremos de\n"
            "todas esas lineas trazaban tres arcos; vistos casi de canto cerca del\n"
            "horizonte, esos arcos se leen como tres planos. El desvanecido estaba bien\n"
            "pensado y mal hecho: a pasos, cuando tenia que ser de un golpe.\n\n"
            "Ahora la rejilla de la Perspectiva se pinta en un lienzo aparte y se le\n"
            "aplica una mascara de degradado, en coordenadas del plano y no de la\n"
            "pantalla: sobre el suelo es un circulo y en pantalla cae como la elipse que\n"
            "le toca, asi que lo que se apaga es lo lejano y no lo que queda a los lados.\n"
            "No hay ninguna orilla porque no hay ningun corte. 5 ms por cuadro con las\n"
            "cuatro ventanas y los tres planos.\n\n"
            "t032 crece con una comprobacion que no habla de discos ni de mascaras sino\n"
            "de lo que se ve, y por eso seguira valiendo si el desvanecido cambia:\n"
            "acercandose, la rejilla nunca puede volverse mas tenue. Medido 0.013 con lo\n"
            "nuevo y 0.142 con lo publicado; la prueba falla contra el visor de la 0.20.0.\n\n"
            "Suite completa en el chat: 810 comprobaciones en 32 pruebas.\n\n"
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
