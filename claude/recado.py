"""El mandadero, prestado a nest101  ·  SÓLO EN LA RAMA `claude/mandado-nest101`.

**El `recado.py` de `main` no se tocó.** Actions hace `checkout` de la rama que
dispara el push, así que esta versión corre únicamente cuando el chat de
nest101 crea `claude/recado-nest101-*`. El mandadero de shape101 sigue siendo
el de `main`, con su `recado.json`, intacto.

Por qué existe: el conector de GitHub del chat da 403 en `.github/workflows/` y
manda cada archivo entero desde su contexto, así que no puede ni tocar el flujo
ni reescribir `ui/app.js` (150 KB) o `verificar.py` (50 KB). Un corredor con
token sí. Mike lo autorizó.

## Este mandado (el tercero)

Todo lo que viaja ya está dentro de nest101, en `build/`; aquí se aplica, se
mide y se empuja. Los seis parches se midieron en el chat sobre una copia
limpia de `main`: aplican sin ruido y dejan el árbol idéntico al medido.

#105 · el menú de Ajustes
  Mike: «no hay ningún lugar donde pueda gestionar el key de Claude. Necesito
  un menú de configuración… la licencia, el key, el idioma, las unidades».

#106 · el arranque que ya no se calla
  Mike: «nest 0.19.2 no abre. Se ve que apenas aparece una ventana pero muy
  rápido y desaparece». Su `arranque.log` acaba en «Activando tu licencia».

Si `verificar.py` o `pruebas/licencia.mjs` fallan, no se empuja nada y el
aviso queda en `claude/recado-fallo` de shape101.
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
PARCHES = [
    "build/105-a-pantalla.patch",
    "build/105-b-diccionario.patch",
    "build/105-c-medicion.patch",
    "build/105-d-motor.patch",
    "build/106-a-puerta.patch",
    "build/106-b-pruebas.patch",
]
APLICADORES: list[str] = []
# Lo que cada parche TIENE que haber dejado. Se mide en el texto del archivo,
# que es barato y caza un parche aplicado a medias antes de empujar nada.
SENAS = [
    ("ui/app.js", 'modal("Ajustes"', "el menú de Ajustes"),
    ("ui/app.js", "const UNI = {", "las unidades"),
    ("server.py", "/api/llave/probar", "probar la llave"),
    ("core/taller.py", 'UNIDADES = ("mm", "cm", "pulg")', "las unidades en el perfil"),
    ("electron/licencia-nucleo.js", "function noAbrio(", "por qué no abrió"),
    ("electron/preload.js", "licenciaCambiar:", "la licencia asomada a la ventana"),
    ("pruebas/ajustes.py", "sync_playwright", "la prueba del menú"),
    ("pruebas/arranque.mjs", "se cerró solo a media prueba", "la prueba del arranque"),
    ("claude/notas-0.19.3.txt", "ya no se cierra en silencio", "las notas de la 0.19.3"),
]
# Y lo que tiene que haber DESAPARECIDO: es la mitad que se olvida.
NO_DEBE = [
    ("electron/main.js", "no-proxy-server",
     "el proxy apagado para todo, que es lo que dejaba sin salida a la activación"),
    ("ui/app.js", "window.t101",
     "el puente con el nombre equivocado, que nunca existió"),
]
LIBRERIAS = [
    "fastapi", "uvicorn", "ezdxf", "openpyxl", "reportlab==4.4.10", "pillow",
    "numpy", "opencv-python-headless", "anthropic", "pypdfium2",
    "python-multipart", "truststore", "httpx",
]
COMMIT = """Un solo menú de Ajustes (#105) y un arranque que ya no se cierra callado (#106)

#106 · «nest 0.19.2 no abre»
  Mike, 11-oct: «se ve que apenas aparece una ventana pero muy rápido y
  desaparece». Su arranque.log acaba en «Activando tu licencia» y ahí se corta.
  Lo que pasaba, en tres fallas encadenadas:

  1. La ventana de activación no cargaba y el código la DESTRUÍA. Destruir
     dispara `closed`, que resolvía primero y con el motivo equivocado
     —«cancelado», aunque nadie cancelara—, y arriba sólo había diálogo para
     «sin_red». Resultado: el programa se cerraba sin una palabra. Una falla
     que no se puede ni reportar.
  2. `no-proxy-server` apagaba el proxy del sistema para TODO. Se puso para
     que el backend local no se bloqueara —y para eso basta la excepción de
     loopback, que se queda—, pero de paso dejaba sin salida a la pantalla de
     activación en una máquina que sale a internet por proxy o VPN.
  3. El `icon` de esa ventana apuntaba a `build/icon.ico`, que no viaja dentro
     del paquete: `files` empaqueta sólo `electron/**`. Medido con Electron:
     no revienta, pero tampoco pinta nada. Se quita la línea.

  Ahora: la ventana se queda abierta enseñando el motivo con su código crudo,
  cada manera de no pasar la puerta tiene su frase (`noAbrio`), todo queda en
  arranque.log, cerrar la última ventana no mata el arranque mientras la
  puerta está abierta, y una excepción suelta se enseña en vez de morir muda.

  pruebas/arranque.mjs lo reproduce con Electron de verdad: con el código de
  la 0.19.2 no imprime ni una línea —se muere a media prueba, igual que en la
  máquina de Mike—; con el arreglo, 15 de 15. pruebas/licencia.mjs pasa de 39
  a 50.

#105 · un solo lugar para lo del equipo
  Mike: «no hay ningún lugar donde pueda gestionar el key de Claude. Necesito
  un menú de configuración donde se puedan ajustar los varios parámetros de la
  aplicación, incluida la licencia con la que está trabajando, el key, el
  idioma, las unidades».

  La llave SÍ existía —pestaña Estándar, bajo «Leer plano», desde #040— y la
  licencia también —menú nativo de Ayuda, desde #100—. Que el dueño del
  programa no las encontrara es el reporte: estaban donde se usan y no había
  un lugar donde se administren. El engrane abre «Ajustes» con siete
  secciones: licencia de este equipo (con qué cuenta, hasta cuándo, cambiarla),
  llave de Claude (pegar, PROBAR, quitar, y los pasos para sacarla), idioma,
  unidades, logotipo, actualizaciones y carpeta del taller.

  Probar la llave le pregunta a Anthropic con el mismo modelo que lee los
  planos. Es lo que le faltaba a Mike: su llave era válida pero no estaba
  ligada a un workspace, y el programa sólo sabía decir «Anthropic no aceptó
  la llave». Ahora ese caso se explica y dice cómo hacer una que sirva.

  Y «Quitar» ahora quita de verdad: `taller.llave()` mira el entorno antes que
  el archivo, así que al borrar el archivo la llave vieja seguía puesta en el
  proceso y no se iba hasta reiniciar. Lo cazó la prueba del navegador.

unidades (sólo de lectura)
  Las cotas del dibujo y las medidas de la parrilla se leen en milímetros,
  centímetros o pulgadas —en quebrados de dieciseisavo, como las cintas—. La
  lista de corte, los planos, el Excel y el DXF se quedan en milímetros a
  propósito: son los que van a la máquina y al carpintero. Medido: el mismo
  mueble despiezado en pulgadas da exactamente el mismo corte.

Medido por el corredor antes de empujar: verificar.py TODO OK y
pruebas/licencia.mjs 50 de 50. Llega por el mandadero de shape101 por lo de
siempre: el conector da 403 en .github/workflows/ y manda los archivos enteros.
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

    # 1 · los parches
    for p in PARCHES:
        if not (repo / p).exists():
            anotar(f"{p} no está: se da por aplicado")
            continue
        correr(["git", "apply", "--check", p], cwd=repo)
        correr(["git", "apply", p], cwd=repo)
        correr(["git", "rm", "-q", p], cwd=repo)
        anotar(f"{p} aplicado y retirado")

    # lo que cada parche tenía que dejar —y lo que tenía que llevarse
    for archivo, sena, que in SENAS:
        if sena not in (repo / archivo).read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo} no quedó con {que}")
    for archivo, sena, que in NO_DEBE:
        if sena in (repo / archivo).read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo} todavía trae {que}")
    anotar(f"los {len(PARCHES)} parches dejaron lo que debían, y se llevaron lo que debían")

    # 2 · los aplicadores (esta vez no hay)
    for a in APLICADORES:
        if (repo / a).exists():
            anotar(correr([sys.executable, a], cwd=repo).strip())
            correr(["git", "rm", "-q", a], cwd=repo)

    # 3 · medir, que es lo que autoriza a empujar
    correr([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    correr([sys.executable, "-m", "pip", "install", "--quiet"] + LIBRERIAS)
    anotar(f"{len(LIBRERIAS)} librerías instaladas")

    entorno = dict(os.environ, PYTHONUTF8="1")
    salida = correr([sys.executable, "verificar.py"], cwd=repo, entorno=entorno)
    if "TODO OK" not in salida:
        raise RuntimeError("verificar.py no acabó en TODO OK")
    anotar("verificar.py: TODO OK")

    salida = correr(["node", "pruebas/licencia.mjs"], cwd=repo, entorno=entorno)
    if "todo bien" not in salida:
        raise RuntimeError("pruebas/licencia.mjs no acabó en «todo bien»")
    anotar("pruebas/licencia.mjs: " + salida.strip().splitlines()[-1])
    # `pruebas/arranque.mjs` y `pruebas/ajustes.py` NO se corren aquí: piden
    # Electron con pantalla y un Chromium de playwright, que este corredor no
    # tiene. Se midieron en el chat —15 de 15 y TODO OK— y viajan en el repo
    # para que se puedan volver a correr.

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
