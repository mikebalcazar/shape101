"""El mandadero, prestado a nest101  ·  SÓLO EN LA RAMA `claude/mandado-nest101`.

**El `recado.py` de `main` no se tocó.** Actions hace `checkout` de la rama que
dispara el push, así que esta versión corre únicamente cuando el chat de
nest101 crea `claude/recado-nest101-*`. El mandadero de shape101 sigue siendo
el de `main`, con su `recado.json`, intacto.

Por qué existe: el conector de GitHub del chat da 403 en `.github/workflows/` y
manda cada archivo entero desde su contexto, así que no puede ni tocar el flujo
ni reescribir `ui/app.js` (150 KB) o `verificar.py` (50 KB). Un corredor con
token sí. Mike lo autorizó.

## Este mandado (el quinto)

#108 · el instrumental de la puerta de licencia
  La 0.19.3 ya dice por qué no abre, y lo que dijo en la máquina de Mike no
  cuadraba: `ERR_FAILED (-2)` y, un milisegundo después, «Object has been
  destroyed». Medido desde el chat: esa misma dirección abre perfecto en su
  Chrome, en su máquina, en ese momento. O sea que no es la red.

  Esta tanda apunta lo que falta para saberlo —si el proceso de la ventana se
  cae y con qué motivo, y si la suite contesta desde el proceso principal sin
  ventana de por medio— y arregla el error de la pantalla de fallo. De paso
  intenta otra vez con una sesión limpia, que puede ser el arreglo entero.

Medido en el chat: `verificar.py` TODO OK, `pruebas/licencia.mjs` 53 de 53 y
`pruebas/arranque.mjs` 18 de 18 con Electron de verdad. Si algo falla aquí, no
se empuja nada y el aviso queda en `claude/recado-fallo` de shape101.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
REPO = "nest101"
PARCHES = ["build/108-instrumental.patch"]
APLICADORES: list[str] = []
# Lo que el parche TIENE que haber dejado.
SENAS = [
    ("electron/licencia.js", "function probarRed(", "la prueba de red sin ventana"),
    ("electron/licencia.js", "render-process-gone", "el motivo de que se caiga la ventana"),
    ("electron/licencia.js", "function unIntento(", "los dos intentos"),
    ("electron/licencia-nucleo.js", "Tu conexión está bien",
     "el aviso que ya no culpa a la red cuando la red va"),
    ("claude/notas-0.19.4.txt", "sesión limpia", "las notas de la 0.19.4"),
]
# Y lo que tiene que haber DESAPARECIDO: la llamada que reventaba.
NO_DEBE = [
    ("electron/licencia.js", "if (!v.isDestroyed()) v.loadURL(pantallaDeFallo",
     "la llamada que comprobaba la ventana y no su contenido"),
]
LIBRERIAS = [
    "fastapi", "uvicorn", "ezdxf", "openpyxl", "reportlab==4.4.10", "pillow",
    "numpy", "opencv-python-headless", "anthropic", "pypdfium2",
    "python-multipart", "truststore", "httpx",
]
COMMIT = """Saber por qué se muere la ventana de activación (#108)

La 0.19.3 ya dice por qué no abre. En la máquina de Mike dijo esto:

    ERR_FAILED (-2) loading 'https://…/licencias/entrar?…'
    TypeError: Object has been destroyed      ← 1 ms después

Y no cuadra. Medido desde el chat, con su propio navegador: esa MISMA dirección
abre perfecto en su Chrome, en su máquina, en ese momento. Así que no es la red,
ni el proxy, ni la VPN —que es lo que decía el aviso—: lo que se muere es la
ventana. Dos detalles del registro lo confirman: no hubo `did-fail-load` (la
promesa se rechazó por el camino genérico de Electron, el de «la navegación se
detuvo sin llegar») y, un milisegundo después, el contenido de la ventana ya
estaba destruido.

Hasta ahí llega lo que se puede deducir. Lo demás se mide:

· `render-process-gone` con su `reason` y su `exitCode`. Si un antivirus de
  empresa está matando el proceso de la ventana, se ve ahí y en ningún otro
  lado: dice «killed», «crashed», «launch-failed».
· Una llamada a la suite DESDE EL PROCESO PRINCIPAL, con `net.request`, sin
  ventana de por medio. Separa las dos cosas que hasta ahora se confundían:
  «esta computadora no llega a la suite» y «la ventana no pudo enseñarla». El
  resultado va al registro y también al aviso.
· Cada paso de la navegación con su hora: empieza a cargar, deja de cargar,
  dom listo, se destruye el contenido, se cierra la ventana.

Y dos arreglos que salen del mismo reporte:

· El TypeError. Se comprobaba `v.isDestroyed()` —la ventana— y el que estaba
  muerto era su CONTENIDO. Ahora se comprueban los dos y además va dentro de un
  try, porque entre la comprobación y la llamada puede morirse.
· Si la prueba sin ventana dice que la suite sí contestó, el aviso ya no manda
  al taller a revisar su proxy. Dice lo que se midió.

De paso, un segundo intento con una sesión limpia, sin la partición guardada. Si
lo que estorbaba era `Partitions/suite101` —cosa que pasa—, con esto abre y el
taller ni se entera. Cuesta volver a escribir la contraseña una vez; vale más
eso que no abrir.

Medido antes de empujar: verificar.py TODO OK, pruebas/licencia.mjs 53 de 53, y
pruebas/arranque.mjs 18 de 18 con Electron de verdad (esa última corre a mano:
pide pantalla, y el corredor no tiene).
"""

lineas: list[str] = []


def anotar(t: str) -> None:
    print(t, flush=True)
    lineas.append(t)


def _sin_secretos(t: str) -> str:
    v = os.environ.get("TOKEN_SHAPE101")
    return t.replace(v, "***") if v else t


def correr(orden, cwd=None, entorno=None) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True, env=entorno)
    if h.returncode != 0:
        raise RuntimeError(_sin_secretos(
            f"falló {' '.join(orden[:3])}: {(h.stdout + h.stderr).strip()[-1200:]}"))
    return h.stdout


def main() -> int:
    t = os.environ.get("TOKEN_SHAPE101")
    if not t:
        print("falta TOKEN_SHAPE101")
        return 1

    tmp = pathlib.Path("/tmp/mandado-nest101")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    repo = tmp / REPO

    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t}@github.com/{DUENO}/{REPO}", str(repo)])
    anotar(f"{REPO} clonado")
    correr(["git", "config", "user.name", "nest101 (mandado desde shape101)"], cwd=repo)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=repo)

    # 1 · las librerías primero: medir sin ellas fue lo que tiró el mandado 108.
    correr([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    correr([sys.executable, "-m", "pip", "install", "--quiet"] + LIBRERIAS)
    anotar(f"{len(LIBRERIAS)} librerías instaladas")

    # 2 · los parches
    for p in PARCHES:
        if not (repo / p).exists():
            anotar(f"{p} no está: se da por aplicado")
            continue
        correr(["git", "apply", "--check", p], cwd=repo)
        correr(["git", "apply", p], cwd=repo)
        correr(["git", "rm", "-q", p], cwd=repo)
        anotar(f"{p} aplicado y retirado")

    for archivo, sena, que in SENAS:
        if sena not in (repo / archivo).read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo} no quedó con {que}")
    for archivo, sena, que in NO_DEBE:
        if sena in (repo / archivo).read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo} todavía trae {que}")
    anotar("el parche dejó lo que debía, y se llevó lo que debía")

    # el JavaScript tiene que seguir siendo JavaScript: `node --check` cuesta
    # un parpadeo y caza un paréntesis mal puesto antes de publicar nada
    for js in ("electron/licencia.js", "electron/licencia-nucleo.js", "electron/main.js"):
        correr(["node", "--check", js], cwd=repo)
    anotar("los tres archivos de la puerta pasan node --check")

    for a in APLICADORES:
        if (repo / a).exists():
            anotar(correr([sys.executable, a], cwd=repo).strip())
            correr(["git", "rm", "-q", a], cwd=repo)

    # 3 · medir, que es lo que autoriza a empujar
    entorno = dict(os.environ, PYTHONUTF8="1")
    salida = correr([sys.executable, "verificar.py"], cwd=repo, entorno=entorno)
    if "TODO OK" not in salida:
        raise RuntimeError("verificar.py no acabó en TODO OK")
    anotar("verificar.py: TODO OK")

    salida = correr(["node", "pruebas/licencia.mjs"], cwd=repo, entorno=entorno)
    if "todo bien" not in salida:
        raise RuntimeError("pruebas/licencia.mjs no acabó en «todo bien»")
    anotar("pruebas/licencia.mjs: " + salida.strip().splitlines()[-1])
    # `pruebas/arranque.mjs` necesita Electron con pantalla: se midió en el chat
    # (18 de 18) y viaja en el repo para poder repetirla.

    # 4 · empujar
    if not correr(["git", "status", "--porcelain"], cwd=repo).strip():
        anotar("no había nada que cambiar")
        return 0
    (repo / "claude" / "ultimo-mandado.md").write_text(
        "# Último mandado\n\n*Lo escribe el mandadero de shape101 al correr en "
        "Actions, prestado a nest101.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n\n"
        "```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=repo)
    correr(["git", "commit", "-m", COMMIT.rstrip()], cwd=repo)
    correr(["git", "push", "origin", "HEAD:main"], cwd=repo)
    anotar("empujado a main de nest101")
    return 0


def avisar_del_fracaso(error: str) -> None:
    """El aviso va a shape101, que es donde este corredor sí puede escribir."""
    t = os.environ.get("TOKEN_SHAPE101")
    tmp = pathlib.Path("/tmp/aviso-shape101")
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        correr(["git", "clone", "--depth", "1",
                f"https://x-access-token:{t}@github.com/{DUENO}/shape101", str(tmp)])
        correr(["git", "checkout", "-B", "claude/recado-fallo"], cwd=tmp)
        correr(["git", "config", "user.name", "shape101 (recado)"], cwd=tmp)
        correr(["git", "config", "user.email", "mike@forespot.com"], cwd=tmp)
        (tmp / "claude").mkdir(exist_ok=True)
        (tmp / "claude" / "ultimo-recado.md").write_text(
            "# Último recado · FALLÓ (mandado de nest101)\n\n"
            f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n\n"
            "```\n" + "\n".join(lineas) + "\n\nERROR: " + error + "\n```\n",
            encoding="utf-8")
        correr(["git", "add", "claude/ultimo-recado.md"], cwd=tmp)
        correr(["git", "commit", "-m", "mandado de nest101 fallido: dónde se rompió"], cwd=tmp)
        correr(["git", "push", "-f", "origin", "claude/recado-fallo"], cwd=tmp)
        print("aviso dejado en claude/recado-fallo de shape101")
    except Exception as e2:
        print(f"ni el aviso del fracaso se pudo escribir: {_sin_secretos(str(e2))}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        d = _sin_secretos(f"{type(e).__name__}: {e}")
        print(f"el mandado falló: {d}")
        avisar_del_fracaso(d)
        sys.exit(1)
