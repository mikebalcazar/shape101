"""El mandadero · recado 9: que el armado también hable de vuelta.

El armado de 0.4.0 se rompió y del corredor no llegó nada: el chat no alcanza
el log de Actions. Con los recados esto ya está resuelto —escriben lo que
hicieron en el repositorio—, pero el flujo de armar y publicar no, y eso deja
cada intento fallido como una vuelta de 45 minutos a ciegas.

Este recado le mete al flujo el mismo canal de vuelta:

1. **Cada paso escribe en un cuaderno.** Se inserta un redirector justo después
   de cada `set -euo pipefail`, de modo que todo lo que el paso imprime cae
   además en `armado.log`. No se cambia ninguna orden: sólo se copia su salida.
2. **Pase lo que pase, el cuaderno se sube.** Un paso final con `if: always()`
   empuja `armado.log` y el resultado de cada paso a la rama
   `claude/ultimo-armado`. Si el armado sale bien, sirve de registro; si sale
   mal, es el diagnóstico.

Lo que **no** se toca: ninguna orden del armado. Un canal de vuelta que además
cambia lo que mide no sirve para medir.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import re
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA = "claude/el-armado-habla"

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


CUADERNO = 'exec > >(tee -a "$GITHUB_WORKSPACE/armado.log") 2>&1'

PASO_FINAL = '''
      - name: El cuaderno del armado, pase lo que pase
        if: always()
        shell: bash
        env:
          TOKEN_SHAPE101: ${{ secrets.TOKEN_SHAPE101 }}
          RESULTADOS: ${{ toJSON(steps) }}
        run: |
          # El chat no alcanza el log de Actions. Esto deja en el repositorio lo
          # que imprimió cada paso y cuál se rompió, que es todo lo que hace
          # falta para arreglarlo sin adivinar.
          set +e
          cd "$RUNNER_TEMP"
          rm -rf cuaderno && mkdir cuaderno && cd cuaderno
          git init -q .
          git config user.name "shape101 (armado)"
          git config user.email "mike@forespot.com"
          mkdir -p claude
          {
            echo "# Último armado"
            echo
            echo "- corrido: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
            echo "- rama: $GITHUB_REF_NAME"
            echo "- commit: $GITHUB_SHA"
            echo
            echo '## Cómo salió cada paso'
            echo
            echo '```json'
            echo "$RESULTADOS"
            echo '```'
            echo
            echo '## Lo que imprimieron (últimas 400 líneas)'
            echo
            echo '```'
            tail -n 400 "$GITHUB_WORKSPACE/armado.log" 2>/dev/null || echo "(no hubo cuaderno)"
            echo '```'
          } > claude/ultimo-armado.md
          git add claude/ultimo-armado.md
          git commit -q -m "armado $GITHUB_REF_NAME: lo que imprimió cada paso"
          git push -q -f "https://x-access-token:$TOKEN_SHAPE101@github.com/mikebalcazar/shape101" HEAD:claude/ultimo-armado
          echo "cuaderno subido a la rama claude/ultimo-armado"
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado9")
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

    if CUADERNO in texto:
        anotar("el flujo ya escribía el cuaderno: no se toca")
    else:
        # Después de cada `set -euo pipefail`, con su misma sangría.
        nuevo, n = re.subn(r"( *)set -euo pipefail\n",
                           lambda m: f"{m.group(0)}{m.group(1)}{CUADERNO}\n", texto)
        if n == 0:
            raise RuntimeError("el flujo no tiene ningún «set -euo pipefail» donde enganchar")
        texto = nuevo
        anotar(f"{n} pasos del armado escriben ahora en el cuaderno")

    if "El cuaderno del armado" in texto:
        anotar("el flujo ya subía el cuaderno: no se toca")
    else:
        texto = texto.rstrip("\n") + "\n" + PASO_FINAL
        anotar("agregado el paso final que sube el cuaderno pase lo que pase")

    flujo.write_text(texto, encoding="utf-8")

    # Comprobar que sigue siendo YAML válido antes de empujar: un flujo roto no
    # corre, y entonces el canal de vuelta tampoco.
    try:
        import yaml  # el corredor lo trae
        datos = yaml.safe_load(flujo.read_text(encoding="utf-8"))
        pasos = datos["jobs"]["armar"]["steps"]
        anotar(f"el flujo sigue siendo YAML válido: {len(pasos)} pasos")
        if not any("cuaderno" in str(p.get("name", "")).lower() for p in pasos):
            raise RuntimeError("el paso del cuaderno no quedó en el flujo")
    except ImportError:
        anotar("sin pyyaml en el corredor: no se pudo revisar el YAML, se sube igual")

    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: que el armado también hable de vuelta\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "El armado deja dicho lo que pasó, salga bien o mal\n\n"
            "El chat no alcanza el log de Actions, así que un armado en rojo era una vuelta\n"
            "de 45 minutos a ciegas. Ahora cada paso copia su salida a un cuaderno y un paso\n"
            "final con if: always() lo empuja a la rama claude/ultimo-armado, junto con el\n"
            "resultado de cada paso. Si sale bien sirve de registro; si sale mal, es el\n"
            "diagnóstico.\n\n"
            "No se cambia ninguna orden del armado: sólo se copia su salida. Un canal de\n"
            "vuelta que además cambia lo que mide no sirve para medir."],
           cwd=shape)
    correr(["git", "push", "-f", "origin", RAMA], cwd=shape)
    correr(["git", "push", "origin", f"{RAMA}:main"], cwd=shape)
    anotar(f"empujada {RAMA} y llevada a main")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado9/shape101")
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
