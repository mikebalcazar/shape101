"""Superficies libres  ·  fase D1 del rumbo de modelado.

Hasta aquí todo lo que salía del 3D era un sólido cerrado: un contorno abierto
no servía para nada. Rhino, en cambio, vive de superficies: una piel que pasa
por varias curvas, una curva que gira, un perfil que recorre un camino, un
parche que cierra un borde. Aquí están esas cuatro, con OpenCASCADE:

- `loft`        piel por secciones abiertas (BRepOffsetAPI_ThruSections).
- `revolucion`  un perfil abierto que gira alrededor de un eje.
- `barrido`     un perfil abierto que recorre un camino (BRepOffsetAPI_MakePipe).
- `red`         un parche que pasa por un borde de varias curvas que cierran
                un lazo (BRepFill_Filling): el NetworkSrf / EdgeSrf de Rhino.

Lo que sale es una superficie (o un conjunto de caras), no un sólido: no tiene
volumen. Vive en la misma entidad `cuerpo`, con su historial, y se ve, se
guarda y sale a STEP igual que un sólido.
"""

from __future__ import annotations


def _forma(shape):
    from build123d import Shape
    return Shape.cast(shape) if hasattr(Shape, "cast") else Shape(shape)


def loft(alambres: list, reglado: bool = False):
    """La piel que pasa por las secciones abiertas, en ese orden."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections

    if len(alambres) < 2:
        raise ValueError("una piel necesita al menos dos secciones")
    ts = BRepOffsetAPI_ThruSections(False, bool(reglado), 1e-6)
    for w in alambres:
        ts.AddWire(w.wrapped)
    ts.CheckCompatibility(True)
    ts.Build()
    if not ts.IsDone():
        raise ValueError("no se pudo tender una piel por esas secciones")
    return _forma(ts.Shape())


def revolucion(alambre, eje, grados: float = 360.0):
    """La superficie que deja un perfil abierto al girar alrededor de `eje`."""
    import math

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

    ax = gp_Ax1(gp_Pnt(eje.position.X, eje.position.Y, eje.position.Z),
                gp_Dir(eje.direction.X, eje.direction.Y, eje.direction.Z))
    rev = BRepPrimAPI_MakeRevol(alambre.wrapped, ax, math.radians(grados))
    rev.Build()
    if not rev.IsDone():
        raise ValueError("no se pudo girar ese perfil")
    return _forma(rev.Shape())


def barrido(perfil, camino):
    """La superficie que deja un perfil abierto al recorrer un camino."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe

    tubo = BRepOffsetAPI_MakePipe(camino.wrapped, perfil.wrapped)
    tubo.Build()
    if not tubo.IsDone():
        raise ValueError("no se pudo barrer ese perfil por ese camino")
    return _forma(tubo.Shape())


def red(alambres: list):
    """El parche que pasa por un borde cerrado hecho de varias curvas.

    Las curvas tienen que cerrar un lazo (se cosen por sus puntas, ya soldadas
    a la tolerancia en el boceto); el parche las toca a todas con continuidad
    de posición."""
    from build123d import Face
    from OCP.BRepFill import BRepFill_Filling
    from OCP.GeomAbs import GeomAbs_C0

    from build123d import Wire

    aristas = [e for w in alambres for e in w.edges()]
    if len(aristas) < 2:
        raise ValueError("un parche necesita al menos dos curvas de borde")
    # Que cierren un lazo se revisa antes: con un lado de menos el kernel arma
    # igual un parche, pero degenerado, y truena después al pintarlo.
    lazos = Wire.combine(aristas)
    if len(lazos) != 1 or not lazos[0].is_closed:
        raise ValueError("esas curvas no cierran un borde: tienen que tocarse punta con punta")
    relleno = BRepFill_Filling()
    for e in aristas:
        relleno.Add(e.wrapped, GeomAbs_C0, True)
    try:
        relleno.Build()
    except Exception as exc:
        raise ValueError("esas curvas no cierran un borde: tienen que tocarse punta con punta") from exc
    if not relleno.IsDone():
        raise ValueError("esas curvas no cierran un borde: tienen que tocarse punta con punta")
    return Face(relleno.Face())
