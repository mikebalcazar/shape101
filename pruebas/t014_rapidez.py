"""t014 · Que una acción cueste lo que cambió, y no lo que mide el plano.

Mike, con un plano de 1 837 entidades: *«Los comandos tardan mucho… Incluso
para borrar se tarda mucho. Unos 3-5 segundos.»* El borrado tardaba 16 ms. Lo
que tardaba era lo de después: cada acción volvía a pedir el documento entero
teselado —9 500 trazos, 6 MB de JSON— para enterarse de que se borró una línea.

Ahora cada endpoint que modifica algo devuelve un **parche**. Esta prueba no
cronometra (un cronómetro en una máquina compartida miente); comprueba las dos
cosas de las que salía la lentitud, que sí son verificables:

1. **El parche no crece con el plano.** Borrar una línea en un plano de 200
   entidades y en uno de 2 000 tiene que costar lo mismo. Es la parte que de
   verdad importa: los planos de obra sólo se hacen más grandes.
2. **Lo pintado coincide con lo que hay en el servidor.** Un lienzo que se pinta
   por parches puede irse quedando atrás sin que nadie lo note, y entonces se
   está midiendo sobre un dibujo que no es el del archivo. Aquí se aplica el
   parche sobre la copia del cliente y se compara **trazo a trazo** contra lo que
   contestaría el documento completo.

Y la tercera, que costó un error el mismo día que se escribió la caché: **una
cota no depende sólo de sí misma y de su capa, sino de su estilo.** Cambiar el
estilo cambia las doscientas cotas del plano sin tocar ninguna.
"""

from __future__ import annotations

import json

import server
from core import entidades as ent
from pruebas import comun

DESCRIPCION = "el parche no crece con el plano, y lo pintado es lo que hay"


def _nuevo(entidades: int) -> list[str]:
    """Documento limpio con `entidades` líneas. Se habla con el servidor por
    sus propias funciones: es el mismo código que corre la app, sin red de por
    medio ni una dependencia más para las pruebas."""
    server.nuevo(None)
    ids = []
    for i in range(entidades):
        res = server.entidad_nueva(server.NuevaEntidad(
            entidad={"tipo": "linea", "puntos": None,
                     "p1": [0, i * 10], "p2": [1000, i * 10]}))
        ids.append(_id_de(res))
    return ids


def _cuerpo(res) -> dict:
    """Las respuestas salen como JSONResponse: se mira lo que lleva dentro."""
    if isinstance(res, dict):
        return res
    return json.loads(bytes(res.body).decode("utf-8"))


def _id_de(res) -> str:
    d = _cuerpo(res)
    return d.get("id") or (d.get("entidad") or {}).get("id") or (d.get("ids") or [None])[0]


def correr(r: comun.Reporte) -> None:
    _parche_no_crece(r)
    _lo_pintado_es_lo_que_hay(r)
    _las_cotas_no_se_cachean(r)


def _parche_no_crece(r: comun.Reporte) -> None:
    tamanos = {}
    for cuantas in (200, 2000):
        ids = _nuevo(cuantas)
        borrado = _cuerpo(server.entidad_borrar(ids[cuantas // 2]))
        parche = borrado.get("parche") or borrado
        tamanos[cuantas] = len(json.dumps(parche))

        completo = len(json.dumps(_cuerpo(server.trazos())))
        r.cierto(tamanos[cuantas] * 20 < completo,
                 f"con {cuantas} entidades, el parche de un borrado es una "
                 f"fracción de mandar el plano entero",
                 f"parche {tamanos[cuantas]} B contra {completo} B")

    chico, grande = tamanos[200], tamanos[2000]
    r.cierto(abs(grande - chico) < 200,
             "y el parche cuesta lo mismo con 200 entidades que con 2 000",
             f"{chico} B contra {grande} B")


def _lo_pintado_es_lo_que_hay(r: comun.Reporte) -> None:
    """El lienzo del cliente, simulado: se pinta una vez y luego se le aplican
    parches. Al final tiene que ser idéntico a lo que dice el servidor."""
    ids = _nuevo(60)

    pintado = {}          # id → trazos, como los guarda el cliente
    for t in _cuerpo(server.trazos())["trazos"]:
        pintado.setdefault(t.get("id"), []).append(t)

    def aplicar(parche: dict) -> None:
        for id_ in parche.get("quitar") or []:
            pintado.pop(id_, None)
        for t in parche.get("trazos") or []:
            pintado.setdefault(t.get("id"), []).append(t)

    # Una tanda de acciones de las de todos los días.
    aplicar(_parche_de(server.entidad_borrar(ids[3])))
    aplicar(_parche_de(server.entidad_nueva(server.NuevaEntidad(
        entidad={"tipo": "circulo", "centro": [500, 500], "radio": 120}))))
    aplicar(_parche_de(server.operacion(server.Operacion(
        accion="Mover", cambios={ids[10]: {"p2": [2000, 100]}}))))
    aplicar(_parche_de(server.deshacer()))
    aplicar(_parche_de(server.entidad_nueva(server.NuevaEntidad(
        entidad={"tipo": "cota", "clase": "lineal",
                 "puntos": [[0, 0], [1000, 0], [0, -100]]}))))

    del_servidor = {}
    for t in _cuerpo(server.trazos())["trazos"]:
        del_servidor.setdefault(t.get("id"), []).append(t)

    r.igual(sorted(pintado), sorted(del_servidor),
            "después de cinco acciones por parche, el lienzo tiene exactamente "
            "las mismas entidades que el servidor")

    distintos = [i for i in del_servidor
                 if json.dumps(pintado.get(i), sort_keys=True)
                 != json.dumps(del_servidor[i], sort_keys=True)]
    r.igual(distintos, [],
            "y cada una está pintada igual, trazo a trazo")


def _parche_de(res) -> dict:
    d = _cuerpo(res)
    return d.get("parche") or d


def _las_cotas_no_se_cachean(r: comun.Reporte) -> None:
    """Cambiar el estilo cambia todas las cotas sin tocar ninguna. Si las cotas
    se cachearan por entidad, el plano seguiría enseñando las viejas: un dibujo
    que no es el del archivo, y eso se descubre midiendo una pieza ya cortada."""
    server.nuevo(None)
    for i in range(5):
        server.entidad_nueva(server.NuevaEntidad(
            entidad={"tipo": "cota", "clase": "lineal",
                     "puntos": [[0, i * 100], [600, i * 100], [0, i * 100 - 60]]}))

    def altura_de_los_textos() -> list[float]:
        return sorted(t.get("altura") for t in _cuerpo(server.trazos())["trazos"]
                      if t.get("clase") == "texto" and t.get("altura"))

    antes = altura_de_los_textos()
    r.cierto(bool(antes), "las cinco cotas se pintan con su texto")

    estilo = dict(_cuerpo(server.estilos_cota())["estilos"]["T101"])
    server.estilo_cota_guardar(server.EstiloCota(
        nombre="T101",
        cambios={"altura_texto": float(estilo.get("altura_texto", 2.5)) * 2}))

    despues = altura_de_los_textos()
    r.cierto(despues and despues != antes,
             "cambiar el estilo cambia las cinco cotas sin tocar ninguna",
             f"antes {antes[:2]}… después {despues[:2]}…")
    if antes and despues:
        r.casi(despues[0] / antes[0], 2.0,
               "y cambian por lo que se cambió el estilo, no por otra cosa", 1e-6)
