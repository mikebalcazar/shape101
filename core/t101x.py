"""Traer una cocina de Taller 101  ·  features 6 y 69 a 74.

Un `.t101x` es el proyecto de Taller 101: catálogo, estándar y una lista de
gabinetes con sus medidas y su posición en la cocina. Es JSON plano — lo escribe
`core/proyecto.py` de allá — y aquí sólo se leen los gabinetes: el despiece, el
nesting y los precios son trabajo de Taller 101 y no se duplican.

De cada gabinete se dibuja **la planta y el alzado**, alineados uno encima del
otro, dentro de un bloque con el nombre del mueble. Que el alzado quede sobre su
planta no es adorno: es como se lee un plano de cocina, y sale gratis si el
bloque lleva las dos vistas.

## Lo que NO hace, a propósito

El despiece pieza por pieza —laterales, entrepaños, cantos— lo calcula Taller
101 y lo exporta en DXF. shape101 abre ese DXF como cualquier otro. Recalcular
aquí las mismas piezas con otro código sería tener dos motores que se contradicen
la primera vez que cambie una holgura, y el que estaría mal sería siempre éste.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

from . import entidades as ent_mod
from . import capas as mod_capas
from .capas import Capa
from .documento import Documento

ORIGEN = "t101x"

# Separación entre la planta y el alzado que va encima, y entre muebles.
HUECO_VISTAS = 400.0
HOLGURA_FRENTE = 2.0        # el hueco que se ve entre puerta y puerta
ESPESOR = 19.0              # tablero, sólo para dibujar el fondo de la planta

CAPA_CUERPO = "T101-CUERPO"
CAPA_FRENTES = "T101-FRENTES"
CAPA_COTAS = mod_capas.CAPA_COTAS      # las cotas siempre en la suya
CAPA_TEXTO = "T101-TEXTO"


class T101xInvalido(ValueError):
    pass


# =========================================================================
# Lectura
# =========================================================================
def leer(ruta) -> dict:
    ruta = pathlib.Path(ruta)
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise T101xInvalido(f"El archivo no es un proyecto de Taller 101: {exc}") from exc
    if not isinstance(datos, dict) or "gabinetes" not in datos:
        raise T101xInvalido("Este archivo no trae gabinetes: ¿es un .t101x?")
    return datos


def resumen(datos: dict) -> dict:
    gs = datos.get("gabinetes") or []
    return {
        "nombre": datos.get("nombre", ""),
        "cliente": datos.get("cliente", ""),
        "gabinetes": len(gs),
        "bajos": sum(1 for g in gs if g.get("tipo") == "base"),
        "aereos": sum(1 for g in gs if g.get("tipo") == "aereo"),
        "nombres": [g.get("nombre", "?") for g in gs],
    }


# =========================================================================
# Las vistas de un mueble  ·  feature 69
# =========================================================================
def _frentes_repartidos(g: dict, alto_util: float) -> list[dict]:
    """Reparte el alto entre los frentes. Los que traen medida la conservan;
    los que vienen en blanco se reparten lo que sobra — es la misma regla de
    Taller 101, y por eso las dos apps enseñan lo mismo."""
    frentes = []
    for f in g.get("frentes") or []:
        for _ in range(max(1, int(f.get("n", 1) or 1))):
            frentes.append({"tipo": f.get("tipo", "puerta"), "alto": f.get("alto")})
    if not frentes:
        return []
    fijos = sum(f["alto"] for f in frentes if f["alto"])
    libres = [f for f in frentes if not f["alto"]]
    if libres:
        sobra = max(alto_util - fijos, 0.0) / len(libres)
        for f in libres:
            f["alto"] = sobra
    return frentes


def _vistas_de(g: dict, estandar: dict) -> list:
    """Planta y alzado de un mueble, en coordenadas relativas a su esquina."""
    ancho = float(g.get("ancho", 0) or 0)
    alto = float(g.get("alto", 0) or 0)
    prof = float(g.get("prof", 0) or 0)
    if ancho <= 0 or alto <= 0 or prof <= 0:
        raise T101xInvalido(f"El mueble «{g.get('nombre', '?')}» no trae medidas")

    piezas = []

    def rect(x, y, w, h, capa):
        piezas.append(ent_mod.Polilinea(
            capa=capa, cerrada=True, origen=ORIGEN,
            puntos=[[x, y, 0], [x + w, y, 0], [x + w, y + h, 0], [x, y + h, 0]]))

    # --- planta: el cuerpo visto desde arriba, con su frente ---------------
    rect(0, 0, ancho, prof, CAPA_CUERPO)
    rect(0, 0, ancho, ESPESOR, CAPA_FRENTES)          # el frente da a la cocina

    # --- alzado, justo encima de la planta ---------------------------------
    y0 = prof + HUECO_VISTAS
    rect(0, y0, ancho, alto, CAPA_CUERPO)

    zoclo = float(estandar.get("altura_zoclo", 100) or 100)
    if g.get("tipo") == "base" and g.get("con_zoclo", True):
        if g.get("altura_zoclo") is not None:
            zoclo = float(g["altura_zoclo"])
        piezas.append(ent_mod.Linea(capa=CAPA_CUERPO, origen=ORIGEN,
                                    p1=[0, y0 + zoclo], p2=[ancho, y0 + zoclo]))
    else:
        zoclo = 0.0

    alto_util = alto - zoclo
    frentes = _frentes_repartidos(g, alto_util)
    y = y0 + zoclo
    for f in frentes:
        h = float(f["alto"] or 0)
        if h <= 0:
            continue
        rect(HOLGURA_FRENTE, y + HOLGURA_FRENTE,
             ancho - 2 * HOLGURA_FRENTE, h - 2 * HOLGURA_FRENTE, CAPA_FRENTES)
        if f["tipo"] == "cajon":
            # la jaladera del cajón, centrada arriba: distingue un cajón de una
            # puerta de un vistazo, que es para lo que sirve un alzado
            jal = min(ancho * 0.4, 200.0)
            yj = y + h - 60
            piezas.append(ent_mod.Linea(capa=CAPA_FRENTES, origen=ORIGEN,
                                        p1=[(ancho - jal) / 2, yj],
                                        p2=[(ancho + jal) / 2, yj]))
        y += h

    # --- el rótulo del mueble ---------------------------------------------
    piezas.append(ent_mod.Texto(
        capa=CAPA_TEXTO, origen=ORIGEN, p=[0, y0 - 180], altura=60,
        texto=f"{g.get('nombre', '?')}  {ancho:g}×{alto:g}×{prof:g}"))
    return piezas


# =========================================================================
# Generar el dibujo  ·  features 70, 71
# =========================================================================
def _asegurar_capas(doc: Documento) -> None:
    from .capas import PLANTILLA_T101
    faltan = {c.nombre: c for c in PLANTILLA_T101}
    for nombre in (CAPA_CUERPO, CAPA_FRENTES, CAPA_COTAS, CAPA_TEXTO):
        if nombre not in doc.capas and nombre in faltan:
            doc.capa_agregar(Capa.de_dict(faltan[nombre].a_dict()))


def limpiar_generado(doc: Documento) -> int:
    """Quita lo que generó una importación anterior y **sólo** eso.

    Es la mitad difícil de la feature 72: lo que alguien anotó encima —una cota
    a mano, una nota de taller— no lo puso la importación y tiene que quedarse.
    Por eso cada entidad generada viene marcada con su origen.
    """
    quitar = [e.id for e in doc.entidades.values() if e.origen == ORIGEN]
    for id_ in quitar:
        doc.borrar(id_)
    for nombre in [b.nombre for b in doc.bloques.values()
                   if any(s.origen == ORIGEN for s in b.entidades)]:
        doc.bloques.pop(nombre, None)
    return len(quitar)


def generar(doc: Documento, datos: dict, ruta: str = "",
            acotar: bool = True) -> dict:
    """Dibuja la cocina completa. Devuelve qué se hizo."""
    _asegurar_capas(doc)
    estandar = datos.get("estandar") or {}
    gabinetes = datos.get("gabinetes") or []
    if not gabinetes:
        raise T101xInvalido("El proyecto no tiene gabinetes")

    borradas = limpiar_generado(doc)

    doc.nombre = doc.nombre if doc.nombre not in ("", "Sin título") else datos.get("nombre") or "Cocina"
    doc.cliente = doc.cliente or datos.get("cliente", "")

    bloques, insertados = [], []
    for g in gabinetes:
        nombre = str(g.get("nombre") or f"Mueble {len(bloques) + 1}")
        base = nombre
        n = 2
        while base in doc.bloques:                  # dos muebles con el mismo nombre
            base = f"{nombre} ({n})"
            n += 1
        piezas = _vistas_de(g, estandar)
        doc.bloque_agregar(ent_mod.Bloque(nombre=base, base=[0.0, 0.0],
                                          entidades=piezas,
                                          descripcion=f"De {pathlib.Path(ruta).name}"))
        bloques.append(base)
        # La posición en la cocina de Taller 101: X a la derecha, Z hacia el
        # frente. En un plano en planta, esa Z es la Y del papel.
        ins = doc.agregar(ent_mod.Insercion(
            capa=CAPA_CUERPO, origen=ORIGEN, bloque=base,
            p=[float(g.get("pos_x", 0) or 0), float(g.get("pos_z", 0) or 0)],
            rotacion=float(g.get("rot", 0) or 0)))
        insertados.append(ins.id)

    cotas = _acotar(doc, gabinetes, estandar) if acotar else 0

    doc.origen_t101x = {
        "ruta": str(ruta),
        "bloques": bloques,
        "importado": dt.datetime.now().isoformat(timespec="seconds"),
        "gabinetes": len(gabinetes),
    }
    return {"gabinetes": len(gabinetes), "bloques": bloques,
            "cotas": cotas, "borradas": borradas}


def _acotar(doc: Documento, gabinetes: list, estandar: dict) -> int:
    """Acota la corrida como se acota a mano  ·  feature 69.

    Un ancho por mueble debajo de las plantas, el total de la corrida debajo de
    todos, y **una sola** cota de altura por cada altura distinta, a la
    izquierda de todo. Poner la altura en cada mueble llena el alzado de
    números repetidos que tapan justo lo que hay que ver — que es el error que
    comete cualquier generador automático la primera vez.

    Las cotas van **fuera** de los bloques: dentro no se podrían mover ni
    borrar una por una, y lo primero que hace cualquiera con un plano generado
    es correr una cota que le estorba.
    """
    utiles = [g for g in gabinetes if float(g.get("ancho", 0) or 0) > 0]
    if not utiles:
        return 0
    n = 0

    # --- anchos, debajo de cada planta ------------------------------------
    for g in utiles:
        ancho = float(g["ancho"])
        x = float(g.get("pos_x", 0) or 0)
        z = float(g.get("pos_z", 0) or 0)
        doc.agregar(ent_mod.Cota(
            capa=CAPA_COTAS, origen=ORIGEN, clase="lineal", rotacion=0,
            puntos=[[x, z], [x + ancho, z], [x, z - 250]]))
        n += 1

    # --- el total de la corrida, un escalón más abajo ---------------------
    x0 = min(float(g.get("pos_x", 0) or 0) for g in utiles)
    x1 = max(float(g.get("pos_x", 0) or 0) + float(g["ancho"]) for g in utiles)
    z0 = min(float(g.get("pos_z", 0) or 0) for g in utiles)
    if len(utiles) > 1:
        doc.agregar(ent_mod.Cota(
            capa=CAPA_COTAS, origen=ORIGEN, clase="lineal", rotacion=0,
            puntos=[[x0, z0], [x1, z0], [x0, z0 - 600]]))
        n += 1

    # --- una altura por cada altura distinta, a la izquierda --------------
    vistos = {}
    for g in utiles:
        alto = round(float(g.get("alto", 0) or 0), 1)
        prof = float(g.get("prof", 0) or 0)
        z = float(g.get("pos_z", 0) or 0)
        clave = (g.get("tipo"), alto, round(z + prof, 1))
        if alto <= 0 or clave in vistos:
            continue
        vistos[clave] = True
        y0 = z + prof + HUECO_VISTAS
        x = x0 - 250 - 300 * (len(vistos) - 1)
        doc.agregar(ent_mod.Cota(
            capa=CAPA_COTAS, origen=ORIGEN, clase="lineal", rotacion=90,
            puntos=[[x0, y0], [x0, y0 + alto], [x, y0]]))
        n += 1
    return n


# =========================================================================
# Regenerar  ·  feature 72
# =========================================================================
def regenerar(doc: Documento) -> dict:
    """Vuelve a leer el `.t101x` de donde salió el dibujo y lo rehace.

    Lo que se dibujó a mano encima se queda: sólo se rehace lo marcado como
    generado. Es la diferencia entre un plano que se puede actualizar y uno que
    hay que volver a anotar entero cada vez que el mueble cambia de medida.
    """
    info = doc.origen_t101x
    if not isinstance(info, dict) or not info.get("ruta"):
        raise T101xInvalido("Este dibujo no vino de un .t101x")
    ruta = pathlib.Path(info["ruta"])
    if not ruta.exists():
        raise T101xInvalido(f"Ya no está el archivo original: {ruta}")
    return generar(doc, leer(ruta), str(ruta))
