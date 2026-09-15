"""El mandadero · recado 6: enchufar el 3D a los dos archivos grandes.

`core/entidades.py` y `server.py` son demasiado grandes para reescribirlos por
el conector del chat, y lo que hay que cambiarles son cuatro líneas. Así que se
parchean aquí, con reemplazos que **comprueban cuántas veces debía aparecer el
texto viejo**: un parche aplicado a medias es peor que uno no aplicado.

Qué se les mete:

1. **La entidad `Cuerpo`** en `core/entidades.py`. Un sólido 3D que no guarda
   geometría sino **cómo se hizo**: el boceto, la extrusión, los barrenos, las
   caras jaladas. Guardar la malla sería más simple y serviría de poco: en
   cuanto se mueve un punto del contorno habría que deformarla, y un barreno
   hecho después dejaría de ser redondo.

   Se llama `Cuerpo` y no `Solido` porque `Solido` **ya existe** en ese
   archivo: es el SOLID del DXF, un relleno plano. Dos cosas distintas con el
   mismo nombre en el mismo archivo es un error esperando su turno.

2. **El enchufe de las rutas del 3D** en `server.py`. Importarlo ahí no carga
   el kernel: `core/solido/rutas.py` lo importa dentro de cada función, porque
   tarda casi tres segundos (medido en P1) y quien sólo va a dibujar en 2D no
   tiene por qué esperarlos cada vez que abre la app.

Todo esto ya se probó en la máquina del chat contra la aplicación entera:
extruir un tablero de 900×600×18 da 9 720 000 mm³, jalar la cara de arriba
12 mm da 16 200 000, mover una esquina a 1200 da 18 900 000 —el volumen del
trapecio, no el del rectángulo— y `/api/salud` del 2D sigue contestando.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA = "claude/enchufar-el-3d"

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
    n = texto.count(viejo)
    if n != 1:
        raise RuntimeError(f"{donde}: «{viejo[:50]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo, 1)


CUERPO = '''@dataclass
class Cuerpo(Entidad):
    """Un sólido 3D. **No guarda geometría: guarda cómo se hizo.**

    Adentro va la lista de operaciones —boceto, extruir, barreno, redondeo,
    cara jalada— y el sólido se reconstruye a partir de ella. Guardar la malla
    sería más simple y serviría de poco: en cuanto se mueve un punto del
    contorno habría que deformarla, y un barreno hecho después dejaría de ser
    redondo. Rehaciendo la pieza, sigue siéndolo.

    Ojo con el nombre: `Solido` ya existe en este archivo y es otra cosa —el
    SOLID del DXF, un relleno plano—. Éste es el cuerpo de tres dimensiones.
    """
    operaciones: list = field(default_factory=list)
    tipo: str = field(init=False, default="cuerpo")

    def caja(self):
        """La sombra en planta, para encuadrar la vista. Se saca del contorno
        del boceto y no del sólido: pedirle la caja al kernel obligaría a
        regenerar la pieza cada vez que alguien encuadra."""
        for op in self.operaciones:
            if op.get("op") != "boceto":
                continue
            pts = []
            for e in op.get("entidades") or []:
                t = e.get("tipo")
                if t == "polilinea":
                    pts += [[p[0], p[1]] for p in (e.get("puntos") or [])]
                elif t in ("circulo", "arco"):
                    c, rad = e.get("centro") or [0, 0], e.get("radio") or 0
                    pts += [[c[0] - rad, c[1] - rad], [c[0] + rad, c[1] + rad]]
                elif t == "linea":
                    pts += [e.get("p1", [0, 0])[:2], e.get("p2", [0, 0])[:2]]
            return _caja_de_puntos(pts)
        return None


# --- Texto -----------------------------------------------------------------
'''

ENCHUFE = '''S = _Activa()

# --- El 3D -----------------------------------------------------------------
# Las rutas de sólidos viven en su propio módulo: son otro oficio y, sobre
# todo, el kernel tarda casi tres segundos en cargar. Importarlas aquí no lo
# carga —`core/solido/rutas.py` lo importa dentro de cada función—, así que la
# app sigue abriendo igual de rápido para quien sólo va a dibujar en 2D.
from core.solido import rutas as rutas_3d  # noqa: E402

rutas_3d.enchufar(lambda: S.doc)
app.include_router(rutas_3d.router)
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado6")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    ent = shape / "core" / "entidades.py"
    texto = ent.read_text(encoding="utf-8")
    if "class Cuerpo" in texto:
        anotar("core/entidades.py ya traía el Cuerpo: no se toca")
    else:
        texto = cambiar(texto, "# --- Texto -----------------------------------------------------------------\n",
                        CUERPO, "entidades.py")
        texto = cambiar(texto, '    "solido": Solido,\n',
                        '    "solido": Solido,\n    "cuerpo": Cuerpo,\n', "entidades.py (registro)")
        ent.write_text(texto, encoding="utf-8")
        anotar("core/entidades.py: entidad Cuerpo agregada y registrada")

    srv = shape / "server.py"
    texto = srv.read_text(encoding="utf-8")
    if "rutas_3d" in texto:
        anotar("server.py ya traía el enchufe: no se toca")
    else:
        srv.write_text(cambiar(texto, "S = _Activa()\n", ENCHUFE, "server.py"), encoding="utf-8")
        anotar("server.py: las rutas del 3D quedan enchufadas al documento abierto")

    # Comprobar antes de empujar: que el programa importe y que las rutas estén
    salida = correr([sys.executable, "-c",
                     "import os, sys, tempfile; os.environ['HOME']=tempfile.mkdtemp();"
                     "sys.path.insert(0, '.');"
                     "from core import entidades as E;"
                     "c = E.de_dict({'tipo': 'cuerpo', 'operaciones': []});"
                     "print('la entidad Cuerpo vive y se relee:', type(c).__name__);"
                     "from core.solido import rutas as R;"
                     "print('rutas del 3D:', len(R.router.routes))"], cwd=shape)
    for l in salida.strip().splitlines():
        anotar(l)

    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: enchufar el 3D a entidades.py y server.py\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "La entidad Cuerpo y el enchufe de las rutas del 3D\n\n"
            "Un cuerpo no guarda geometría: guarda cómo se hizo. Guardar la malla sería más\n"
            "simple y serviría de poco, porque al mover un punto del contorno habría que\n"
            "deformarla y un barreno hecho después dejaría de ser redondo.\n\n"
            "Se llama Cuerpo y no Solido porque Solido ya existe en ese archivo: es el SOLID\n"
            "del DXF, un relleno plano. Dos cosas distintas con el mismo nombre en el mismo\n"
            "archivo es un error esperando su turno.\n\n"
            "El enchufe en server.py no carga el kernel: rutas.py lo importa dentro de cada\n"
            "función, porque tarda casi tres segundos y quien sólo dibuja en 2D no tiene por\n"
            "qué esperarlos al abrir la app.\n\n"
            "Probado contra la aplicación entera antes de mandarlo: extruir 900×600×18 da\n"
            "9 720 000 mm³, jalar la cara de arriba 12 mm da 16 200 000, mover una esquina a\n"
            "1200 da 18 900 000 —el volumen del trapecio, no el del rectángulo— y /api/salud\n"
            "del 2D sigue contestando 200."],
           cwd=shape)
    correr(["git", "push", "-f", "origin", RAMA], cwd=shape)
    correr(["git", "push", "origin", f"{RAMA}:main"], cwd=shape)
    anotar(f"empujada {RAMA} y llevada a main")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado6/shape101")
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
