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
- `barrido_dos_rieles`  el Sweep2 de Rhino: un perfil que recorre dos rieles
                tocando los dos (fase D1b).

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


# --- Barrido por dos rieles (fase D1b) -------------------------------------

def _seccion(perfil, p0, v0, r1, r2):
    """El perfil llevado a que su punta p0 caiga en r1 y la otra en r2: se gira
    lo mínimo (de v0 a r2 - r1), se escala por la razón de largos y se mueve.
    Es una semejanza: el perfil conserva su forma, sólo cambia de tamaño."""
    import math

    from build123d import Shape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

    w = r2 - r1
    k = w.length / v0.length
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(-p0.X, -p0.Y, -p0.Z))
    esc = gp_Trsf()
    esc.SetScale(gp_Pnt(0, 0, 0), k)
    t = esc.Multiplied(t)
    eje = v0.cross(w)
    angulo = v0.get_angle(w)
    if eje.length > 1e-12 and abs(angulo) > 1e-12:
        rot = gp_Trsf()
        rot.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(eje.X, eje.Y, eje.Z)), math.radians(angulo))
        t = rot.Multiplied(t)
    elif angulo > 179.999:
        # Opuestos: media vuelta sobre cualquier eje perpendicular.
        perp = v0.cross((1, 0, 0)) if abs(v0.normalized().X) < 0.9 else v0.cross((0, 1, 0))
        rot = gp_Trsf()
        rot.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(perp.X, perp.Y, perp.Z)), math.pi)
        t = rot.Multiplied(t)
    mov = gp_Trsf()
    mov.SetTranslation(gp_Vec(r1.X, r1.Y, r1.Z))
    t = mov.Multiplied(t)
    return Shape.cast(BRepBuilderAPI_Transform(perfil.wrapped, t, True).Shape())


def _distancia(a, b) -> float:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    return BRepExtrema_DistShapeShape(a.wrapped, b.wrapped).Value()


def _en(riel, s: float):
    """El punto del riel a la fracción s de su largo; un riel (alambre, al
    revés) se recorre desde su final."""
    alambre, al_reves = riel if isinstance(riel, tuple) else (riel, False)
    return alambre.position_at(1 - s if al_reves else s)


def barrido_dos_rieles(perfil, riel1, riel2, tol: float):
    """Sweep2: el perfil recorre dos rieles tocando los dos a la vez.

    `perfil` arranca en el inicio de `riel1` y termina en el de `riel2`. Un riel
    puede venir como (alambre, al_revés): se recorre desde su final. En cada fracción s del largo de los rieles el perfil
    se copia por semejanza para que sus puntas caigan en riel1(s) y riel2(s), y
    se tiende una piel por todas las copias. Cuántas: se empieza con 16 y se
    duplican mientras la piel se separe de la copia de en medio de cada tramo
    más que `tol` (hasta 128). Devuelve (superficie, separación medida)."""
    from build123d import Wire

    p0, p1 = perfil.start_point(), perfil.end_point()
    v0 = p1 - p0
    if v0.length < 1e-9:
        raise ValueError("el perfil de un barrido por dos rieles no puede ser cerrado")
    n = 16
    while True:
        secciones = [_seccion(perfil, p0, v0, _en(riel1, i / n), _en(riel2, i / n))
                     for i in range(n + 1)]
        piel = loft([Wire(s.edges()) if not isinstance(s, Wire) else s for s in secciones])
        peor = 0.0
        for i in range(n):
            s = (i + 0.5) / n
            medio = _seccion(perfil, p0, v0, _en(riel1, s), _en(riel2, s))
            peor = max(peor, max(_distancia(v, piel) for v in _muestras_de(medio)))
        if peor <= tol or n >= 128:
            return piel, peor
        n *= 2


def _muestras_de(alambre, k: int = 5):
    """Unos puntos (como vértices) a lo largo de un alambre, para medir."""
    from build123d import Vertex
    return [Vertex(*tuple(alambre.position_at(j / (k - 1)))) for j in range(k)]


