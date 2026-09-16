"""El mandadero · recado 10: el kernel también donde corren las pruebas.

**Por qué se rompió 0.4.0.** El armado instala `build123d` dentro del Python
empotrado —el que se mete al instalador— y las pruebas corren con el Python del
armador, que es otro. Las tres pruebas nuevas del 3D importan el kernel, así
que reventaron con «no existe el módulo build123d». Dos Pythons distintos en el
mismo armado: fácil de pasar por alto, y el flujo lo dijo en un log que el chat
no alcanza.

Aquí se arreglan dos cosas:

1. `build123d` se agrega a lo que se instala antes de correr `verificar.py`.
2. **Se revisa que el flujo siga siendo YAML válido antes de empujarlo.** El
   recado 9 no pudo hacerlo porque al corredor le faltaba la biblioteca; ahora
   se instala primero. Un flujo mal escrito no corre, y si no corre tampoco
   sube el cuaderno: el canal de vuelta se perdería justo cuando más falta
   hace.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA = "claude/kernel-en-las-pruebas"

lineas: list[str] = []


def anotar(t: str) -> None:
    print(t, flush=True)
    lineas.append(t)


def _sin_secretos(t: str) -> str:
    for n in ("TOKEN_DRAW101", "TOKEN_SHAPE101"):
        v = os.environ.get(n)
        if v:
            t = t.replace(v, "***")
    return t


def correr(orden, cwd=None) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if h.returncode != 0:
        raise RuntimeError(_sin_secretos(f"falló {orden[0]}: {h.stderr.strip()[-800:]}"))
    return h.stdout


VIEJO = "pip install -q ezdxf fastapi uvicorn numpy pillow reportlab pymupdf pypdfium2 playwright"
NUEVO = ("# build123d es el kernel de sólidos. Se instala también aquí porque las\n"
         "          # pruebas del 3D (t020, t021, t022) corren con ESTE Python, no con el\n"
         "          # empotrado que se mete al instalador. Son dos Pythons distintos, y\n"
         "          # olvidarlo fue lo que tumbó el primer intento de 0.4.0.\n"
         "          pip install -q ezdxf fastapi uvicorn numpy pillow reportlab pymupdf pypdfium2 playwright build123d")


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado10")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    flujo = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    texto = flujo.read_text(encoding="utf-8")
    if "playwright build123d" in texto:
        anotar("el flujo ya instalaba build123d para las pruebas: no se toca")
    else:
        n = texto.count(VIEJO)
        if n != 1:
            raise RuntimeError(f"la línea de dependencias de las pruebas aparece {n} veces, esperaba 1")
        flujo.write_text(texto.replace(VIEJO, NUEVO, 1), encoding="utf-8")
        anotar("las pruebas ya instalan build123d en el Python del armador")

    # Ahora sí: revisar el YAML. Sin esto, un flujo roto no corre y el cuaderno
    # del armado tampoco se sube, que es perder el canal de vuelta.
    correr([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
    import yaml
    datos = yaml.safe_load(flujo.read_text(encoding="utf-8"))
    pasos = datos["jobs"]["armar"]["steps"]
    anotar(f"el flujo es YAML válido: {len(pasos)} pasos")
    nombres = [str(p.get("name", p.get("uses", "?"))) for p in pasos]
    if not any("cuaderno" in n.lower() for n in nombres):
        raise RuntimeError("el paso que sube el cuaderno no está en el flujo")
    anotar("el paso del cuaderno sigue en su sitio: " + nombres[-1])
    con_tee = sum(1 for p in pasos if "tee -a" in str(p.get("run", "")))
    anotar(f"{con_tee} pasos copian su salida al cuaderno")

    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: el kernel también donde corren las pruebas\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "Las pruebas del 3D también necesitan el kernel instalado\n\n"
            "El armado mete build123d dentro del Python empotrado —el que va al instalador—\n"
            "y las pruebas corren con el Python del armador, que es otro. Las tres pruebas\n"
            "nuevas importan el kernel, así que reventaron con «no existe el módulo\n"
            "build123d». Dos Pythons distintos en el mismo armado: fácil de pasar por alto.\n\n"
            "De paso se revisa que el flujo siga siendo YAML válido antes de empujarlo. El\n"
            "intento anterior no pudo porque al corredor le faltaba la biblioteca; ahora se\n"
            "instala primero. Un flujo mal escrito no corre, y si no corre tampoco sube el\n"
            "cuaderno del armado: se perdería el canal de vuelta justo cuando más falta hace."],
           cwd=shape)
    correr(["git", "push", "-f", "origin", RAMA], cwd=shape)
    correr(["git", "push", "origin", f"{RAMA}:main"], cwd=shape)
    anotar(f"empujada {RAMA} y llevada a main")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado10/shape101")
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
