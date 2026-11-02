"""De un boceto del dibujo (entidades 2D) a un sólido de build123d.

Qué se acepta: líneas, arcos, círculos, polilíneas (cerradas o no, con
bulges), splines y elipses. La spline y la elipse entran como curvas exactas
(B-spline y elipse de OpenCASCADE), no como polilíneas. Las cotas, textos y
demás se ignoran: no son geometría. Las puntas sueltas se sueldan a la
tolerancia del documento antes de coser (`soldadas`).

Cómo se arma: cada entidad da uno o varios `Edge`; `Wire.combine` los cose por
extremos en contornos cerrados, y los contornos se ordenan por **anidamiento**
(`caras_de`, fase C1): uno que no está dentro de ningún otro es un borde
exterior; uno dentro de uno, un hueco; uno dentro de dos, una isla —material
otra vez—, y así. Como el PlanarSrf de Rhino. Cada borde exterior con sus
huecos directos es una cara; un boceto con dos piezas separadas da dos caras,
y se extruyen las dos.

Bulge: convención DXF. `b = tan(θ/4)`; positivo = antihorario del vértice al
siguiente. El punto medio del arco queda a `s = b·d/2` del punto medio de la
cuerda, hacia la derecha de la dirección de la cuerda cuando b > 0.
"""
from __future__ import annotations

import math

from build123d import (Edge, Face, Plane, Vector, Wire, extrude)


def _arco_tres_puntos(p1, p2, bulge: float) -> Edge:
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    d = math.hypot(dx, dy)
    if d < 1e-12:
        raise ValueError("un tramo de polilínea con bulge y largo cero")
    s = bulge * d / 2.0
    mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
    # perpendicular a la derecha de la dirección de la cuerda
    px, py = dy / d, -dx / d
    medio = (mx + px * s, my + py * s)
    return Edge.make_three_point_arc(Vector(p1[0], p1[1], 0), Vector(*medio, 0), Vector(p2[0], p2[1], 0))


def aristas_de(entidad: dict) -> list[Edge]:
    t = entidad.get("tipo")
    if t == "arco3":
        # Un arco ya soldado (ver `soldadas`): por sus dos extremos y un punto
        # de en medio, que es como OpenCASCADE lo arma sin redondear nada.
        a, m, b = entidad["p1"], entidad["pm"], entidad["p2"]
        return [Edge.make_three_point_arc(Vector(a[0], a[1], 0), Vector(m[0], m[1], 0),
                                          Vector(b[0], b[1], 0))]
    if t == "linea":
        a, b = entidad["p1"], entidad["p2"]
        return [Edge.make_line(Vector(a[0], a[1], 0), Vector(b[0], b[1], 0))]
    if t == "circulo":
        c, r = entidad["centro"], entidad["radio"]
        return [Edge.make_circle(r, Plane(origin=(c[0], c[1], 0)))]
    if t == "arco":
        c, r = entidad["centro"], entidad["radio"]
        a0, a1 = entidad["ang_ini"], entidad["ang_fin"]
        if a1 <= a0:
            a1 += 360.0
        return [Edge.make_circle(r, Plane(origin=(c[0], c[1], 0)), start_angle=a0, end_angle=a1)]
    if t == "polilinea":
        pts = entidad["puntos"]
        n = len(pts)
        tramos = n - 1 + (1 if entidad.get("cerrada") else 0)
        out = []
        for i in range(tramos):
            p1, p2 = pts[i], pts[(i + 1) % n]
            b = p1[2] if len(p1) > 2 else 0.0
            if abs(b) > 1e-12:
                out.append(_arco_tres_puntos(p1, p2, b))
            else:
                if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) > 1e-12:
                    out.append(Edge.make_line(Vector(p1[0], p1[1], 0), Vector(p2[0], p2[1], 0)))
        return out
    if t in ("spline", "elipse"):
        # Exactas: la spline como B-spline y la elipse como elipse del kernel
        # (core/regiones), no como polilínea. Hasta la fase C1 el boceto las
        # ignoraba sin decir nada, y un contorno con una spline «no cerraba».
        from core import entidades as ent_mod
        from core import regiones
        return regiones._aristas_de(ent_mod.de_dict(entidad))
    return []        # cotas, textos, bloques…: no son geometría del boceto


def _extremos_de_arco(e: dict):
    c, r = e["centro"], e["radio"]
    a0, a1 = math.radians(e["ang_ini"]), math.radians(e["ang_fin"])
    if a1 <= a0:
        a1 += 2 * math.pi
    p = lambda a: [c[0] + r * math.cos(a), c[1] + r * math.sin(a)]
    return p(a0), p((a0 + a1) / 2), p(a1)


