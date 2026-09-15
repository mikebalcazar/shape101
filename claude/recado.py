"""El mandadero · recado 8: la entidad Cuerpo y el enchufe del 3D (segundo intento).

El recado 6 aplicó bien los dos parches y **se cayó comprobándolos**: pedía
importar `core/solido/rutas.py`, que necesita `fastapi`, y el Python del
armador no lo trae instalado —la app corre con el Python empotrado, no con
éste—. Como el recado se detiene ante cualquier fallo, no empujó nada.

La lección no es «quitar la comprobación»: es **comprobar con lo que hay a la
mano**. Aquí se comprueba el texto de los archivos y se importa sólo
`core/entidades.py`, que no depende de nada de fuera. Que las rutas funcionan
ya está medido en otra parte: las tres pruebas `t020`, `t021` y `t022` las
ejercitan de punta a punta, y ésas corren en el armado, donde sí están las
dependencias.

Qué mete, igual que el recado 6:

1. **La entidad `Cuerpo`** en `core/entidades.py`: un sólido 3D que no guarda
   geometría sino **cómo se hizo**. Se llama `Cuerpo` y no `Solido` porque
   `Solido` ya existe ahí —es el SOLID del DXF, un relleno plano—.
2. **El enchufe de las rutas del 3D** en `server.py`. No carga el kernel:
   `rutas.py` lo importa dentro de cada función, porque tarda casi tres
   segundos y quien sólo dibuja en 2D no tiene por qué esperarlos.
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
    tmp = pathlib.Path("/tmp/recado8")
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

    # Comprobar con lo que hay a la mano. `core/entidades.py` no depende de
    # nada de fuera, así que se puede importar de verdad. Lo demás se comprueba
    # leyendo el texto: el Python de este corredor no tiene fastapi, y pedirle
    # que importe las rutas fue justo lo que tumbó el intento anterior.
    salida = correr([sys.executable, "-c",
                     "import os, sys, tempfile; os.environ['HOME']=tempfile.mkdtemp();"
                     "sys.path.insert(0, '.');"
                     "from core import entidades as E;"
                     "c = E.de_dict({'tipo': 'cuerpo', 'operaciones': [{'op': 'boceto',"
                     " 'entidades': [{'tipo': 'polilinea', 'puntos': [[0,0,0],[900,0,0],[900,600,0]]}]}]});"
                     "print('la entidad Cuerpo se relee y su caja mide', c.caja())"], cwd=shape)
    for l in salida.strip().splitlines():
        anotar(l)

    rutas_py = (shape / "core" / "solido" / "rutas.py").read_text(encoding="utf-8")
    faltan = [r for r in ("/extruir", "/{id_}/malla", "/{id_}/empujar-cara",
                          "/{id_}/mover-punto", "/{id_}/exportar")
              if r not in rutas_py]
    if faltan:
        raise RuntimeError(f"a rutas.py le faltan: {faltan}")
    anotar("las cinco rutas del 3D están escritas en core/solido/rutas.py")
    if "rutas_3d.enchufar" not in srv.read_text(encoding="utf-8"):
        raise RuntimeError("server.py no quedó enchufado")
    anotar("server.py quedó enchufado al documento abierto")

    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: la entidad Cuerpo y el enchufe del 3D (segundo intento)\n\n```\n"
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
            "El intento anterior aplicó bien los parches y se cayó comprobándolos: pedía\n"
            "importar las rutas, que necesitan fastapi, y el Python del corredor no lo trae.\n"
            "Ahora se comprueba con lo que hay a la mano; que las rutas funcionen ya lo miden\n"
            "t020, t021 y t022, que corren donde sí están las dependencias."],
           cwd=shape)
    correr(["git", "push", "-f", "origin", RAMA], cwd=shape)
    correr(["git", "push", "origin", f"{RAMA}:main"], cwd=shape)
    anotar(f"empujada {RAMA} y llevada a main")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado8/shape101")
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
