"""t055 · Superficies: editarlas por sus puntos de control (como en Rhino).

En una superficie (fase D1) los tiradores traen ahora sus **puntos de control**
(polos), y arrastrar uno es una operación más del historial —`mover_polo`—:
se puede cambiar o quitar después, igual que un redondeo.

Se comprueba en el motor, que es donde vive la promesa:

- el polo movido queda exactamente donde se pidió y **ningún otro** cambia;
- en una superficie de una sola cara, mover el polo de una esquina mueve la
  esquina de la superficie lo mismo (en una B-spline sujeta coinciden);
- el desplazamiento se cambia en el historial y quitar el paso devuelve la
  superficie de antes;
- donde mover un polo rompería algo, no se ofrece y se avisa: en un sólido
  (lo abriría), en un parche recortado de RED (se despegaría de su borde) y en
  el borde de una cara que toca a otra (las despegaría).
"""

from __future__ import annotations

from fastapi import HTTPException

from core import entidades as E
from core import tolerancia
from core.documento import Documento
from core.solido import cuerpo as mod
from core.solido import rutas, superficies
from pruebas import comun

DESCRIPCION = "superficies: mover sus puntos de control, exacto y en el historial"


def _doc():
    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    tolerancia.enchufar(lambda: doc)
    mod.olvidar()
    return doc


def _agregar(doc, *ents):
    with doc.transaccion("Dibujar"):
        return [doc.agregar(e).id for e in ents]


def _polos(doc, cid, cara):
    reg = mod.regenerar(doc.entidades[cid])
    sup, _ = superficies.bspline_de(reg.nombrador.cara(cara))
    return {(i, j): (sup.Pole(i, j).X(), sup.Pole(i, j).Y(), sup.Pole(i, j).Z())
            for i in range(1, sup.NbUPoles() + 1) for j in range(1, sup.NbVPoles() + 1)}


def correr(r: comun.Reporte) -> None:
    previo = tolerancia._doc_actual
    try:
        _mover(r)
        _donde_no(r)
    finally:
        tolerancia.enchufar(previo)
        mod.olvidar()


def _mover(r: comun.Reporte) -> None:
    doc = _doc()
    ids = _agregar(doc, *[E.Spline(puntos_ajuste=[[0, 0], [100, 40 * k + 10], [200, 0]]) for k in range(3)])
    m = rutas.loft(rutas.Seleccion(ids=ids, separacion=50))
    cid = m["id"]
    t = rutas.tiradores(cid)
    r.cierto(len(t["polos"]) > 0, "una superficie trae sus puntos de control como tiradores", str(len(t["polos"])))
    interior = next(p for p in t["polos"] if p["i"] == 2 and p["j"] == 2)
    antes = _polos(doc, cid, interior["cara"])
    rutas.mover_polo(cid, rutas.MoverEnElMundo(nombre=interior["nombre"], d=[0, 0, 40]))
    despues = _polos(doc, cid, interior["cara"])
    movido = despues[(2, 2)]
    esperado = (antes[(2, 2)][0], antes[(2, 2)][1], antes[(2, 2)][2] + 40)
    r.cierto(max(abs(a - b) for a, b in zip(movido, esperado)) < 1e-9, "el polo (2, 2) queda 40 más arriba, exacto")
    otros = max(max(abs(a - b) for a, b in zip(antes[k], despues[k])) for k in antes if k != (2, 2))
    r.cierto(otros < 1e-9, "y ningún otro punto de control se mueve", f"{otros:.2e}")

    ops = list(doc.entidades[cid].operaciones)
    k = next(n for n, op in enumerate(ops) if op["op"] == "mover_polo")
    doc.entidades[cid].operaciones = mod.cambiar_operacion(ops, k, {"d/2": 10.0})
    mod.olvidar()
    r.casi(_polos(doc, cid, interior["cara"])[(2, 2)][2], antes[(2, 2)][2] + 10,
           "el desplazamiento se cambia en el historial (40 → 10)", 1e-9)
    doc.entidades[cid].operaciones = mod.quitar_operacion(list(doc.entidades[cid].operaciones), k)
    mod.olvidar()
    r.cierto(_polos(doc, cid, interior["cara"]) == antes, "y quitar el paso devuelve la superficie de antes")

    # Una sola cara: el polo de la esquina es la esquina.
    esquina = next(p for p in t["polos"] if p["i"] == 1 and p["j"] == 1)
    rutas.mover_polo(cid, rutas.MoverEnElMundo(nombre=esquina["nombre"], d=[0, 0, 25]))
    reg = mod.regenerar(doc.entidades[cid])
    esquinas = [v for v in reg.solido.vertices()
                if abs(v.X - esquina["p"][0]) < 1e-6 and abs(v.Y - esquina["p"][1]) < 1e-6]
    r.cierto(any(abs(v.Z - (esquina["p"][2] + 25)) < 1e-6 for v in esquinas),
             "en una superficie de una cara, mover el polo de la esquina sube la esquina lo mismo")


def _donde_no(r: comun.Reporte) -> None:
    doc = _doc()
    caja = E.Polilinea(puntos=[[0, 0], [100, 0], [100, 60], [0, 60]], cerrada=True)
    m = rutas.extruir(rutas.Extruir(ids=_agregar(doc, caja), mm=18))
    r.igual(rutas.tiradores(m["id"])["polos"], [], "un sólido no ofrece puntos de control (moverlos lo abriría)")
    try:
        rutas.mover_polo(m["id"], rutas.MoverEnElMundo(nombre="arriba#1,1", d=[0, 0, 5]))
        r.cierto(False, "mover un polo de un sólido debería avisar")
    except HTTPException as exc:
        r.cierto("sólido" in exc.detail, "y si se pide, avisa", exc.detail)

    bordes = [E.Linea(p1=[0, 0], p2=[200, 0]), E.Spline(puntos_ajuste=[[200, 0], [230, 100], [200, 200]]),
              E.Linea(p1=[200, 200], p2=[0, 200]), E.Spline(puntos_ajuste=[[0, 200], [-30, 100], [0, 0]])]
    m = rutas.red(rutas.Seleccion(ids=_agregar(doc, *bordes)))
    r.igual(rutas.tiradores(m["id"])["polos"], [],
            "un parche de RED va recortado por su borde: no ofrece puntos de control")

    perfil = E.Polilinea(puntos=[[0, 0], [30, 30], [60, 0]], cerrada=False)
    perfil.plano = "XZ"
    m = rutas.barrer(rutas.Seleccion(ids=_agregar(doc, perfil, E.Spline(puntos_ajuste=[[0, 0], [100, 50], [200, 0]]))))
    t = rutas.tiradores(m["id"])
    reg = mod.regenerar(doc.entidades[m["id"]])
    r.cierto(len(reg.solido.faces()) > 1, "un perfil de dos tramos barrido deja dos caras que se tocan")
    bordes_ofrecidos = []
    for p in t["polos"]:
        sup, _ = superficies.bspline_de(reg.nombrador.cara(p["cara"]))
        if p["i"] in (1, sup.NbUPoles()) or p["j"] in (1, sup.NbVPoles()):
            bordes_ofrecidos.append(p["nombre"])
    r.igual(bordes_ofrecidos, [], "y sólo se ofrecen los puntos de control de adentro, no los del borde")