def soldadas(entidades: list[dict], tol: float | None = None) -> list[dict]:
    """Las mismas entidades con sus extremos sueltos soldados a la tolerancia.

    OpenCASCADE cose un contorno sólo si los extremos coinciden a unas micras.
    Un plano de AutoCAD o de Revit trae huecos de centésimas: UNIR los pasaba
    por alto (0.05 mm) y aquí el mismo contorno «no cerraba». Ahora los dos
    usan la tolerancia del documento (core/tolerancia.py), como en Rhino.

    Sólo se tocan las puntas sueltas —de líneas, arcos y polilíneas abiertas—;
    un círculo o una polilínea cerrada ya cierran solos. Una punta se mueve
    como mucho `tol`.
    """
    from core import tolerancia

    if tol is None:
        tol = tolerancia.kernel_mm()
    # Las puntas de una spline o de un arco de elipse abiertos no se mueven
    # (moverlas cambia la curva), pero sirven de **anclas**: van primero, y
    # las líneas y arcos vecinos se sueldan a ellas.
    anclas = []
    for e in entidades:
        t = e.get("tipo")
        try:
            if t == "spline" and not e.get("cerrada"):
                from core import entidades as ent_mod
                c = ent_mod.de_dict(e).curva()
                anclas += [c.punto(x)[:2] for x in c.dominio]
            elif t == "elipse" and (e["param_fin"] - e["param_ini"]) % (2 * math.pi) > 1e-9:
                c, (ax, ay), k = e["centro"], e["eje_mayor"], e["razon"]
                for u in (e["param_ini"], e["param_fin"]):
                    anclas.append([c[0] + ax * math.cos(u) - ay * k * math.sin(u),
                                   c[1] + ay * math.cos(u) + ax * k * math.sin(u)])
        except (ValueError, KeyError, ArithmeticError):
            continue
    puntas = []          # (índice de entidad, cuál, punto)
    for i, e in enumerate(entidades):
        t = e.get("tipo")
        if t == "linea":
            puntas += [(i, "p1", e["p1"]), (i, "p2", e["p2"])]
        elif t == "arco":
            a, _, b = _extremos_de_arco(e)
            puntas += [(i, "a", a), (i, "b", b)]
        elif t == "polilinea" and not e.get("cerrada") and len(e.get("puntos") or []) >= 2:
            puntas += [(i, "ini", e["puntos"][0]), (i, "fin", e["puntos"][-1])]
    if not puntas:
        return entidades
    reps = tolerancia.soldar(anclas + [p for _, _, p in puntas], tol)[len(anclas):]
    salida = [dict(e) for e in entidades]
    for (i, cual, _), rep in zip(puntas, reps):
        e = salida[i]
        if cual in ("p1", "p2"):
            e[cual] = [rep[0], rep[1]]
        elif cual in ("a", "b"):
            if e.get("tipo") == "arco":
                a, m, b = _extremos_de_arco(entidades[i])
                salida[i] = e = {"tipo": "arco3", "p1": a, "pm": m, "p2": b}
            e["p1" if cual == "a" else "p2"] = [rep[0], rep[1]]
        else:
            pts = [list(v) for v in e["puntos"]]
            k = 0 if cual == "ini" else len(pts) - 1
            pts[k] = [rep[0], rep[1]] + pts[k][2:]
            e["puntos"] = pts
    return salida


def caras_de(entidades: list[dict], tol: float | None = None) -> list[Face]:
    """Las caras del boceto, con sus huecos y sus islas (fase C1).

    Cada contorno cerrado se clasifica por cuántos otros lo rodean: con un
    número par es borde de material, con uno impar es hueco. Así un marco con
    una ventana y un botón dentro de la ventana da dos caras: el marco con su
    hueco, y el botón. Dos contornos que se cruzan no tienen anidamiento claro
    y se avisa: hay que unirlos antes (UNION) o recortarlos.
    """
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON

    entidades = soldadas(entidades, tol)
    aristas = [a for e in entidades for a in aristas_de(e)]
    if not aristas:
        raise ValueError("el boceto no trae geometría")
    contornos = Wire.combine(aristas)
    cerrados = [w for w in contornos if w.is_closed]
    if not cerrados:
        raise ValueError("el boceto no forma ningún contorno cerrado")
    planas = [Face(w) for w in cerrados]

    def dentro(i, j):
        """¿El contorno i está dentro de la cara j? Se miran varios de sus
        puntos: si unos caen dentro y otros fuera, los dos se cruzan."""
        w = cerrados[i]
        estados = set()
        for k in range(8):
            p = w.position_at(k / 8)
            st = BRepClass_FaceClassifier(planas[j].wrapped, p.to_pnt(), 1e-7).State()
            if st != TopAbs_ON:
                estados.add(st == TopAbs_IN)
        if len(estados) > 1:
            raise ValueError("dos contornos del boceto se cruzan: únelos (UNION) o recórtalos antes")
        return estados == {True}

    n = len(cerrados)
    # El cruce se revisa en todos los pares (dos iguales que se traslapan
    # también se cruzan); estar dentro, sólo de uno más grande.
    padres = {i: [] for i in range(n)}
    for i in range(n):
        for j in range(n):
            if j != i and dentro(i, j) and planas[j].area > planas[i].area:
                padres[i].append(j)
    profundidad = {i: len(padres[i]) for i in range(n)}
    caras = []
    for i in range(n):
        if profundidad[i] % 2:
            continue                                   # es hueco
        # Sus huecos: los que tiene adentro a un nivel más de profundidad.
        huecos = [cerrados[k] for k in range(n)
                  if i in padres[k] and profundidad[k] == profundidad[i] + 1]
        caras.append(Face(planas[i].outer_wire(), [Face(h).outer_wire() for h in huecos]))
    return sorted(caras, key=lambda f: f.area, reverse=True)


def cara_de(entidades: list[dict], tol: float | None = None):
    """La cara del boceto; si trae varias piezas separadas, un compuesto con
    todas (que se extruye entero). Ver `caras_de`."""
    from build123d import Compound

    caras = caras_de(entidades, tol)
    return caras[0] if len(caras) == 1 else Compound(caras)


def solido_de(entidades: list[dict], espesor: float):
    return extrude(cara_de(entidades), amount=espesor)
