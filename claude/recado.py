"""El mandadero, prestado a nest101  ·  SÓLO EN LA RAMA `claude/mandado-nest101`.

**El `recado.py` de `main` no se tocó.** Actions hace `checkout` de la rama que
dispara el push, así que esta versión corre únicamente cuando el chat de
nest101 crea `claude/recado-nest101-*`. El mandadero de shape101 sigue siendo
el de `main`, con su `recado.json`, intacto.

Por qué existe: el conector de GitHub del chat da 403 en `.github/workflows/` y
manda cada archivo entero desde su contexto, así que no puede ni tocar el flujo
ni reescribir `ui/app.js` (140 KB) o `verificar.py` (46 KB). Un corredor con
token sí. Mike lo autorizó. El primer mandado dejó a nest101 publicando sola
—`apps.yml` se dispara con `claude/publicar-<version>`, como draw101— y la
0.19.0 salió por ahí.

## Este mandado (el segundo)

Todo lo que viaja ya está dentro de nest101; aquí sólo se aplica y se mide.

1. `claude/100-licencia-robusta.patch` — **#100**, el arreglo que importa de
   esta tanda: un 429, un 408, un 401 de proxy, un 404 o una página de «acceso
   bloqueado» ya no le borran la licencia al taller. Sólo un «no» con motivo
   conocido cuenta como «la suite dice que no». Y Ayuda → «Licencia de este
   equipo…» para ver con qué cuenta quedó y cambiarla sin borrar archivos a mano.
2. `build/apps-notas-desde-archivo.patch` — las notas de la release salen de
   `claude/notas-<version>.txt` cuando el disparo es por rama. La 0.19.0 salió
   con «Compilada y verificada por el chat» porque por rama no hay formulario, y
   esas notas son lo que el taller lee en el aviso de actualizar.
3. `claude/aplicar_103_pruebas.py` — las ocho comprobaciones de #103 se mudan
   adentro de `verificar.py`. Fuera de él no corren en el armado, y una
   comprobación que no corre donde se publica es media comprobación.

Y se mide antes de empujar: `verificar.py` TODO OK y `pruebas/licencia.mjs`
39 de 39. Si cualquiera de los dos falla, no se empuja nada y el aviso queda en
`claude/recado-fallo` de shape101.

Medido en el chat sobre una copia de `main` antes de mandar esto: los dos
parches aplican limpios, `verificar.py` acaba en TODO OK con el bloque de #103
dentro, y las 39 de licencia pasan.
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
PARCHES = ["claude/100-licencia-robusta.patch", "build/apps-notas-desde-archivo.patch"]
APLICADORES = ["claude/aplicar_103_pruebas.py"]
LIBRERIAS = [
    "fastapi", "uvicorn", "ezdxf", "openpyxl", "reportlab==4.4.10", "pillow",
    "numpy", "opencv-python-headless", "anthropic", "pypdfium2",
    "python-multipart", "truststore",
]
COMMIT = """La licencia aguanta el mal rato (#100), las notas salen del repo y #103 se mide adentro

#100 · un mal rato del camino ya no le quita la licencia al taller
  El latido contaba como «la suite dice que no» todo lo que no fuera un 5xx, y
  medidas una por una, cinco situaciones normales borraban la licencia que ya
  estaba guardada en el equipo: un 429 con tres equipos del taller abriendo a la
  vez, un 408, un 401 del proxy de la empresa, un 404 el día que cambie una
  dirección, y un 200 con la página de «acceso bloqueado» de un proxy.

  Ahora es lista blanca: la suite dice que no cuando contesta un JSON con un
  motivo conocido —sin_pago, suspendida, maquina_desconocida,
  licencia_desconocida, token_invalido— y todo lo demás es «no se pudo llegar»,
  que no toca lo guardado. Un motivo que la suite invente mañana cae del lado
  seguro: el token trae su propio `hasta` firmado, así que se cierra solo cuando
  venza; cerrarle a un taller que sí pagó no se arregla solo.

  Y Ayuda → «Licencia de este equipo…»: con qué cuenta quedó, qué licencia,
  hasta cuándo con los días que faltan, y el equipo con la huella cortada. Si
  está activa ofrece «Cambiar de cuenta…», que pregunta otra vez antes de
  cerrar el programa y liberar el lugar. Antes, la única forma de pasar la
  licencia a otra cuenta era borrar a mano un archivo dentro de AppData.

  pruebas/licencia.mjs pasa de 20 a 39 comprobaciones. Los seis fallos del
  camino se miden por las DOS mitades: que se llamen «no se pudo llegar» y que
  el archivo de licencia siga ahí — es el llamador quien borra al oír «vencida».

notas de la release desde el repositorio
  La 0.19.0 salió con «Compilada y verificada por el chat»: disparado por rama
  no hay formulario donde escribirlas. Ahora el flujo lee
  `claude/notas-<version>.txt`, un renglón por cambio. Es lo que el taller lee
  en el aviso de actualizar, así que importa que diga algo.

#103 se mide donde se publica
  Las ocho comprobaciones del zoclo vivían en `claude/comprobar_103.py`, fuera
  de `verificar.py`, y por tanto no corrían en el armado. Se mudan adentro y el
  archivo suelto se retira: dos verdades sobre lo mismo es una de más.

Medido por el corredor antes de empujar: verificar.py TODO OK y
pruebas/licencia.mjs 39 de 39. Llega por el mandadero de shape101 por lo de
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

    # lo que cada parche tenía que dejar, comprobado en el texto
    nucleo = (repo / "electron/licencia-nucleo.js").read_text(encoding="utf-8")
    if "function esUnNo(" not in nucleo or "function resumen(" not in nucleo:
        raise RuntimeError("licencia-nucleo.js no quedó con esUnNo() y resumen()")
    flujo = (repo / ".github/workflows/apps.yml").read_text(encoding="utf-8")
    if 'claude/notas-{os.environ[' not in flujo:
        raise RuntimeError("apps.yml no quedó leyendo las notas del repositorio")
    anotar("los dos parches dejaron lo que debían")

    # 2 · los aplicadores
    for a in APLICADORES:
        if (repo / a).exists():
            anotar(correr([sys.executable, a], cwd=repo).strip())
            correr(["git", "rm", "-q", a], cwd=repo)
        else:
            anotar(f"{a} no está: se da por aplicado")
    anotar("andamios retirados")

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
