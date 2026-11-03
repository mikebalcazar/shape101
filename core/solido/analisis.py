"""Análisis de curvatura de superficies y sólidos  ·  fase D3.

Lo que Rhino llama CurvatureAnalysis y Zebra: ver, antes de mandar una pieza
a la CNC o al render, si una superficie es lisa de verdad. Para eso hacen
falta datos que la malla de pintar no trae: la **normal exacta** y las
**curvaturas** en cada vértice, sacadas de la superficie misma (no de los
triángulos, que son planos y no tienen curvatura).

Por cada cara: se tesela más fino que para pintar, y en el (u, v) de cada nodo
se le pregunta a la superficie (BRepLProp_SLProps) su normal, su curvatura
gaussiana (K = k1·k2: positiva en un domo, negativa en una silla, cero en lo
plano o desarrollable) y su curvatura media (H = (k1 + k2) / 2).

Una cara invertida (su normal apunta al revés de la de su superficie) voltea
la normal y el signo de H; K no cambia.
"""

from __future__ import annotations

#: Más fina que la malla de pintar (0.5 / 0.3): el mapa y la cebra se leen
#: en la interpolación entre vértices, y una malla gruesa los pinta a saltos.
TOLERANCIA = 0.1
ANGULAR = 0.15


def de_cara(f, tolerancia: float = TOLERANCIA, angular: float = ANGULAR) -> dict:
    """{"v": [...], "i": [...], "n": [...], "kg": [...], "km": [...]} de una cara."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.TopLoc import TopLoc_Location

    cara = f.wrapped
    BRepMesh_IncrementalMesh(cara, tolerancia, False, angular, True)
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(cara, loc)
    if tri is None:
        return {"v": [], "i": [], "n": [], "kg": [], "km": []}
    trsf = loc.Transformation()
    invertida = cara.Orientation() == TopAbs_REVERSED
    ad = BRepAdaptor_Surface(cara)
    props = BRepLProp_SLProps(ad, 2, 1e-7)
    u0, u1, v0, v1 = ad.FirstUParameter(), ad.LastUParameter(), ad.FirstVParameter(), ad.LastVParameter()
    eu, ev = (u1 - u0) * 1e-7, (v1 - v0) * 1e-7
    v, n, kg, km = [], [], [], []
    for k in range(1, tri.NbNodes() + 1):
        p = tri.Node(k).Transformed(trsf)
        v += [p.X(), p.Y(), p.Z()]
        uv = tri.UVNode(k) if tri.HasUVNodes() else None
        g = h = 0.0
        nn = [0.0, 0.0, 1.0]
        if uv is not None:
            # En un punto singular de la parametrización (el polo de una
            # esfera) la superficie no sabe su normal ni su curvatura: se le
            # pregunta un poquito al lado, hacia adentro del dominio. Poner
            # cero ahí pintaba una mancha de «plano» en la punta de un domo.
            for du, dv in ((0, 0), (eu, 0), (-eu, 0), (0, ev), (0, -ev), (eu, ev), (-eu, -ev)):
                props.SetParameters(min(u1, max(u0, uv.X() + du)), min(v1, max(v0, uv.Y() + dv)))
                if props.IsNormalDefined() and props.IsCurvatureDefined():
                    d = props.Normal()
                    nn = [d.X(), d.Y(), d.Z()]
                    g, h = props.GaussianCurvature(), props.MeanCurvature()
                    break
        if invertida:
            nn = [-c for c in nn]
            h = -h
        n += nn
        kg.append(g)
        km.append(h)
    ix = []
    for k in range(1, tri.NbTriangles() + 1):
        a, b, c = tri.Triangle(k).Get()
        ix += [a - 1, c - 1, b - 1] if invertida else [a - 1, b - 1, c - 1]
    return {"v": v, "i": ix, "n": n, "kg": kg, "km": km}


def analisis(reg) -> dict:
    """El análisis de todas las caras de una pieza regenerada, con el rango de
    la curvatura gaussiana (para la escala de colores)."""
    caras = []
    for nombre, f in reg.nombrador.caras.items():
        c = de_cara(f)
        c["nombre"] = nombre
        caras.append(c)
    todas = [abs(k) for c in caras for k in c["kg"]]
    return {"caras": caras, "kg_max": max(todas) if todas else 0.0}
