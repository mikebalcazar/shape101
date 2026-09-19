"""El mandadero · recado 32: fuera draw101 de la maquinaria.

Mike (19-sep): «ya deja de pensar en draw101, haz de cuenta que no existe, esto
es un producto completamente independiente».

Lo que quedaba, y era deuda de verdad, no sólo de nombre:

1. `recado.yml` le pasaba a cada recado un `TOKEN_DRAW101` que ya nadie usa. Un
   secreto de más es una puerta de más, y además decía en voz alta que shape101
   dependía de otro repositorio.
2. `armar-y-publicar.yml` hablaba de «la 0.20.x instalada» —la numeración de
   draw101— y explicaba de dónde venía el Python empotrado citando al otro
   producto. Ahora sale de shape101 y así debe leerse.
3. Los recados tapaban `TOKEN_DRAW101` al escribir sus reportes; ya no hace
   falta tapar lo que no existe.

Este recado **no toca la rama de publicación**: hay un armado en curso y no
tiene por qué enterarse.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"

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


def cambiar(texto: str, viejo: str, nuevo: str, donde: str) -> str:
    n = texto.count(viejo)
    if n != 1:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo)


ENCABEZADO_VIEJO = """# Arma el instalador de shape101 en un Windows de GitHub, lo prueba, lo manda a
# `descargas` por la rama de carga que espera `publicar-instalador.yml`, espera
# a que esa release exista y entonces deja `shape101.json` y el README de
# `descargas` diciendo la versión nueva. Al terminar, la 0.20.x instalada en
# cualquier máquina ve el letrero «Actualizar».
"""

ENCABEZADO_NUEVO = """# Arma el instalador de shape101 en un Windows de GitHub, lo prueba, lo manda a
# `descargas` por la rama de carga que espera `publicar-instalador.yml`, espera
# a que esa release exista y entonces deja `shape101.json` y el README de
# `descargas` diciendo la versión nueva. Al terminar, cualquier shape101 ya
# instalada ve el letrero «Actualizar».
#
# La receta completa, con sus trampas, está en `claude/COMO-PUBLICAR.md`.
"""

FUENTE_VIEJA = """  # INSTALADOR_ANTERIOR es la última release de shape101: de ahí sale el Python
  # de Windows con todo dentro, kernel de sólidos incluido. Hasta 0.11.0 era el
  # de draw101 0.20.1, y cuando esa release se borró de descargas (19-sep) el
  # armado murió a los 19 s sin decir por qué. shape101 se alimenta de sí mismo.
"""

FUENTE_NUEVA = """  # INSTALADOR_ANTERIOR es la última release de shape101: de ahí sale el Python
  # de Windows con todo dentro, kernel de sólidos incluido. shape101 se alimenta
  # de sí mismo, así que **esa release no se borra nunca**: es el cimiento del
  # siguiente armado. (Se aprendió a golpes el 19-sep, cuando desapareció el
  # archivo del que salía el Python y el armado murió a los 19 s sin decir por
  # qué. Ver claude/COMO-PUBLICAR.md.)
"""

ULTIMA_VIEJA = """          echo "- Release \\`shape101-$VER\\` publicada · \\`shape101-ultima\\` movida · \\`shape101.json\\` y README en main." >> "$GITHUB_STEP_SUMMARY"
          echo "- Las 0.20.x instaladas ya ven el letrero «Actualizar»." >> "$GITHUB_STEP_SUMMARY"
"""

ULTIMA_NUEVA = """          echo "- Release \\`shape101-$VER\\` publicada · \\`shape101-ultima\\` movida · \\`shape101.json\\` y README en main." >> "$GITHUB_STEP_SUMMARY"
          echo "- Las shape101 instaladas ya ven el letrero «Actualizar»." >> "$GITHUB_STEP_SUMMARY"
"""


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado32")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    # 1 · el recado ya no recibe un token de otro producto
    rec = shape / ".github" / "workflows" / "recado.yml"
    t = rec.read_text(encoding="utf-8")
    if "TOKEN_DRAW101" not in t:
        anotar("recado.yml ya no pasaba TOKEN_DRAW101: no se toca")
    else:
        rec.write_text(cambiar(t, "          TOKEN_DRAW101: ${{ secrets.TOKEN_DRAW101 }}\n", "",
                               "recado.yml"), encoding="utf-8")
        anotar("recado.yml: fuera TOKEN_DRAW101 (un secreto de más es una puerta de más)")

    # 2 · el flujo de armado habla de shape101 y de nadie más
    flujo = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    t = flujo.read_text(encoding="utf-8")
    if "COMO-PUBLICAR.md" in t:
        anotar("armar-y-publicar.yml ya estaba limpio: no se toca")
    else:
        t = cambiar(t, ENCABEZADO_VIEJO, ENCABEZADO_NUEVO, "flujo (encabezado)")
        t = cambiar(t, FUENTE_VIEJA, FUENTE_NUEVA, "flujo (fuente)")
        t = cambiar(t, ULTIMA_VIEJA, ULTIMA_NUEVA, "flujo (resumen)")
        flujo.write_text(t, encoding="utf-8")
        anotar("armar-y-publicar.yml: habla de shape101 y de nadie más")

    correr([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
    import yaml
    for f in (rec, flujo):
        datos = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert datos["jobs"], f
    anotar("los dos flujos siguen siendo YAML válido")
    quedan = correr(["bash", "-lc",
                     "grep -rIl 'draw101' --include='*.yml' --include='*.py' --include='*.js' "
                     ". | grep -v '^./claude/COMO-PUBLICAR.md' | grep -v node_modules || true"],
                    cwd=shape).strip()
    anotar("archivos que todavía nombran draw101: " + (quedan.replace("\n", ", ") if quedan else "ninguno"))

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: fuera draw101 de la maquinaria\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "Fuera draw101 de la maquinaria: shape101 se arma solo\n\n"
            "Mike: «ya deja de pensar en draw101, haz de cuenta que no existe, esto es un\n"
            "producto completamente independiente».\n\n"
            "Los recados recibían un TOKEN_DRAW101 que ya nadie usaba —un secreto de más es\n"
            "una puerta de más—, y el flujo de armado hablaba de la numeración 0.20.x del\n"
            "otro producto. El Python empotrado sale de la última release de shape101 y el\n"
            "comentario ahora dice lo que importa: esa release no se borra nunca, porque es\n"
            "el cimiento del siguiente armado.\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    anotar("main actualizado (la rama de publicación no se toca: hay un armado en curso)")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado32/shape101")
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
