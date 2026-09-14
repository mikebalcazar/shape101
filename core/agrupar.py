"""Grupos y EXPLOTAR  ·  lo pidió Mike el 4-sep.

**Grupo**: varias entidades que se agarran juntas. Picar una selecciona todas.
Es lo que hace GROUP en AutoCAD, y es distinto de un bloque: un bloque es una
definición que se inserta muchas veces; un grupo es una selección con nombre.
Aquí un grupo es sólo una marca en cada entidad (`Entidad.grupo`): no hay tabla
aparte que mantener, y cada entidad sigue siendo ella misma —se puede mover
sola si se desagrupa, y sale al DXF sin que nadie tenga que traducir nada—.

**Explotar**: deshacer una cosa compuesta en sus partes, en su sitio.

  · una inserción de bloque → las entidades del bloque, transformadas;
  · una polilínea → líneas y arcos;
  · un rayado → las polilíneas de su contorno;
  · una cota o una entidad ajena («cruda») → sus rayas y su texto. Es lo que
    hace **editable** lo que vino de otro programa: la cota de AutoCAD entra
    intacta para no moverla un pelo, y si alguien la quiere tocar, la explota y
    ya son líneas suyas;
  · un grupo → sus miembros, sueltos.

Todo pasa por `Documento.agregar/borrar/modificar` para que un Ctrl+Z lo
deshaga entero.
"""

from __future__ import annotations

import math

from . import dibujo
from . import entidades as E
from .documento import Documento


# =========================================================================
# Grupos
# =========================================================================

def _nombre_libre(doc: Documento) -> str:
    usados = {getattr(e, "grupo", "") for e in doc.entidades.values()}
    n = 1
    while f"G{n}" in usados:
        n += 1
    return f"G{n}"


def miembros(doc: Documento, nombre: str) -> list[str]:
    return [i for i in doc.orden
            if getattr(doc.entidades[i], "grupo", "") == nombre]


def agrupar(doc: Documento, ids: list[str]) -> str:
    """Mete estas entidades en un grupo nuevo. Si alguna ya estaba en otro, se
    lleva a **todo** ese grupo: los grupos no se parten por accidente."""
    todos = set()
    for i in ids:
        e = doc.entidades.get(i)
        if e is None:
            continue
        g = getattr(e, "grupo", "")
        todos.update(miembros(doc, g) if g else [i])
    if len(todos) < 2:
        raise ValueError("Un grupo necesita al menos dos entidades.")
    nombre = _nombre_libre(doc)
    for i in todos:
        doc.modificar(i, {"grupo": nombre})
    return nombre


def desagrupar(doc: Documento, ids: list[str]) -> list[str]:
    """Deshace los grupos a los que pertenezca cualquiera de estas entidades.
    Devuelve los ids que quedaron sueltos."""
    grupos = {getattr(doc.entidades[i], "grupo", "")
              for i in ids if i in doc.entidades}
    sueltos = []
    for g in grupos:
        if not g:
            continue
        for i in miembros(doc, g):
            doc.modificar(i, {"grupo": ""})
            sueltos.append(i)
    return sueltos


# =========================================================================
# Explotar
# =========================================================================

def _matriz(px, py, sx, sy, rot_grados):
    """Transformación de una inserción: escala, giro y traslado, en ese orden."""
    r = math.radians(rot_grados or 0.0)
    c, s = math.cos(r), math.sin(r)

    def punto(p):
        x, y = p[0] * sx, p[1] * sy
        return [px + x * c - y * s, py + x * s + y * c]

    return punto


