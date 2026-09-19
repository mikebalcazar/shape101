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


def _factor_mm() -> float:
    """Milímetros por unidad del dibujo. El kernel trabaja en mm y toma los
    números tal cual; si el dibujo está en cm, todo lo que salga del kernel
    hacia fuera —volumen, STEP, STL— se corrige con esto. Lo que se pinta no:
    la pantalla usa los números del dibujo y la pieza va encima de su contorno."""
    from core.unidades import MM_POR_NOMBRE
    return float(MM_POR_NOMBRE.get(getattr(_doc(), "unidades", "mm"), 1.0))


def _a_mundo(plano: str, p):
    """(u, v, w) del kernel → (x, y, z) del mundo. Rotaciones, no espejos:
    XZ → (u, −w, v), hacia quien mira la Frontal; YZ → (w, u, v), hacia +X.
    `ui/planos.js` hace exactamente la misma cuenta."""
    u, v, w = p[0], p[1], p[2] if len(p) > 2 else 0.0
    if plano == "XZ":
        return [u, -w, v]
    if plano == "YZ":
        return [w, u, v]
    return [u, v, w]


def _del_mundo(plano: str, p):
    """(x, y, z) del mundo → (u, v, w) del kernel. La vuelta exacta de
    `_a_mundo`, y por eso se escriben juntas: si un día cambia una, la otra
    tiene que cambiar en el mismo renglón.

      XY: (x, y, z) → (x, y, z)
      XZ: (u, −w, v) = (x, y, z) → (x, z, −y)
      YZ: (w, u, v)  = (x, y, z) → (y, z, x)
    """
    x, y, z = p[0], p[1], p[2] if len(p) > 2 else 0.0
    if plano == "XZ":
        return [x, z, -y]
    if plano == "YZ":
        return [y, z, x]
    return [x, y, z]


def _al_mundo(m: dict, plano: str) -> dict:
    """La malla del kernel, ya en el mundo. El kernel siempre trabaja en XY:
    ahí los nombres de caras están probados. La pieza se rota al salir."""
    if plano in (None, "", "XY"):
        return m
    for cara in m.get("caras", []):
        v = cara.get("v") or []
        nuevo = []
        for k in range(0, len(v), 3):
            nuevo.extend(_a_mundo(plano, (v[k], v[k + 1], v[k + 2])))
        cara["v"] = nuevo
    m["aristas"] = [[_a_mundo(plano, p) for p in a] for a in m.get("aristas", [])]
    return m


def _rotar(solido, plano: str):
    """Lo mismo para el sólido que se exporta: la rotación que lleva el plano
    del kernel al del mundo."""
    from build123d import Axis
    if plano == "XZ":
        return solido.rotate(Axis.X, 90)
    if plano == "YZ":
        return solido.rotate(Axis((0, 0, 0), (1, 1, 1)), 120)
    return solido


def _malla(cuerpo):
    from core.solido import cuerpo as mod
    try:
        m = mod.malla(cuerpo)
    except Exception as e:
        # El kernel habla en inglés y con nombres de clase. Aquí se contesta en
        # el idioma del taller, y el cuerpo se queda como estaba.
        raise HTTPException(400, f"no se pudo construir la pieza: {e}") from e
    m = _al_mundo(m, getattr(cuerpo, "plano", "XY"))
    f = _factor_mm()
    if f != 1.0 and "volumen_mm3" in m:
        m["volumen_mm3"] = round(m["volumen_mm3"] * f ** 3, 1)
    m["unidades"] = getattr(_doc(), "unidades", "mm")
    return m


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

    import time
    t0 = time.perf_counter()
    nuevo = Cuerpo(operaciones=ops, capa=entidades[0].get("capa", "0"),
                   plano=entidades[0].get("plano", "XY"))
    with doc.transaccion("extruir"):
        doc.agregar(nuevo)
    salida = _malla(nuevo)
    # Cuánto tardó de verdad, para que la pantalla lo diga y nadie adivine.
    salida["ms"] = round((time.perf_counter() - t0) * 1000)
    return salida


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


@router.get("/{id_}/tiradores")
def tiradores(id_: str):
    """De qué se puede jalar la pieza: sus vértices y sus aristas de verdad,
    cada uno con su nombre, ya girados al plano de la pieza.

    Esto sí toca el kernel —hay que tener el sólido para saber sus puntos—,
    pero la regeneración está en caché por huella de las operaciones: pedirlos
    después de pintar no cuesta nada.
    """
    from core.solido import cuerpo as mod
    c = _cuerpo(id_)
    d = mod.tiradores(c)
    plano = d["plano"]
    for v in d["vertices"]:
        v["p"] = _a_mundo(plano, v["p"])
    for a in d["aristas"]:
        for k in ("p", "a", "b"):
            a[k] = _a_mundo(plano, a[k])
    return d


class MoverEnElMundo(BaseModel):
    nombre: str
    d: list[float]


def _mover(id_: str, entrada: MoverEnElMundo, cual: str):
    """El camino común de mover un vértice y mover una arista.

    El arrastre llega en coordenadas del mundo —es lo que el ratón sabe— y se
    gira al plano de la pieza antes de entrar al historial, porque el kernel
    siempre trabaja en XY.

    Si la pieza sale imposible, el historial se queda como estaba. Es la misma
    promesa de todas las demás operaciones: vale más que no pase nada a que el
    modelo quede roto y el usuario no sepa en qué momento.
    """
    from core.solido import cuerpo as mod
    c = _cuerpo(id_)
    antes = list(c.operaciones)
    if all(abs(k) < 1e-9 for k in entrada.d):
        return _malla(c)
    d = _del_mundo(getattr(c, "plano", "XY"), list(entrada.d) + [0.0, 0.0, 0.0])
    hacer = mod.mover_vertice if cual == "vertice" else mod.mover_arista
    nuevas = hacer(antes, entrada.nombre, d)
    doc = _doc()
    with doc.transaccion(f"mover {cual}"):
        doc.modificar(id_, {"operaciones": nuevas})
    try:
        return _malla(doc.entidades[id_])
    except HTTPException:
        with doc.transaccion(f"deshacer mover {cual}"):
            doc.modificar(id_, {"operaciones": antes})
        raise


@router.post("/{id_}/mover-vertice")
def mover_vertice(id_: str, entrada: MoverEnElMundo):
    """Una esquina de la pieza, corrida. Sólo esa."""
    return _mover(id_, entrada, "vertice")


@router.post("/{id_}/mover-arista")
def mover_arista(id_: str, entrada: MoverEnElMundo):
    """Una arista entera, corrida: sus dos extremos se mueven lo mismo."""
    return _mover(id_, entrada, "arista")


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
    # A tamaño real: si el dibujo está en cm, la pieza sale diez veces más
    # grande que los números del kernel, que es lo que mide de verdad.
    f = _factor_mm()
    solido = reg.solido.scale(f) if f != 1.0 else reg.solido
    solido = _rotar(solido, getattr(c, "plano", "XY"))
    if formato == "step":
        export_step(solido, str(destino))
    elif formato == "stl":
        export_stl(solido, str(destino))
    else:
        raise HTTPException(400, f"no conozco el formato «{entrada.formato}»: step o stl")
    return {"ruta": str(destino), "bytes": destino.stat().st_size}
