"""Rayados (HATCH): los patrones y sus rayas  ·  0.20.0.

Hasta la 0.19.4 un rayado se pintaba sólo por su contorno: el patrón viajaba al
DXF (ezdxf lo conoce) pero en pantalla y en el PDF no se veía. Mike (9-sep-2026)
pidió una **galería de patrones con previa en el modelo** antes de cerrar el
comando, y para eso el patrón tiene que dibujarse de verdad.

Aquí viven los patrones —los de AutoCAD que se usan en un plano de mueble y de
obra, con sus mismos nombres para que el DXF salga igual— y el cálculo de las
rayas: cada familia de rayas del patrón se recorta contra el contorno (par-impar,
así las islas quedan huecas). Un sólido no es rayas: es un relleno, y viaja como
tal (`clase: "relleno"`, ver core/dibujo.py).

Las medidas de los patrones son las de AutoCAD en **milímetros** (ANSI31 raya
cada 3.175 mm a escala 1); en un dibujo en metros se dividen por los mm por
unidad, para que un rayado a escala 1 se vea igual en cualquier unidad.
"""

from __future__ import annotations

import math

# name → (descripción, [familias]). Cada familia: (ángulo en grados,
# separación en mm, desfase en mm entre rayas consecutivas (0 = alineadas),
# patrón de raya [largo, hueco…] en mm o [] = continua).
PATRONES: dict[str, tuple[str, list]] = {
    "SOLID":  ("Sólido", []),
    "ANSI31": ("Diagonal 45°", [(45.0, 3.175, 0.0, [])]),
    "ANSI32": ("Diagonal doble (acero)", [(45.0, 9.525, 0.0, []), (45.0, 9.525, 3.175, [])]),
    "ANSI33": ("Diagonal punteada (bronce)", [(45.0, 6.35, 0.0, [6.35, -3.175]), (45.0, 6.35, 3.175, [6.35, -3.175])]),
    "ANSI34": ("Diagonal ancha (plástico)", [(45.0, 19.05, 0.0, [])] + [(45.0, 19.05, d, []) for d in (3.175, 6.35, 9.525)]),
    "ANSI37": ("Cruzada 45° (aislante)", [(45.0, 3.175, 0.0, []), (135.0, 3.175, 0.0, [])]),
    "LINE":   ("Horizontal", [(0.0, 3.175, 0.0, [])]),
    "VERT":   ("Vertical", [(90.0, 3.175, 0.0, [])]),
    "NET":    ("Cuadrícula", [(0.0, 3.175, 0.0, []), (90.0, 3.175, 0.0, [])]),
    "NET3":   ("Cuadrícula triple", [(0.0, 3.175, 0.0, []), (90.0, 3.175, 0.0, []), (45.0, 3.175, 0.0, [])]),
    "DOTS":   ("Puntos", [(0.0, 2.54, 1.27, [0.0, -2.54])]),
    "BRICK":  ("Ladrillo", [(0.0, 6.35, 0.0, []), (90.0, 12.7, 6.35, [6.35, -6.35])]),
    "AR-CONC": ("Concreto", [(50.0, 10.0, 4.0, [3.0, -8.0]), (355.0, 9.0, 3.0, [2.0, -7.0]), (100.0, 11.0, 5.0, [1.5, -9.0])]),
    "AR-SAND": ("Arena", [(37.5, 4.0, 1.5, [0.0, -4.0]), (7.5, 4.0, 2.0, [0.0, -4.0]), (102.5, 4.0, 1.0, [0.0, -4.0])]),
    "EARTH":  ("Tierra", [(0.0, 6.35, 3.175, [6.35, -6.35]), (90.0, 6.35, 3.175, [6.35, -6.35])]),
    "STEEL":  ("Acero", [(45.0, 3.175, 0.0, []), (45.0, 3.175, 1.5875, [])]),
    "WOOD":   ("Madera (veta)", [(0.0, 5.0, 0.0, [12.0, -3.0]), (0.0, 5.0, 2.5, [4.0, -11.0])]),
    "INSUL":  ("Aislante", [(0.0, 9.525, 0.0, []), (0.0, 9.525, 3.175, [9.525, -9.525]), (0.0, 9.525, 6.35, [9.525, -9.525])]),
    "GLASS":  ("Vidrio", [(45.0, 12.0, 0.0, [8.0, -4.0]), (45.0, 12.0, 6.0, [3.0, -9.0])]),
    "HEX":    ("Hexágonos", [(0.0, 5.4985, 0.0, [3.175, -6.35]), (120.0, 5.4985, 0.0, [3.175, -6.35]), (60.0, 5.4985, 3.175, [3.175, -6.35])]),
}

#: Orden en que la galería los enseña: los de siempre primero.
ORDEN = ["SOLID", "ANSI31", "ANSI32", "ANSI37", "LINE", "VERT", "NET", "DOTS",
         "BRICK", "AR-CONC", "AR-SAND", "EARTH", "STEEL", "WOOD", "INSUL", "GLASS",
         "NET3", "HEX", "ANSI33", "ANSI34"]

