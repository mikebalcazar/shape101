"""Deja en app/ui/lib/ los archivos de three.js que la pantalla importa, copiados
de node_modules (una versión fija, package.json). Se corre antes de empaquetar
y en desarrollo; app/ui/lib/ no se versiona.

    npm install && python app/armar_ui.py
"""
from __future__ import annotations

import pathlib
import shutil

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "node_modules" / "three"
DESTINO = RAIZ / "app" / "ui" / "lib"
ARCHIVOS = {
    "build/three.module.js": "three.module.js",
    "build/three.core.js": "three.core.js",
    "examples/jsm/controls/OrbitControls.js": "addons/controls/OrbitControls.js",
}

if __name__ == "__main__":
    if not ORIGEN.is_dir():
        raise SystemExit("no hay node_modules/three: corre `npm install` primero")
    for de, a in ARCHIVOS.items():
        destino = DESTINO / a
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ORIGEN / de, destino)
        print(f"{a}: {destino.stat().st_size} bytes")