def papeles_dos_rieles(alambres: list, tol: float):
    """De tres curvas abiertas, (perfil, riel1, riel2): el perfil es la que
    toca con una punta a una y con la otra a la otra. Cada riel sale como
    (alambre, al_revés), para que se recorra desde donde toca al perfil; el
    riel1 es el que toca el inicio del perfil."""
    def cerca(a, b):
        return (a - b).length <= tol

    for k in range(3):
        perfil = alambres[k]
        rieles = [alambres[j] for j in range(3) if j != k]
        p0, p1 = perfil.start_point(), perfil.end_point()
        orient = []
        for r in rieles:
            if cerca(r.start_point(), p0) or cerca(r.start_point(), p1):
                orient.append((r, False))
            elif cerca(r.end_point(), p0) or cerca(r.end_point(), p1):
                orient.append((r, True))
            else:
                break
        else:
            arranque = lambda rr: rr[0].end_point() if rr[1] else rr[0].start_point()
            ra, rb = orient
            # El riel1 es el que arranca en el inicio del perfil.
            if cerca(arranque(ra), p0) and cerca(arranque(rb), p1):
                return perfil, ra, rb
            if cerca(arranque(rb), p0) and cerca(arranque(ra), p1):
                return perfil, rb, ra
    raise ValueError("para un barrido por dos rieles, el perfil tiene que tocar con sus dos "
                     "puntas el arranque de los dos rieles")


# --- Editar por puntos de control (fase D2) ---------------------------------

def bspline_de(cara):
    """(superficie B-spline, recortada?) de una cara. Una cara que no es
    B-spline (un cilindro de un revolucionado, un plano) se convierte a NURBS,
    que es la misma superficie dicha de otra manera. «Recortada» quiere decir
    que la cara no cubre el dominio entero de su superficie: un parche de RED,
    por ejemplo, va recortado por su borde."""
    from build123d import Face
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_NurbsConvert
    from OCP.GeomAbs import GeomAbs_BSplineSurface

    ad = BRepAdaptor_Surface(cara.wrapped)
    if ad.GetType() != GeomAbs_BSplineSurface:
        conv = BRepBuilderAPI_NurbsConvert(cara.wrapped, True)
        cara = Face(conv.Shape())
        ad = BRepAdaptor_Surface(cara.wrapped)
    sup = ad.BSpline()
    entera = Face(BRepBuilderAPI_MakeFace(sup, 1e-7).Face())
    recortada = abs(entera.area - cara.area) > 1e-6 * max(1.0, entera.area)
    return sup, recortada


def polos_de(cara) -> list:
    """Los puntos de control de la cara, como [(i, j, (x, y, z), en_borde)],
    con i y j desde 1 (como los cuenta OpenCASCADE). Vacío si la cara está
    recortada: ahí mover un polo dejaría el borde fuera de la superficie."""
    sup, recortada = bspline_de(cara)
    if recortada:
        return []
    nu, nv = sup.NbUPoles(), sup.NbVPoles()
    salida = []
    for i in range(1, nu + 1):
        for j in range(1, nv + 1):
            p = sup.Pole(i, j)
            salida.append((i, j, (p.X(), p.Y(), p.Z()), i in (1, nu) or j in (1, nv)))
    return salida


def mover_polo(forma, cara, i: int, j: int, d):
    """La forma con el polo (i, j) de `cara` corrido `d`. Devuelve (forma
    nueva, cara nueva).

    Reglas, para que la superficie no se rompa: la cara no puede estar
    recortada; y si la superficie tiene más de una cara, sólo se mueven polos
    interiores (uno del borde despegaría la cara de su vecina)."""
    from build123d import Face, Shape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepTools import BRepTools_ReShape
    from OCP.gp import gp_Pnt

    sup, recortada = bspline_de(cara)
    if recortada:
        raise ValueError("esa cara está recortada por su borde (como un parche de RED): "
                         "mover sus puntos de control la despegaría del borde")
    nu, nv = sup.NbUPoles(), sup.NbVPoles()
    if not (1 <= i <= nu and 1 <= j <= nv):
        raise ValueError(f"esa cara no tiene el punto de control ({i}, {j}); tiene {nu} × {nv}")
    en_borde = i in (1, nu) or j in (1, nv)
    if en_borde and len(forma.faces()) > 1:
        raise ValueError("ese punto de control está en el borde de una cara que toca a otra: "
                         "moverlo las despegaría. Mueve uno de adentro.")
    nueva_sup = sup.Copy()
    p = sup.Pole(i, j)
    nueva_sup.SetPole(i, j, gp_Pnt(p.X() + d[0], p.Y() + d[1], p.Z() + d[2]))
    nueva = Face(BRepBuilderAPI_MakeFace(nueva_sup, 1e-7).Face())
    if len(forma.faces()) == 1:
        return nueva, nueva
    cambio = BRepTools_ReShape()
    cambio.Replace(cara.wrapped, nueva.wrapped)
    return _forma(cambio.Apply(forma.wrapped)), nueva
