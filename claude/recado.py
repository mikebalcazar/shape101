"""El mandadero · recado 30: el armado se alimenta de su propia última release.

Los dos armados de 0.12.0 murieron a los 19 s en el paso «Python empotrado»
con exit 2, sin cuaderno. Medido desde fuera: el instalador de draw101 0.20.1
—de donde el armado sacaba el Python empotrado— **ya no existe en descargas**
(404). Alguien limpió las releases viejas de draw101 y ese archivo era el
cimiento de shape101 sin que se notara. `curl` sin `-f` bajó una página de
error en vez del .exe, y `7z` tronó con exit 2.

Dos cambios en `.github/workflows/armar-y-publicar.yml`:

1. `INSTALADOR_ANTERIOR` apunta a la última release de **shape101** (0.11.0),
   que ya trae el Python empotrado con el kernel dentro. shape101 deja de
   depender de draw101 para armarse.
2. `curl -f`: si el archivo no existe, falla en voz alta con un mensaje claro
   en vez de dejar que truene 7z sin explicación.

Y se vuelve a disparar el armado de 0.12.0 con un commit de verdad.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
DESTINO = "claude/publicar-0.12.0"
NUEVA_FUENTE = "https://github.com/mikebalcazar/descargas/releases/download/shape101-0.11.0/shape101-0.11.0-setup.exe"

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


def cambiar(texto: str, viejo: str, nuevo: str, donde: str) -> str:
    n = texto.count(viejo)
    if n != 1:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo)


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado30")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    flujo = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    t = flujo.read_text(encoding="utf-8")
    if NUEVA_FUENTE in t:
        anotar("el flujo ya se alimentaba de shape101 0.11.0: no se toca")
    else:
        t = cambiar(
            t,
            "  # INSTALADOR_ANTERIOR es de draw101 a propósito: de ahí sale el Python de\n"
            "  # Windows con ezdxf, fastapi, numpy, pillow y reportlab ya dentro, que es lo que\n"
            "  # shape101 necesita hoy. Cuando el 3D pida OpenCascade, esto cambia.\n",
            "  # INSTALADOR_ANTERIOR es la última release de shape101: de ahí sale el Python\n"
            "  # de Windows con todo dentro, kernel de sólidos incluido. Hasta 0.11.0 era el\n"
            "  # de draw101 0.20.1, y cuando esa release se borró de descargas (19-sep) el\n"
            "  # armado murió a los 19 s sin decir por qué. shape101 se alimenta de sí mismo.\n",
            "flujo (comentario)")
        t = cambiar(
            t,
            "  INSTALADOR_ANTERIOR: https://github.com/mikebalcazar/descargas/releases/download/draw101-0.20.1/draw101-0.20.1-setup.exe",
            f"  INSTALADOR_ANTERIOR: {NUEVA_FUENTE}",
            "flujo (fuente)")
        t = cambiar(
            t,
            '          curl -sSL -o anterior.exe "$INSTALADOR_ANTERIOR"\n',
            '          # -f: si la release ya no existe, que falle aquí con un mensaje y no\n'
            '          # tres líneas después en 7z con un «exit 2» que no explica nada.\n'
            '          curl -fsSL -o anterior.exe "$INSTALADOR_ANTERIOR" || { echo "no existe $INSTALADOR_ANTERIOR: la release de la que se saca el Python empotrado fue borrada"; exit 1; }\n',
            "flujo (curl -f)")
        flujo.write_text(t, encoding="utf-8")
        anotar("armar-y-publicar.yml: se alimenta de shape101 0.11.0 y curl falla en voz alta")

    correr([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
    import yaml
    datos = yaml.safe_load(flujo.read_text(encoding="utf-8"))
    pasos = datos["jobs"]["armar"]["steps"]
    anotar(f"el flujo sigue siendo YAML válido: {len(pasos)} pasos")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: el armado se alimenta de su propia última release\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "El armado se alimenta de la última release de shape101, no de draw101\n\n"
            "Los dos armados de 0.12.0 murieron a los 19 s en «Python empotrado» con exit 2\n"
            "y sin cuaderno. El instalador de draw101 0.20.1, de donde se sacaba el Python\n"
            "empotrado, ya no existe en descargas: alguien limpió las releases viejas y ese\n"
            "archivo era el cimiento de shape101 sin que se notara. curl sin -f bajó una\n"
            "página de error y 7z tronó.\n\n"
            "Ahora la fuente es shape101 0.11.0, que ya trae el kernel dentro, y curl -f\n"
            "falla en voz alta si la release no existe.\n\n"
            "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} movida: el armado de 0.12.0 arranca de nuevo")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado30/shape101")
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
