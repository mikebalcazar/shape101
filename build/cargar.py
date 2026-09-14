"""Prepara la carga de un instalador ya armado para el flujo
`publicar-instalador.yml` de `descargas`, y deja listo el manifiesto.

Uso (lo llama el workflow, pero corre igual a mano):

    python build/cargar.py dist/shape101-0.20.3-setup.exe salida/

Deja en `salida/`:
    carga/meta.json      programa, version, tag, nombre, archivo, bytes, sha256,
                         ultima_tag, ultima_nombre   (lo que exige el flujo)
    carga/notas.md       las notas de la release, sacadas de core/version.py
    carga/partes/*.bin   el .exe en pedazos de 40 000 000 bytes
    shape101.json         el manifiesto que lee el actualizador de la app
    readme-renglon.md    el renglón de la tabla del README de descargas

Todo sale de un solo lugar —`core/version.py`— para que la release, el
manifiesto y el README nunca digan cosas distintas.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core import version as V  # noqa: E402

PROGRAMA = "shape101"
REPO = "mikebalcazar/descargas"
PEDAZO = 40_000_000


def main(exe: Path, salida: Path) -> None:
    datos = exe.read_bytes()
    sha = hashlib.sha256(datos).hexdigest()
    n = len(datos)
    ver = V.VERSION
    if exe.name != f"{PROGRAMA}-{ver}-setup.exe":
        raise SystemExit(f"el archivo se llama {exe.name} pero core/version.py dice {ver}")
    entrada = V.BITACORA[0]
    if entrada["version"] != ver:
        raise SystemExit(f"la primera entrada de BITACORA es {entrada['version']}, no {ver}")

    carga = salida / "carga"
    partes = carga / "partes"
    partes.mkdir(parents=True, exist_ok=True)
    for i in range(0, n, PEDAZO):
        (partes / f"parte-{i // PEDAZO:02d}.bin").write_bytes(datos[i:i + PEDAZO])

    tag = f"{PROGRAMA}-{ver}"
    url = f"https://github.com/{REPO}/releases/download/{tag}/{exe.name}"
    meta = {
        "programa": PROGRAMA,
        "version": ver,
        "tag": tag,
        "nombre": f"{PROGRAMA} {ver}",
        "archivo": exe.name,
        "bytes": n,
        "sha256": sha,
        "ultima_tag": f"{PROGRAMA}-ultima",
        "ultima_nombre": f"{PROGRAMA} — última versión",
    }
    (carga / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    titulo = f"{PROGRAMA} {ver} ({V.FECHA})"
    notas = [f"# {titulo}", ""] + [f"- {c}" for c in entrada["cambios"]] + [""]
    (carga / "notas.md").write_text("\n".join(notas), encoding="utf-8")

    manifiesto = {
        PROGRAMA: {
            "version": ver,
            "fecha": V.FECHA,
            "notas": [titulo] + list(entrada["cambios"]),
            "pagina": f"https://github.com/{REPO}#readme",
            "windows": {
                "archivo": exe.name,
                "bytes": n,
                "sha256": sha,
                "url": url,
                "ultima": f"https://github.com/{REPO}/releases/tag/{PROGRAMA}-ultima",
            },
        }
    }
    (salida / f"{PROGRAMA}.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    mb = (n + 500_000) // 1_000_000
    renglon = (f"| **{PROGRAMA}** | {ver} | {V.FECHA} | [{exe.name}]({url}) | "
               f"[{PROGRAMA}-ultima](https://github.com/{REPO}/releases/tag/{PROGRAMA}-ultima) | {mb} MB |")
    (salida / "readme-renglon.md").write_text(renglon + "\n", encoding="utf-8")

    print(f"{exe.name}: {n} bytes · sha256 {sha} · {len(list(partes.iterdir()))} pedazos · tag {tag}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
