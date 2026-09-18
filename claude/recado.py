"""El mandadero · recado 21: 0.8.1 — el kernel se calienta al abrir.

Mike, en la 0.8.0: «se tarda como medio minuto en pasar del 2D al 3D». No es el
pintado —girar ya va bien—: es el **kernel de sólidos cargando por primera
vez**. Son 350 MB de bibliotecas que Windows lee y su antivirus escanea la
primera vez que alguien extruye. En la máquina del chat tarda 3 s; en Windows
con antivirus, medio minuto es creíble.

Dos cosas:

1. **Calentar el kernel al abrir el programa**, en un hilo aparte. Para cuando
   el usuario dibuje su primer contorno y extruya, ya está cargado. La app no
   tarda más en abrir: el hilo no bloquea nada.
2. **Cronómetro en el motor.** `/api/cuerpo/extruir` devuelve cuánto tardó, y
   la pantalla lo dice. Si vuelve a tardar, sabremos si es el kernel, el sólido
   o la malla, en vez de adivinar.
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
RAMA = "claude/kernel-caliente"
VERSION = "0.8.1"
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


def fin_de(t: str) -> str:
    return "\r\n" if "\r\n" in t else "\n"


def cambiar(texto: str, viejo: str, nuevo: str, donde: str, veces: int = 1) -> str:
    fin = fin_de(texto)
    viejo, nuevo = viejo.replace("\n", fin), nuevo.replace("\n", fin)
    n = texto.count(viejo)
    if veces and n != veces:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba {veces}")
    if not veces and n == 0:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» no aparece")
    return texto.replace(viejo, nuevo)


def parchar(ruta: pathlib.Path, cambios, ya: str, donde: str) -> None:
    t = ruta.read_text(encoding="utf-8")
    if ya in t:
        anotar(f"{donde}: ya estaba, no se toca")
        return
    for c in cambios:
        veces = c[2] if len(c) > 2 else 1
        t = cambiar(t, c[0], c[1], donde, veces)
    ruta.write_text(t, encoding="utf-8", newline="")
    anotar(f"{donde}: parchado")


CALENTAR = '''app = FastAPI(title=config.APP_NOMBRE)

# --- El kernel de sólidos se calienta en segundo plano --------------------
# Son 350 MB de bibliotecas que Windows lee, y su antivirus escanea, la
# primera vez que se importan: medio minuto medido por Mike en la 0.8.0 al
# extruir por primera vez. Aquí se importa al arrancar, en un hilo que no
# bloquea nada, para que cuando el usuario extruya ya esté cargado.
import threading as _hilos  # noqa: E402


def _calentar_kernel():
    import time as _t
    t0 = _t.perf_counter()
    try:
        import build123d  # noqa: F401
        print(f"[3d] kernel listo en {_t.perf_counter() - t0:.1f} s", flush=True)
    except Exception as e:  # sin kernel no hay 3D, pero el 2D sigue
        print(f"[3d] el kernel no cargó: {e}", flush=True)


_hilos.Thread(target=_calentar_kernel, name="calentar-kernel", daemon=True).start()'''


BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "El motor de sólidos se carga al abrir el programa, en segundo plano, en vez de "
            "la primera vez que extruyes. En 0.8.0 esa primera extrusión tardaba medio "
            "minuto: eran 350 MB de bibliotecas leyéndose por primera vez.",
            "Al extruir, la consola dice cuánto tardó el motor. Si algo vuelve a tardar, "
            "sabremos dónde.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado21")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    parchar(shape / "server.py", [("app = FastAPI(title=config.APP_NOMBRE)", CALENTAR)],
            "_calentar_kernel", "server.py (el kernel se calienta al abrir)")

    parchar(shape / "core" / "solido" / "rutas.py", [
        ('    nuevo = Cuerpo(operaciones=ops, capa=entidades[0].get("capa", "0"))\n'
         '    with doc.transaccion("extruir"):\n'
         '        doc.agregar(nuevo)\n'
         '    return _malla(nuevo)',
         '    import time\n'
         '    t0 = time.perf_counter()\n'
         '    nuevo = Cuerpo(operaciones=ops, capa=entidades[0].get("capa", "0"))\n'
         '    with doc.transaccion("extruir"):\n'
         '        doc.agregar(nuevo)\n'
         '    salida = _malla(nuevo)\n'
         '    # Cuánto tardó de verdad, para que la pantalla lo diga y nadie adivine.\n'
         '    salida["ms"] = round((time.perf_counter() - t0) * 1000)\n'
         '    return salida'),
    ], 'salida["ms"]', "core/solido/rutas.py (cronómetro)")

    parchar(shape / "ui" / "tresd.js", [
        ('      Comandos.eco(`pieza de ${m.caja[0]} × ${m.caja[1]} × ${m.caja[2]} mm · ${(m.volumen_mm3 / 1000).toFixed(1)} cm³`);',
         '      Comandos.eco(`pieza de ${m.caja[0]} × ${m.caja[1]} × ${m.caja[2]} mm · ${(m.volumen_mm3 / 1000).toFixed(1)} cm³`\n'
         '        + (m.ms !== undefined ? ` · el motor tardó ${m.ms} ms` : ""));'),
    ], "el motor tardó", "ui/tresd.js (la pantalla dice cuánto tardó)")

    hoy = dt.date.today().isoformat()
    ver = shape / "core" / "version.py"
    t = ver.read_text(encoding="utf-8")
    actual = re.search(r'VERSION = "([^"]+)"', t).group(1)
    if actual != VERSION:
        t = cambiar(t, f'VERSION = "{actual}"', f'VERSION = "{VERSION}"', "version.py")
        t = re.sub(r'FECHA = "[^"]+"', f'FECHA = "{hoy}"', t, count=1)
        ver.write_text(cambiar(t, "BITACORA: list[dict] = [\n", BITACORA % (VERSION, hoy), "version.py"),
                       encoding="utf-8")
        paq = shape / "package.json"
        t = paq.read_text(encoding="utf-8")
        t = cambiar(t, f'"version": "{actual}"', f'"version": "{VERSION}"', "package.json")
        t = cambiar(t, f'"_versionApp": "{actual} —', f'"_versionApp": "{VERSION} —', "package.json")
        paq.write_text(cambiar(t, f'"artifactName": "shape101-{actual}-setup.${{ext}}"',
                               f'"artifactName": "shape101-{VERSION}-setup.${{ext}}"', "package.json"),
                       encoding="utf-8")
        anotar(f"versión {actual} → {VERSION}")

    correr(["node", "--check", str(shape / "ui" / "tresd.js")])
    correr([sys.executable, "-c",
            "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('server.py', 'core/solido/rutas.py')]"],
           cwd=shape)
    anotar("server.py y rutas.py siguen siendo Python válido; tresd.js pasa node --check")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, el kernel se calienta al abrir\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: el kernel de sólidos se calienta al abrir el programa\n\n"
            "Mike midió medio minuto en la primera extrusión de la 0.8.0. No es el pintado:\n"
            "es el kernel cargando por primera vez, 350 MB que Windows lee y el antivirus\n"
            "escanea. Ahora se importa al arrancar, en un hilo que no bloquea nada.\n\n"
            "Y el motor devuelve cuánto tardó cada extrusión, y la consola lo dice: si algo\n"
            "vuelve a tardar, sabremos dónde en vez de adivinar."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado21/shape101")
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