def _transformada(e, punto, sx, sy, rot, capa_ins: str, color_ins):
    """Una copia de `e` con la transformación de la inserción aplicada.

    Regla de AutoCAD que aquí se respeta: lo que dentro del bloque está en la
    capa «0» toma la capa de la inserción; lo demás conserva la suya.
    """
    d = e.a_dict()
    d.pop("id", None)
    d["handle_origen"] = ""
    if d.get("capa") in ("0", "", None):
        d["capa"] = capa_ins
    if d.get("color") is None and color_ins:
        d["color"] = color_ins
    f = (abs(sx) + abs(sy)) / 2          # escala «uniforme» para radios y letras
    espejo = (sx < 0) != (sy < 0)
    t = e.tipo
    if t == "linea":
        d["p1"], d["p2"] = punto(e.p1), punto(e.p2)
    elif t == "polilinea":
        d["puntos"] = [[*punto(v), (-(v[2]) if espejo else v[2]) if len(v) > 2 else 0.0]
                       for v in e.puntos]
    elif t == "circulo":
        d["centro"], d["radio"] = punto(e.centro), e.radio * f
    elif t == "arco":
        a0, a1 = e.ang_ini + rot, e.ang_fin + rot
        d["centro"], d["radio"] = punto(e.centro), e.radio * f
        d["ang_ini"], d["ang_fin"] = (a1, a0) if espejo else (a0, a1)
    elif t == "elipse":
        c = punto(e.centro)
        punta = punto([e.centro[0] + e.eje_mayor[0], e.centro[1] + e.eje_mayor[1]])
        d["centro"], d["eje_mayor"] = c, [punta[0] - c[0], punta[1] - c[1]]
    elif t == "spline":
        d["puntos_ajuste"] = [punto(p) for p in (e.puntos_ajuste or [])]
        d["puntos_control"] = [punto(p) for p in (e.puntos_control or [])]
    elif t == "punto":
        d["p"] = punto(e.p)
    elif t == "solido":
        d["puntos"] = [punto(p) for p in e.puntos]
    elif t in ("texto", "textom"):
        d["p"] = punto(e.p)
        d["altura"] = e.altura * f
        d["rotacion"] = (e.rotacion or 0.0) + rot
        if t == "textom":
            d["ancho"] = e.ancho * f
    elif t == "insercion":
        d["p"] = punto(e.p)
        d["rotacion"] = (e.rotacion or 0.0) + rot
        d["escala"] = [e.escala[0] * sx, e.escala[1] * sy]
    elif t == "rayado":
        d["rutas"] = [[[*punto(v), (-(v[2]) if espejo else v[2]) if len(v) > 2 else 0.0]
                       for v in ruta] for ruta in e.rutas]
    elif t == "cota":
        d["puntos"] = [punto(p) for p in e.puntos]
        d["liga"] = []
    elif t == "cruda":
        d["dibujo"] = [[punto(p) for p in pts] for pts in (e.dibujo or [])]
        d["textos"] = [{**tx, "p": punto(tx["p"]),
                        "altura": tx.get("altura", 2.5) * f,
                        "rotacion": tx.get("rotacion", 0.0) + rot}
                       for tx in (e.textos or [])]
    else:
        return None
    return E.de_dict(d)


def _partes_de_insercion(doc: Documento, ins) -> list:
    bl = doc.bloques.get(ins.bloque)
    if bl is None:
        return []
    sx, sy = ins.escala[0], ins.escala[1]
    punto = _matriz(ins.p[0] - bl.base[0] * sx, ins.p[1] - bl.base[1] * sy,
                    sx, sy, ins.rotacion)
    # El punto base del bloque: la matriz de arriba ya lo descuenta, igual que
    # hace `dibujo._trazos_de` al pintar. Si se hiciera distinto, lo explotado
    # caería a un lado de donde se veía.
    salida = []
    for sub in bl.entidades:
        nuevo = _transformada(sub, punto, sx, sy, ins.rotacion, ins.capa, ins.color)
        if nuevo is not None:
            nuevo.espacio = ins.espacio
            salida.append(nuevo)
    return salida