#: Tope de rayas por rayado. Pasado eso, la separación se abre sola: un rayado
#: de mil metros a escala 1 no es un dibujo, es un bloque negro.
MAX_RAYAS = 6000


def lista() -> list[dict]:
    return [{"nombre": n, "descripcion": PATRONES[n][0], "solido": not PATRONES[n][1]} for n in ORDEN]


def _teselar(ruta) -> list[list[float]]:
    """El contorno como polígono (los arcos con bulge, en trocitos)."""
    from . import dibujo
    pts = dibujo._polilinea(ruta, True)
    if len(ruta) == 2:
        # Un círculo como dos medios arcos (así lo guarda el DXF): `_polilinea`
        # sólo cierra con tres vértices o más; el tramo de vuelta va aquí.
        b = ruta[1][2] if len(ruta[1]) > 2 else 0.0
        pts = pts + dibujo._bulge(ruta[1], ruta[0], b)
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        pts = pts[:-1]
    return [[p[0], p[1]] for p in pts]


def _cruces(poligonos, ox, oy, dx, dy):
    """Parámetros t donde la recta (ox,oy)+t·(dx,dy) cruza las aristas."""
    ts = []
    for pol in poligonos:
        n = len(pol)
        for i in range(n):
            ax, ay = pol[i]
            bx, by = pol[(i + 1) % n]
            ex, ey = bx - ax, by - ay
            den = dx * ey - dy * ex
            if abs(den) < 1e-12:
                continue
            # (ox,oy)+t(dx,dy) = (ax,ay)+u(ex,ey)
            t = ((ax - ox) * ey - (ay - oy) * ex) / den
            u = ((ax - ox) * dy - (ay - oy) * dx) / den
            if -1e-9 <= u < 1 - 1e-9:
                ts.append(t)
    ts.sort()
    return ts


def rayas(rutas, patron: str, escala: float = 1.0, angulo: float = 0.0,
          mm_por_unidad: float = 1.0) -> list[list[list[float]]]:
    """Las rayas del patrón dentro del contorno, como pares [[x,y],[x,y]]."""
    pat = PATRONES.get((patron or "").upper())
    if not pat or not pat[1]:
        return []
    poligonos = [_teselar(r) for r in rutas if len(r) >= 2]
    if not poligonos:
        return []
    xs = [p[0] for pol in poligonos for p in pol]
    ys = [p[1] for pol in poligonos for p in pol]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    diag = math.hypot(x1 - x0, y1 - y0) or 1.0
    k = float(escala or 1.0) / float(mm_por_unidad or 1.0)
    salida = []
    for (ang, sep, desfase, guion) in pat[1]:
        sep_u = max(sep * k, 1e-6)
        # Que no explote: si la caja pide más rayas que el tope, se abre la
        # separación (y el guion con ella) hasta que quepan.
        cuantas = diag / sep_u
        f = max(1.0, cuantas / (MAX_RAYAS / max(1, len(pat[1]))))
        sep_u *= f
        des_u = desfase * k * f
        guion_u = [g * k * f for g in guion]
        a = math.radians(ang + angulo)
        dx, dy = math.cos(a), math.sin(a)          # a lo largo de la raya
        nx, ny = -dy, dx                            # de raya en raya
        # Rayas desde -diag hasta +diag respecto del centro, con la fase
        # anclada al origen (0,0) para que dos rayados vecinos casen.
        m0 = math.floor(((cx * nx + cy * ny) - diag) / sep_u)
        m1 = math.ceil(((cx * nx + cy * ny) + diag) / sep_u)
        for m in range(m0, m1 + 1):
            d = m * sep_u
            ox, oy = nx * d, ny * d
            ts = _cruces(poligonos, ox, oy, dx, dy)
            for i in range(0, len(ts) - 1, 2):
                ta, tb = ts[i], ts[i + 1]
                if tb - ta < 1e-9:
                    continue
                if not guion_u:
                    salida.append([[ox + dx * ta, oy + dy * ta], [ox + dx * tb, oy + dy * tb]])
                    continue
                # Raya con guiones: se recorre el tramo por el patrón, con la
                # fase corrida `des_u` por raya para que el punteado escalone.
                # (positivo = raya, negativo = hueco, 0 = punto, como en el .pat).
                periodo = sum(abs(g) for g in guion_u)
                if periodo < 1e-9:
                    continue
                fase = (m * des_u) % periodo
                t = ta - fase
                vueltas = 0
                while t < tb and vueltas < 20000:
                    vueltas += 1
                    for g in guion_u:
                        largo = abs(g)
                        if g > 0:
                            ini, fin = max(t, ta), min(t + largo, tb)
                            if fin - ini > 1e-9:
                                salida.append([[ox + dx * ini, oy + dy * ini], [ox + dx * fin, oy + dy * fin]])
                        elif g == 0 and ta <= t <= tb:
                            # un punto: una raya diminuta, que el lienzo pinta como mancha
                            e = 0.2 * k
                            salida.append([[ox + dx * t, oy + dy * t], [ox + dx * (t + e), oy + dy * (t + e)]])
                        t += largo
                        if t >= tb:
                            break
                if len(salida) > MAX_RAYAS * 4:
                    return salida
    return salida
