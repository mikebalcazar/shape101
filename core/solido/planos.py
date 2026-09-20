"""Sobre qué plano vive un boceto.

Hasta la 0.18.0 todos los bocetos vivían en el suelo del kernel (XY, z = 0).
Alcanzaba porque lo único que se hacía con ellos era extruirlos hacia arriba.
Deja de alcanzar de golpe con el grupo **model**: dos perfiles en el mismo
plano no hacen un loft, y un barrido necesita un camino que no esté encima del
perfil.

Mike, 19-sep, describiendo el grupo `draw`: *«para trazar los dibujos de lo que
queremos extruir sobre un plano, puede ser el plano de la vista, puede ser
sobre una cara de algún sólido, o puede ser sobre un plano libre definido por
nosotros (en esta opción se puede tomar una cara alabeada y sacar el promedio
de la perpendicularidad para proponer el plano)»*.

Las tres, entonces, y una cuarta que sale gratis:

    {"z": 50}                                   el suelo, subido 50
    {"origen": [x,y,z], "normal": [a,b,c]}      plano libre
    {"cara": "arriba", "desfase": 0}            sobre una cara del sólido
    ausente                                     el suelo, como siempre

El boceto se sigue dibujando en coordenadas planas —(u, v)— y el plano dice
dónde cae ese papel. Es lo mismo que hace un tablero de dibujo: el dibujo no
sabe en qué pared está colgado.

**`x` es opcional pero importa.** Si no se da, el kernel elige un eje
horizontal cualquiera y el mismo boceto puede salir girado dentro de su plano.
Para un plano libre que se vaya a guardar conviene darlo.
"""
from __future__ import annotations

import math

# Cuántos puntos por lado se muestrean para promediar una cara alabeada. 12×12
# = 144 normales; medido el 19-sep en 54 ms, y con 6×6 el promedio ya se movía
# más de un grado en una cara de doble curvatura.
REJILLA = 12


def _vec(v, cuantos=3):
    fuera = [float(k) for k in (v or [])]
    while len(fuera) < cuantos:
        fuera.append(0.0)
    return tuple(fuera[:cuantos])


def es_el_suelo(spec) -> bool:
    """El caso de siempre: nada dicho, o el suelo sin subir."""
    if not spec:
        return True
    if set(spec) <= {"z"} and abs(float(spec.get("z", 0.0))) < 1e-12:
        return True
    return False


def plano_de(spec, nombrador=None, solido=None):
    """El `Plane` de build123d que describe esa especificación."""
    from build123d import Plane

    if not spec:
        return Plane.XY
    if "cara" in spec:
        if nombrador is None or solido is None:
            raise ValueError("un boceto sobre una cara necesita una pieza debajo")
        cara = nombrador.cara(spec["cara"])
        n = cara.normal_at()
        o = cara.center() + n * float(spec.get("desfase", 0.0))
        return Plane(origin=(o.X, o.Y, o.Z), z_dir=(n.X, n.Y, n.Z))
    if "origen" in spec or "normal" in spec:
        o = _vec(spec.get("origen", [0, 0, 0]))
        n = _vec(spec.get("normal", [0, 0, 1]))
        if math.sqrt(sum(k * k for k in n)) < 1e-12:
            raise ValueError("la normal de un plano no puede ser cero")
        if "x" in spec:
            return Plane(origin=o, x_dir=_vec(spec["x"]), z_dir=n)
        return Plane(origin=o, z_dir=n)
    z = float(spec.get("z", 0.0))
    return Plane(origin=(0, 0, z), z_dir=(0, 0, 1))


def colocar(forma, spec, nombrador=None, solido=None):
    """Lleva algo dibujado en el papel (u, v) al plano que le toca.

    Si el plano es el suelo se devuelve tal cual, sin pasar por el kernel: es
    el caso de todas las piezas que ya existen y no tiene por qué costar nada.
    """
    if es_el_suelo(spec):
        return forma
    return plano_de(spec, nombrador, solido).from_local_coords(forma)