def _partes_de_polilinea(pl) -> list:
    from .geometria import _arco_de_bulge
    pts = pl.puntos
    n = len(pts)
    if n < 2:
        return []
    tramos = list(range(n - 1)) + ([n - 1] if pl.cerrada and n > 2 else [])
    comun = {"capa": pl.capa, "color": pl.color, "grosor": pl.grosor,
             "tipo_linea": pl.tipo_linea, "espacio": pl.espacio}
    salida = []
    for i in tramos:
        a, b = pts[i], pts[(i + 1) % n]
        bulge = a[2] if len(a) > 2 else 0.0
        arco = _arco_de_bulge(a, b, bulge) if bulge else None
        if arco:
            salida.append(E.Arco(centro=arco["c"], radio=arco["r"],
                                 ang_ini=arco["a0"], ang_fin=arco["a1"], **comun))
        else:
            salida.append(E.Linea(p1=[a[0], a[1]], p2=[b[0], b[1]], **comun))
    return salida


def _partes_de_rayado(r) -> list:
    comun = {"capa": r.capa, "color": r.color, "grosor": r.grosor,
             "tipo_linea": r.tipo_linea, "espacio": r.espacio}
    return [E.Polilinea(puntos=[[v[0], v[1], v[2] if len(v) > 2 else 0.0] for v in ruta],
                        cerrada=True, **comun) for ruta in r.rutas if len(ruta) >= 2]


def _partes_dibujadas(doc: Documento, e) -> list:
    """Lo que se ve de una cota o de una entidad ajena, como líneas y textos."""
    comun = {"capa": e.capa, "color": e.color, "grosor": e.grosor,
             "tipo_linea": e.tipo_linea, "espacio": e.espacio}
    salida = []
    for t in dibujo.trazos_de(doc, e):
        if t.get("clase") == "linea" and len(t.get("puntos") or []) >= 2:
            pts = t["puntos"]
            if len(pts) == 2:
                salida.append(E.Linea(p1=list(pts[0][:2]), p2=list(pts[1][:2]), **comun))
            else:
                salida.append(E.Polilinea(puntos=[[p[0], p[1], 0.0] for p in pts],
                                          cerrada=False, **comun))
        elif t.get("clase") == "texto" and t.get("texto"):
            salida.append(E.Texto(p=list(t["p"][:2]), texto=str(t["texto"]),
                                  altura=float(t.get("altura", 2.5)),
                                  rotacion=float(t.get("rotacion", 0.0) or 0.0),
                                  alineacion=t.get("alineacion", "IZQ"), **comun))
    return salida


def partes(doc: Documento, e) -> list | None:
    """En qué se convierte esta entidad al explotarla. `None` si no se puede."""
    t = e.tipo
    if t == "insercion":
        return _partes_de_insercion(doc, e)
    if t == "polilinea":
        return _partes_de_polilinea(e)
    if t == "rayado":
        return _partes_de_rayado(e)
    if t in ("cota", "cruda"):
        return _partes_dibujadas(doc, e)
    return None


def explotar(doc: Documento, ids: list[str]) -> dict:
    """Explota lo que se pueda de esta lista. Devuelve qué se creó, qué se quitó
    y qué se dejó como estaba (con el porqué)."""
    nuevos, quitados, dejadas = [], [], []
    # Un grupo se explota desagrupando, sin tocar las entidades.
    for i in list(ids):
        e = doc.entidades.get(i)
        if e is not None and getattr(e, "grupo", ""):
            desagrupar(doc, [i])
    for i in ids:
        e = doc.entidades.get(i)
        if e is None:
            continue
        p = partes(doc, e)
        if p is None:
            dejadas.append((i, e.tipo))
            continue
        if not p:
            dejadas.append((i, e.tipo))
            continue
        for nuevo in p:
            nuevo.espacio = e.espacio
            doc.agregar(nuevo)
            nuevos.append(nuevo.id)
        doc.borrar(i)
        quitados.append(i)
    return {"nuevos": nuevos, "quitados": quitados, "dejadas": dejadas}
