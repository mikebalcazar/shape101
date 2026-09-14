"""El mandadero · recado 5: rescatar el motor de sólidos y meter el kernel al armado.

Dos cosas que el chat no puede hacer con sus manos, y las dos por el mismo
motivo: el conector sólo escribe texto que pase por la ventana del chat.

**1. Rescatar el motor de sólidos del historial de git.** La versión 0.2.0 de
shape101 —la del camino desechado— dejó escrito y probado lo más difícil de
todo esto: nombrar las caras de un sólido de forma que sigan significando lo
mismo después de cambiar una cota (`nombres.py`), convertir entidades de
draw101 en una cara cerrada (`boceto.py`), el historial de operaciones
(`historial.py`) y la malla por cara para pintarla (`malla.py`). Ese código no
se perdió al borrar `app/`: sigue en el commit 6b573ff. Reescribirlo sería
tirar mediciones buenas por gusto.

Se copia a `core/solido/`, que es donde vive el 3D de shape101, y se le
arreglan los `import` para su casa nueva.

**2. Meter el kernel al Python empotrado.** El Python que se saca del
instalador de draw101 **no trae pip**, así que build123d se instala desde el
Python del armador hacia adentro, con `pip install --target`. Comprobado antes:
hay ruedas para ese Windows exacto, 122 MB comprimidos.

El kernel arrastra su propio numpy y su propio ezdxf, y la app ya usa los
suyos. Ahí puede haber un choque, así que el paso termina importando **los dos
mundos juntos** con el Python empotrado: si se pelean, el armado se detiene
ahí y no tres pasos después, donde el error ya no se entiende.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA = "claude/motor-de-solidos"
COMMIT_0_2_0 = "6b573ff676645a30455505d6bd49c83af54678f0"
MODULOS = ["nombres.py", "boceto.py", "historial.py", "malla.py"]

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


PASO_KERNEL = '''      - name: El kernel de sólidos dentro del Python empotrado
        run: |
          set -euo pipefail
          # El Python empotrado no trae pip: se instala desde el Python del
          # armador hacia adentro. Las ruedas son para este mismo Windows.
          pip install --target runtime/python/Lib/site-packages --upgrade build123d
          # Los dos mundos tienen que convivir: el kernel trae su numpy y su
          # ezdxf, y la app ya usaba los suyos. Si se pelean, que truene aquí.
          ./runtime/python/python.exe -c "import ezdxf, fastapi, uvicorn, numpy, PIL, reportlab; import build123d; from build123d import Box; print('kernel y app conviven; caja de prueba con', len(Box(1,1,1).faces()), 'caras')"
          du -sh runtime/python || true

'''


def meter_kernel_al_flujo(texto: str) -> str:
    ancla = "      - uses: actions/setup-node@v4"
    if PASO_KERNEL.strip().splitlines()[0] in texto:
        anotar("el flujo ya traía el paso del kernel: no se toca")
        return texto
    if texto.count(ancla) != 1:
        raise RuntimeError("no encontré dónde meter el paso del kernel en el flujo")
    return texto.replace(ancla, PASO_KERNEL + ancla, 1)


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado5")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    # Clon completo: hace falta el historial para rescatar el commit viejo.
    correr(["git", "clone", f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    destino = shape / "core" / "solido"
    destino.mkdir(parents=True, exist_ok=True)
    for modulo in MODULOS:
        texto = correr(["git", "show", f"{COMMIT_0_2_0}:app/motor/{modulo}"], cwd=shape)
        # Su casa cambió: app.motor → core.solido.
        texto = texto.replace("from app.motor import", "from core.solido import")
        texto = texto.replace("from app.motor.", "from core.solido.")
        texto = texto.replace("import app.motor", "import core.solido")
        (destino / modulo).write_text(texto, encoding="utf-8")
        anotar(f"rescatado {modulo} ({len(texto)} bytes) de la 0.2.0")

    (destino / "__init__.py").write_text(
        '"""El 3D de shape101: sólidos exactos sobre OpenCascade.\n\n'
        'Estos módulos vienen de la 0.2.0 —el camino que se desechó— porque lo\n'
        'que resolvían sigue siendo cierto: nombrar las caras de manera que\n'
        'sobrevivan a un cambio de cota es lo más difícil de un modelador con\n'
        'historial, y ya estaba medido. Lo desechado fue la app, no el motor.\n"""\n',
        encoding="utf-8")
    anotar("core/solido/__init__.py escrito")

    flujo = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    flujo.write_text(meter_kernel_al_flujo(flujo.read_text(encoding="utf-8")), encoding="utf-8")
    anotar("armar-y-publicar.yml: el kernel se instala dentro del Python empotrado y se comprueba que conviva con la app")

    # Comprobaciones antes de empujar
    for modulo in MODULOS:
        if "app.motor" in (destino / modulo).read_text(encoding="utf-8"):
            raise RuntimeError(f"{modulo} todavía apunta a app.motor")
    if "build123d" not in flujo.read_text(encoding="utf-8"):
        raise RuntimeError("el flujo no quedó con el kernel")
    anotar("ningún módulo quedó apuntando a su casa vieja")

    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: rescatar el motor de sólidos y meter el kernel al armado\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "El motor de sólidos, rescatado del historial, y el kernel dentro del armado\n\n"
            "Lo más difícil de un modelador con historial es que «la cara de arriba» siga\n"
            "siendo la de arriba después de cambiar una cota de abajo. Eso ya estaba escrito\n"
            "y medido en la 0.2.0, el camino que se desechó: se rescata del commit 6b573ff a\n"
            "core/solido/ en vez de volver a escribirlo. Lo desechado fue la app, no el motor.\n\n"
            "El armado instala build123d dentro del Python empotrado (que no trae pip) desde\n"
            "el Python del armador, y termina importando los dos mundos juntos: el kernel\n"
            "trae su numpy y su ezdxf y la app ya usaba los suyos, así que si se pelean el\n"
            "armado se detiene ahí, donde el error todavía se entiende."],
           cwd=shape)
    correr(["git", "push", "-f", "origin", RAMA], cwd=shape)
    correr(["git", "push", "origin", f"{RAMA}:main"], cwd=shape)
    anotar(f"empujada {RAMA} y llevada a main")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado5/shape101")
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
