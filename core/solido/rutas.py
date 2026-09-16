"""Las rutas del 3D  ·  `/api/cuerpo/...`

Van en su propio módulo, no dentro de `server.py`, por dos razones:

1. `server.py` ya tiene casi dos mil líneas y es el 2D. El 3D no tiene por qué
   crecer ahí adentro.
2. **El kernel tarda casi tres segundos en cargar** (medido en la prueba de
   concepto, P1). Si `build123d` se importara al arrancar, la app tardaría eso
   de más en abrir aunque nadie vaya a modelar en 3D. Por eso aquí no hay ni un
   `import` del kernel arriba: se importan **dentro** de cada función, la
   primera vez que de verdad hacen falta.

El documento no se toca directo: `server.py` enchufa un buscador con
`enchufar()`. Así este módulo no sabe nada de sesiones ni de escritorios, y se
puede probar solo.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/cuerpo", tags=["3d"])

_doc_actual = None


def enchufar(buscador) -> None:
    """`buscador()` devuelve el documento abierto. Lo llama `server.py`."""
    global _doc_actual
    _doc_actual = buscador


def _doc():
    if _doc_actual is None:
        raise HTTPException(500, "las rutas del 3D no están enchufadas al documento")
    return _doc_actual()


def _cuerpo(id_: str):
    ent = _doc().entidades.get(id_)
    if ent is None:
        raise HTTPException(404, f"no existe la entidad {id_}")
    if ent.tipo != "cuerpo":
        raise HTTPException(400, f"{id_} no es un cuerpo, es un {ent.tipo}")
    return ent


def _malla(cuerpo):
    from core.solido import cuerpo as mod
    try:
        return mod.malla(cuerpo)
    except Exception as e:
        # El kernel habla en inglés y con nombres de clase. Aquí se contesta en
        # el idioma del taller, y el cuerpo se queda como estaba.
        raise HTTPException(400, f"no se pudo construir la pieza: {e}") from e


class Extruir(BaseModel):
    ids: list[str]
    mm: float


@router.post("/extruir")
def extruir(entrada: Extruir):
    """Un contorno cerrado del dibujo se levanta y se vuelve sólido."""
    from core.entidades import Cuerpo
    from core.solido import cuerpo as mod

    doc = _doc()
    entidades = []
    for id_ in entrada.ids:
        e = doc.entidades.get(id_)
        if e is None:
            raise HTTPException(404, f"no existe la entidad {id_}")
        entidades.append(e.a_dict())
    if not entidades:
        raise HTTPException(400, "elige primero el contorno que se va a levantar")
    try:
        ops = mod.ops_de_contorno(entidades, entrada.mm)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    nuevo = Cuerpo(operaciones=ops, capa=entidades[0].get("capa", "0"))
    with doc.transaccion("extruir"):
        doc.agregar(nuevo)
    return _malla(nuevo)


@router.get("/lista")
def lista():
    """Los ids de las piezas del dibujo, para que la pantalla sepa qué pintar."""
    doc = _doc()
    return {"ids": [e.id for e in doc.entidades.values() if getattr(e, "tipo", "") == "cuerpo"]}


@router.get("/{id_}/malla")
def malla(id_: str):
    return _malla(_cuerpo(id_))


@router.get("/{id_}/referencias")
def referencias(id_: str):
    """Los nombres de caras y aristas, que es con lo que se le habla al
    historial. La pantalla los usa para enseñar qué está señalado."""
    from core.solido import cuerpo as mod
    c = _cuerpo(id_)
    return {"caras": mod.caras(c), "aristas": mod.aristas(c)}


class EmpujarCara(BaseModel):
    cara: str
    mm: float


@router.post("/{id_}/empujar-cara")
def empujar_cara(id_: str, entrada: EmpujarCara):
    """Jalar una cara: se mueve y la pieza se rehace. Positivo, hacia afuera.

    Si la operación deja una pieza imposible, el historial se queda como
    estaba. Vale más que no pase nada a que el modelo quede roto y el usuario
    no sepa en qué momento.
    """
    c = _cuerpo(id_)
    if entrada.mm == 0:
        return _malla(c)
    antes = list(c.operaciones)
    doc = _doc()
    with doc.transaccion("empujar cara"):
        doc.modificar(id_, {"operaciones": antes + [
            {"op": "empujar_cara", "cara": entrada.cara, "mm": float(entrada.mm)}]})
    try:
        return _malla(doc.entidades[id_])
    except HTTPException:
        with doc.transaccion("deshacer empujar cara"):
            doc.modificar(id_, {"operaciones": antes})
        raise


class MoverPunto(BaseModel):
    entidad: int = 0
    punto: int
    x: float
    y: float


@router.post("/{id_}/mover-punto")
def mover_punto(id_: str, entrada: MoverPunto):
    """Mover un vértice del contorno con el que nació la pieza.

    Todo lo que se hizo después —barrenos, redondeos, caras jaladas— se vuelve
    a aplicar solo. Eso es lo que se gana guardando cómo se hizo la pieza en vez
    de guardar la pieza.
    """
    from core.solido import cuerpo as mod
    c = _cuerpo(id_)
    antes = list(c.operaciones)
    try:
        nuevas = mod.mover_punto(antes, entrada.entidad, entrada.punto, entrada.x, entrada.y)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    doc = _doc()
    with doc.transaccion("mover punto"):
        doc.modificar(id_, {"operaciones": nuevas})
    try:
        return _malla(doc.entidades[id_])
    except HTTPException:
        with doc.transaccion("deshacer mover punto"):
            doc.modificar(id_, {"operaciones": antes})
        raise


class Exportar(BaseModel):
    formato: str
    ruta: str


@router.post("/{id_}/exportar")
def exportar(id_: str, entrada: Exportar):
    """STEP para que lo abra otro CAD; STL para imprimir."""
    import pathlib

    from build123d import export_step, export_stl

    from core.solido import cuerpo as mod

    c = _cuerpo(id_)
    reg = mod.regenerar(c)
    if reg.solido is None:
        raise HTTPException(400, "esta pieza no tiene sólido que exportar")
    destino = pathlib.Path(entrada.ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    formato = entrada.formato.lower()
    if formato == "step":
        export_step(reg.solido, str(destino))
    elif formato == "stl":
        export_stl(reg.solido, str(destino))
    else:
        raise HTTPException(400, f"no conozco el formato «{entrada.formato}»: step o stl")
    return {"ruta": str(destino), "bytes": destino.stat().st_size}
