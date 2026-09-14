"""DWG sin depender de que el taller instale nada  ·  shape101.

Feature 1 y 3 (F7). El DWG es formato cerrado de Autodesk: no hay una librería
de Python que lo lea. Hasta la 0.9.0 esto se resolvía pidiendo el **ODA File
Converter**, que es gratuito pero es *otro programa que hay que instalar*, y
eso convertía «shape101 lee DWG» en «shape101 lee DWG si antes te bajas otra
cosa». Para un taller que recibe planos en DWG, eso es no leerlos.

Ahora hay tres caminos, y se prueban en este orden:

1. **ODA File Converter**, si está instalado. Es el oficial y el más fiel: lo
   mantiene la gente que escribió la especificación. Si está, se usa.
2. **LibreDWG** (GNU) compilado a WebAssembly. Va dentro del programa. Lee de
   R13 a R2018 menos R2007.
3. **acad-ts** (puerto de ACadSharp, MIT). También va dentro. Cubre R2007, que
   es justo donde LibreDWG tropieza, y **escribe** DWG.

Los tres desembocan en lo mismo: un DXF que lee `dxf_lector.leer_dxf()`. No hay
un segundo importador que mantener.

Los motores 2 y 3 son JavaScript y necesitan Node ≥20. No se empaqueta un Node
aparte: **Electron ya lo trae**, y con `ELECTRON_RUN_AS_NODE=1` se comporta como
un Node pelón. Un intérprete, no dos.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
GUION = RAIZ / "dwgjs" / "convertir.mjs"

#: Cuánto se espera a una conversión. Un plano de obra grande tarda; un motor
#: colgado no debe colgar el programa.
ESPERA = 180


class DWGNoDisponible(RuntimeError):
    """No hay forma de convertir este DWG en esta máquina."""


# --- encontrar con qué correr el JavaScript --------------------------------

#: Dónde vive el ejecutable respecto a `core/dwg.py`, según el sistema.
#:
#:  · Windows:  `shape101.exe` · `resources/app/core/dwg.py`  → dos arriba
#:  · macOS:    `Contents/MacOS/shape101` · `Contents/Resources/app/core/dwg.py`
#:              → tres arriba y por otra rama, así que se busca aparte
NOMBRES_ELECTRON = ("shape101.exe", "shape101", "t101draw.exe", "t101draw", "electron.exe", "electron",
                    "Electron")


def _electron() -> pathlib.Path | None:
    """Un Electron con el que correr el JavaScript.

    Primero el nuestro, que va dentro del propio paquete. Si no —porque se
    está corriendo desde el código— se busca el de la app instalada, y de paso
    el de **Taller 101**, que también es Electron. Es la misma idea que ya usa
    `shape101.bat` con el Python de Taller 101: lo que ya está en la máquina,
    se aprovecha.

    En macOS el árbol de un `.app` no es el de Windows: el binario vive en
    `Contents/MacOS/` y nuestro código en `Contents/Resources/app/`, que son
    ramas hermanas. Subir dos niveles no llega; hay que cruzar.
    """
    for arriba in (RAIZ.parent.parent, RAIZ.parent):
        for nombre in NOMBRES_ELECTRON:
            cand = arriba / nombre
            if cand.exists() and cand.is_file():
                return cand

    # macOS, dentro del .app: .../Contents/Resources/app/core/dwg.py
    for padre in RAIZ.parents:
        if padre.name == "Contents":
            macos = padre / "MacOS"
            if macos.is_dir():
                for cand in sorted(macos.iterdir()):
                    if cand.is_file():
                        return cand
            break

    if sys.platform == "darwin":
        for base in ("/Applications/shape101.app", "/Applications/t101draw.app",
                     "/Applications/Taller 101.app",
                     str(pathlib.Path.home() / "Applications/shape101.app")):
            macos = pathlib.Path(base) / "Contents" / "MacOS"
            if macos.is_dir():
                for cand in sorted(macos.iterdir()):
                    if cand.is_file():
                        return cand
        return None

    for base in (r"C:\Program Files\Taller 101\shape101",
                 r"C:\Program Files (x86)\Taller 101\shape101",
                 r"C:\Program Files\Taller 101\t101draw",
                 r"C:\Program Files\Taller 101",
                 r"C:\Program Files (x86)\Taller 101"):
        p = pathlib.Path(base)
        if not p.exists():
            continue
        for nombre in ("shape101.exe", "t101draw.exe", "Taller 101.exe", "Taller101.exe"):
            cand = p / nombre
            if cand.exists():
                return cand
    return None


def runtimes_node() -> list[str]:
    """Todo lo que en esta máquina podría correr el guión, en orden de preferencia.

    Es una lista y no uno solo a propósito: encontrar un `.exe` no es lo mismo
    que poder ejecutarlo. Si el primero no arranca se prueba el siguiente, en
    vez de dar por perdido el DWG.
    """
    cands: list[str] = []
    exe = _electron()
    if exe:
        cands.append(str(exe))
    for nombre in ("node", "node.exe"):
        ruta = shutil.which(nombre)
        if ruta and ruta not in cands:
            cands.append(ruta)
    return cands


def runtime_node() -> list[str] | None:
    """El primero de `runtimes_node()`, o None. Lo usa el diagnóstico."""
    c = runtimes_node()
    return [c[0]] if c else None


def _memoria_total_mb() -> int:
    """RAM de la máquina en MB, o 8192 si no se puede saber."""
    try:
        if sys.platform == "win32":
            import ctypes
            class _Mem(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = _Mem(); m.dwLength = ctypes.sizeof(_Mem)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return int(m.ullTotalPhys // (1024 * 1024))
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024))
    except Exception:
        return 8192


def _heap_mb() -> int:
    """Cuánta memoria se le deja a V8 para convertir.

    Un DWG de 60 MB (A8-501, de Mike) sale como DXF de 350 MB, y LibreDWG lo
    arma en memoria como una sola cadena: con el tope por omisión de Node
    (unos 2–4 GB) se moría con «FatalProcessOutOfMemory» y el plano abría
    vacío. Se le da hasta el 70 % de la RAM, mínimo 4 GB.
    """
    return max(4096, int(_memoria_total_mb() * 0.7))


def _correr(args: list[str]) -> dict:
    """Corre el guión y devuelve su JSON. Nunca levanta por culpa del motor."""
    cands = runtimes_node()
    if not cands:
        raise DWGNoDisponible(
            "No se encontró con qué correr el lector de DWG. En la app instalada "
            "esto no pasa; si estás corriendo desde el código, instala shape101 "
            "o ten Node 20 o más nuevo."
        )
    entorno = dict(os.environ)
    entorno["ELECTRON_RUN_AS_NODE"] = "1"     # que Electron sea un Node pelón
    entorno["NODE_OPTIONS"] = ""              # nada heredado que lo estorbe

    problemas = []
    for runtime in cands:
        try:
            p = subprocess.run(
                [runtime, f"--max-old-space-size={_heap_mb()}", str(GUION)] + args,
                capture_output=True, timeout=ESPERA, env=entorno,
            )
        except subprocess.TimeoutExpired:
            raise DWGNoDisponible(
                f"El DWG tardó más de {ESPERA} segundos en convertirse. "
                "Suele ser un archivo enorme o dañado."
            )
        except OSError as exc:
            problemas.append(f"{runtime}: no arrancó ({exc})")
            continue

        for linea in reversed((p.stdout or b"").decode("utf-8", "replace").splitlines()):
            linea = linea.strip()
            if linea.startswith("{"):
                try:
                    return json.loads(linea)
                except json.JSONDecodeError:
                    continue
        err = (p.stderr or b"").decode("utf-8", "replace").strip()[-300:]
        problemas.append(f"{runtime}: no contestó. {err}".strip())

    raise DWGNoDisponible("El lector de DWG no contestó.\n" + "\n".join(problemas))


def motor_disponible() -> bool:
    """¿Se puede leer DWG en esta máquina, sin contar el ODA?"""
    if not GUION.exists():
        return False
    try:
        return bool(_correr(["probar"]).get("ok"))
    except Exception:
        return False


# --- ODA File Converter, si está ------------------------------------------

def oda_disponible() -> str | None:
    """Ruta al ODA File Converter, o None si no está instalado."""
    for cand in ("ODAFileConverter", "ODAFileConverter.exe"):
        ruta = shutil.which(cand)
        if ruta:
            return ruta
    # macOS: el ODA se instala como una app en /Applications.
    for base in ("/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter",
                 str(pathlib.Path.home()
                     / "Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter")):
        if pathlib.Path(base).exists():
            return base

    for base in (r"C:\Program Files\ODA", r"C:\Program Files (x86)\ODA",
                 r"C:\Archivos de programa\ODA"):
        p = pathlib.Path(base)
        if p.exists():
            for hijo in p.glob("**/ODAFileConverter.exe"):
                return str(hijo)
    return None


def _oda(entrada: pathlib.Path, carpeta_salida: pathlib.Path,
         tipo: str, version: str = "ACAD2013") -> pathlib.Path | None:
    """Convierte con el ODA. Devuelve el archivo producido, o None si no pudo."""
    oda = oda_disponible()
    if not oda:
        return None
    dentro = carpeta_salida / "in"
    fuera = carpeta_salida / "out"
    dentro.mkdir(parents=True, exist_ok=True)
    fuera.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entrada, dentro / entrada.name)
    try:
        subprocess.run(
            [oda, str(dentro), str(fuera), version, tipo, "0", "1", entrada.name],
            check=True, capture_output=True, timeout=ESPERA)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    producidos = list(fuera.glob("*." + tipo.lower()))
    return producidos[0] if producidos else None


# --- lo que usa el resto del programa --------------------------------------

def a_dxf(ruta: str | pathlib.Path, destino: str | pathlib.Path) -> dict:
    """DWG → DXF. Devuelve `{motor, apagadas}`.

    `apagadas` es la lista de capas que el DWG trae apagadas, o **None** si no
    se pudo averiguar — y None no es lo mismo que lista vacía: significa
    «déjalas todas encendidas», que es el lado seguro del error.

    Levanta `DWGNoDisponible` si ningún motor pudo, con el porqué de cada uno:
    un plano que no abre y no dice por qué es lo peor que le puede pasar a
    alguien con prisa.
    """
    ruta = pathlib.Path(ruta)
    destino = pathlib.Path(destino)
    if not ruta.exists():
        raise DWGNoDisponible(f"No está el archivo: {ruta}")

    from . import progreso
    mb = ruta.stat().st_size / 1e6
    progreso.poner(f"Convirtiendo el DWG ({mb:.0f} MB)… en un archivo grande "
                   "esto es lo que más tarda")
    producido = _oda(ruta, destino.parent / "_oda", "DXF")
    if producido is not None:
        shutil.move(str(producido), destino)
        shutil.rmtree(destino.parent / "_oda", ignore_errors=True)
        return {"motor": "oda", "apagadas": None}
    shutil.rmtree(destino.parent / "_oda", ignore_errors=True)

    r = _correr(["dwg2dxf", str(ruta), str(destino)])
    if not r.get("ok"):
        detalle = "; ".join(r.get("fallos") or []) or r.get("error", "")
        raise DWGNoDisponible(
            f"No se pudo leer el DWG. {detalle}\n"
            "Si el archivo abre en AutoCAD, mándamelo: casi siempre es una "
            "versión o una entidad que todavía no cubrimos."
        )
    motor = r.get("motor", "?")
    # acad-ts escribe el apagado bien en su propio DXF; LibreDWG no, y por eso
    # se le pregunta aparte (ver `capasApagadas` en dwgjs/convertir.mjs).
    apagadas = r.get("apagadas") if motor == "libredwg" else []
    return {"motor": motor, "apagadas": apagadas}


def desde_dxf(dxf: str | pathlib.Path, destino: str | pathlib.Path,
              version: str = "R2013") -> str:
    """DXF → DWG. Devuelve el nombre del motor que lo logró."""
    dxf = pathlib.Path(dxf)
    destino = pathlib.Path(destino)

    producido = _oda(dxf, destino.parent / "_oda", "DWG")
    if producido is not None:
        shutil.move(str(producido), destino)
        shutil.rmtree(destino.parent / "_oda", ignore_errors=True)
        return "oda"
    shutil.rmtree(destino.parent / "_oda", ignore_errors=True)

    r = _correr(["dxf2dwg", str(dxf), str(destino), version])
    if not r.get("ok"):
        raise DWGNoDisponible(
            f"No se pudo escribir el DWG: {r.get('error', '')}\n"
            "El DXF sí se puede guardar, y AutoCAD y Rhino lo abren igual."
        )
    return r.get("motor", "?")


def estado() -> dict:
    """Qué motores hay, para enseñarlo en la interfaz sin adivinar."""
    return {
        "oda": oda_disponible() is not None,
        "empotrado": motor_disponible(),
        "runtime": (runtimes_node() or [None])[0],
        "runtimes": runtimes_node(),
    }


if __name__ == "__main__":                       # diagnóstico a mano
    print(json.dumps(estado(), indent=2, ensure_ascii=False))
    sys.exit(0 if (estado()["oda"] or estado()["empotrado"]) else 1)
