"""El mandadero · recado 23: 0.8.2, segundo intento — las pruebas aprenden que se nace en mm.

El armado de 0.8.2 se detuvo, y bien: dos comprobaciones de `t001_dxf` seguían
esperando que un dibujo nuevo naciera en centímetros, que es como nace draw101.
shape101 nace en milímetros por decisión de Mike del primer día, y las pruebas
lo cazaron. Es justo para lo que están.

Aquí se actualizan esas dos expectativas y se vuelve a disparar el armado.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA = "claude/pruebas-en-mm"
VERSION = "0.8.2"
DESTINO = f"claude/publicar-{VERSION}"

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
    fin = "\r\n" if "\r\n" in texto else "\n"
    viejo, nuevo = viejo.replace("\n", fin), nuevo.replace("\n", fin)
    n = texto.count(viejo)
    if n != 1:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo)


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado23")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    ruta = shape / "pruebas" / "t001_dxf.py"
    t = ruta.read_text(encoding="utf-8")
    if "nace en milímetros" in t:
        anotar("t001_dxf ya esperaba milímetros: no se toca")
    else:
        t = cambiar(t, '''    r.igual(doc_dxf.header.get("$INSUNITS"), 5,
            "el DXF declara la unidad en la que se dibujó (5 = cm)")''',
                    '''    r.igual(doc_dxf.header.get("$INSUNITS"), 4,
            "el DXF declara la unidad en la que se dibujó (4 = mm)")''', "t001 (INSUNITS)")
        t = cambiar(t, '''    # **Todo se compara en milímetros de verdad, no en números.** Un dibujo
    # nuevo nace en centímetros y al abrir un archivo se convierte a la unidad
    # que declara su encabezado: 1 200 cm vuelven como 12 000 mm, que es el
    # mismo mueble. Comparar los números pelados haría fallar la prueba por
    # una conversión correcta, y —peor— la haría pasar el día que la
    # conversión se pierda.
    ki = doc.mm_por_unidad()
    kv = vuelto.mm_por_unidad()
    r.casi(ki, 10.0, "el dibujo nuevo nace en centímetros")''',
                    '''    # **Todo se compara en milímetros de verdad, no en números.** En shape101
    # un dibujo nuevo nace en milímetros —decisión de Mike del primer día; en
    # draw101 nacía en centímetros— y al abrir un archivo se convierte a la
    # unidad que declara su encabezado. Comparar los números pelados haría
    # fallar la prueba por una conversión correcta, y —peor— la haría pasar el
    # día que la conversión se pierda.
    ki = doc.mm_por_unidad()
    kv = vuelto.mm_por_unidad()
    r.casi(ki, 1.0, "el dibujo nuevo nace en milímetros")''', "t001 (nace en mm)")
        t = cambiar(t, '''        r.punto(mm(linea.p2), [1200 * ki, 0],
                "la línea vuelve midiendo lo mismo (12 000 mm)")''',
                    '''        r.punto(mm(linea.p2), [1200 * ki, 0],
                "la línea vuelve midiendo lo mismo")''', "t001 (etiqueta)")
        ruta.write_text(t, encoding="utf-8", newline="")
        anotar("pruebas/t001_dxf.py: espera milímetros, como shape101")

    correr([sys.executable, "-c",
            "import ast, pathlib; ast.parse(pathlib.Path('pruebas/t001_dxf.py').read_text(encoding='utf-8'))"], cwd=shape)
    anotar("t001_dxf.py sigue siendo Python válido")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, segundo intento: las pruebas aprenden que se nace en mm\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "Las pruebas del DXF aprenden que shape101 nace en milímetros\n\n"
            "El armado de 0.8.2 se detuvo porque dos comprobaciones de t001 esperaban que un\n"
            "dibujo nuevo naciera en centímetros, como en draw101. shape101 nace en mm por\n"
            "decisión de Mike del primer día. Las pruebas cazaron el cambio, que es justo\n"
            "para lo que están; aquí se actualizan las dos expectativas."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} movida: el armado de {VERSION} arranca de nuevo")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado23/shape101")
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