def promedio_de_cara(cara) -> dict:
    """El plano que mejor representa una cara alabeada: su punto medio y el
    promedio de sus perpendiculares.

    Para qué: una cara que se alabeó al mover un punto ya no es plana, así que
    no se puede dibujar «sobre ella». Esto propone un plano honesto y, de
    paso, dice **cuánto se está mintiendo**: `desvio_mm` es lo más lejos que
    queda un punto de la cara respecto del plano propuesto. Medido el 19-sep:
    0.00 mm en una cara plana, ±7.34 en una alabeada, +43 a +47 en un casquete
    de doble curvatura —ahí el plano no sirve y el número lo grita—.
    """
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    sup = BRepAdaptor_Surface(cara.wrapped)
    u0, u1 = sup.FirstUParameter(), sup.LastUParameter()
    v0, v1 = sup.FirstVParameter(), sup.LastVParameter()
    sx = sy = sz = 0.0
    px = py = pz = 0.0
    n = 0
    puntos = []
    for i in range(REJILLA):
        for j in range(REJILLA):
            u = u0 + (u1 - u0) * (i + 0.5) / REJILLA
            v = v0 + (v1 - v0) * (j + 0.5) / REJILLA
            prop = BRepLProp_SLProps(sup, u, v, 1, 1e-7)
            if not prop.IsNormalDefined():
                continue
            nn, pp = prop.Normal(), prop.Value()
            sx, sy, sz = sx + nn.X(), sy + nn.Y(), sz + nn.Z()
            px, py, pz = px + pp.X(), py + pp.Y(), pz + pp.Z()
            puntos.append((pp.X(), pp.Y(), pp.Z()))
            n += 1
    if n == 0:
        raise ValueError("esta cara no tiene perpendicular en ningún lado")
    largo = math.sqrt(sx * sx + sy * sy + sz * sz)
    if largo < 1e-9:
        raise ValueError("las perpendiculares de esta cara se cancelan: no hay plano promedio")
    normal = (sx / largo, sy / largo, sz / largo)
    origen = (px / n, py / n, pz / n)
    desvio = max(abs(sum(normal[k] * (p[k] - origen[k]) for k in range(3))) for p in puntos)
    return {"origen": [round(k, 6) for k in origen],
            "normal": [round(k, 6) for k in normal],
            "desvio_mm": round(desvio, 4),
            "muestras": n}


# --- el plano de la ventana donde se dibujó  ·  0.19.0 ----------------------
#
# El dibujo 2D vive en una de las tres ventanas ortogonales y cada entidad se
# acuerda de cuál: `"XY"` la Superior, `"XZ"` la Frontal, `"YZ"` la Lateral.
# Hasta la 0.18.0 eso se resolvía al final —la pieza se armaba en el suelo y se
# rotaba al salir, `rutas._al_mundo`—, y alcanzaba porque una pieza salía de un
# solo contorno.
#
# Deja de alcanzar con el grupo `model`: un barrido quiere el perfil en la
# Frontal y el camino en la Superior, y esos dos no se pueden rotar juntos al
# final porque no están en el mismo plano. Así que cada boceto se coloca en su
# sitio **desde el principio** y la pieza nace ya en el mundo.
#
# Las cuentas son las mismas que `rutas._a_mundo`, sólo que dichas como plano:
#   XZ: (u, v) → (u, 0, v)   normal (0, −1, 0), hacia quien mira la Frontal
#   YZ: (u, v) → (0, u, v)   normal (1, 0, 0),  hacia +X
DEL_DIBUJO = {
    "XY": {"origen": [0, 0, 0], "x": [1, 0, 0], "normal": [0, 0, 1]},
    "XZ": {"origen": [0, 0, 0], "x": [1, 0, 0], "normal": [0, -1, 0]},
    "YZ": {"origen": [0, 0, 0], "x": [0, 1, 0], "normal": [1, 0, 0]},
}


def del_dibujo(plano: str | None, z: float = 0.0) -> dict | None:
    """La especificación de plano que le toca a un boceto según la ventana en
    la que se dibujó. `z` lo separa de sus hermanos a lo largo de su normal,
    que es lo que hace falta para un loft entre contornos de la misma ventana.

    Devuelve `None` para la Superior a ras de suelo: es el caso de todas las
    piezas que ya existen y no tiene por qué costar nada ni cambiar un nombre.
    """
    base = DEL_DIBUJO.get(plano or "XY", DEL_DIBUJO["XY"])
    if not z:
        return None if (plano or "XY") == "XY" else dict(base)
    n = base["normal"]
    return {"origen": [n[0] * z, n[1] * z, n[2] * z], "x": list(base["x"]), "normal": list(n)}
